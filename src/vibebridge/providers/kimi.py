"""Kimi Code CLI provider implementation (print mode with stream-json)."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import AsyncIterator

from .base import BaseProvider, StreamEvent, StreamEventType


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class KimiTask:
    task_id: str
    user_message: str
    workdir: str
    status: TaskStatus = TaskStatus.PENDING
    process: asyncio.subprocess.Process | None = None
    output_lines: list[str] = field(default_factory=list)
    final_result: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class KimiProvider(BaseProvider):
    name = "kimi"
    display_name = "Kimi Code"

    def __init__(
        self,
        binary: str | None = None,
        default_workdir: str = "~/workspace",
    ):
        self.binary = binary or self._auto_detect_binary()
        self._default_workdir = os.path.expanduser(default_workdir)
        self._tasks: dict[str, KimiTask] = {}
        self._lock = asyncio.Lock()
        # Session continuity: workdir -> session_id
        self._session_mapping: dict[str, str] = {}

    def _auto_detect_binary(self) -> str:
        if env := os.getenv("KIMI_BINARY"):
            return env
        if path := shutil.which("kimi"):
            return path
        home = Path.home()
        candidates = [
            home / ".local/bin/kimi",
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        raise FileNotFoundError(
            "Kimi CLI not found. Please install kimi-cli or set KIMI_BINARY."
        )

    async def health_check(self) -> tuple[bool, str]:
        if not shutil.which(self.binary):
            return False, (
                "Kimi CLI not found in PATH. Install: "
                "https://moonshotai.github.io/kimi-cli/"
            )
        try:
            proc = await asyncio.create_subprocess_exec(
                self.binary,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            if proc.returncode == 0:
                return True, stdout.decode().strip()
            return False, f"Error: {stderr.decode().strip()}"
        except Exception as e:
            return False, str(e)

    def default_workdir(self) -> str:
        return self._default_workdir

    async def create_task(
        self,
        prompt: str,
        workdir: str,
        session_id: str,
        chat_id: str | None = None,
    ) -> str:
        wd = Path(workdir).expanduser()
        try:
            wd.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            wd = Path(self._default_workdir)
            try:
                wd.mkdir(parents=True, exist_ok=True)
            except Exception as e2:
                raise RuntimeError(
                    f"Cannot create workdir {workdir} or fallback {self._default_workdir}: {e2}"
                ) from e2

        task_id = f"kimi_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{session_id[-8:]}"
        task = KimiTask(
            task_id=task_id,
            user_message=prompt,
            workdir=str(wd),
        )
        async with self._lock:
            self._tasks[task_id] = task
        return task_id

    async def stream_task(self, task_id: str) -> AsyncIterator[StreamEvent]:
        task = await self._get_task(task_id)
        if not task:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                content=f"Task {task_id} not found",
                task_id=task_id,
            )
            return

        await self._update_task(task_id, status=TaskStatus.RUNNING)
        yield StreamEvent(
            type=StreamEventType.STATUS,
            content="正在启动 Kimi Code...",
            task_id=task_id,
        )

        process: asyncio.subprocess.Process | None = None
        try:
            wd = task.workdir
            session_args = []
            if wd in self._session_mapping:
                session_args = ["--continue"]

            cmd = [
                self.binary,
                "--print",
                "--output-format",
                "stream-json",
                "--yolo",
                "--work-dir",
                wd,
                *session_args,
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=wd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            await self._update_task(task_id, process=process)

            # Send user prompt via stdin
            if process.stdin is not None:
                process.stdin.write(task.user_message.encode("utf-8") + b"\n")
                await process.stdin.drain()
                process.stdin.close()

            buffer = ""
            stdout = process.stdout
            final_text_parts: list[str] = []
            has_error = False
            total_deadline = asyncio.get_event_loop().time() + 1200  # 20 min total

            if stdout is None:
                raise RuntimeError("Subprocess stdout is None")

            while True:
                remaining = total_deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    raise asyncio.TimeoutError("Total execution time exceeded 1200s")

                try:
                    chunk = await asyncio.wait_for(
                        stdout.read(4096), timeout=min(60.0, remaining)
                    )
                    if not chunk:
                        break
                    buffer += chunk.decode("utf-8", errors="replace")

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue

                        # Skip the resume hint line
                        if line.startswith("To resume this session:"):
                            # Extract session id for continuity
                            import re

                            m = re.search(r"kimi -r ([a-f0-9\-]+)", line)
                            if m:
                                self._session_mapping[wd] = m.group(1)
                            continue

                        try:
                            event = json.loads(line)
                            role = event.get("role", "")

                            if role == "assistant":
                                content = event.get("content", [])
                                for part in content:
                                    ptype = part.get("type", "")
                                    if ptype == "think":
                                        think = part.get("think", "")
                                        if think:
                                            yield StreamEvent(
                                                type=StreamEventType.STATUS,
                                                content=think[:200],
                                                task_id=task_id,
                                            )
                                    elif ptype == "text":
                                        text = part.get("text", "")
                                        if text:
                                            task.output_lines.append(text)
                                            final_text_parts.append(text)
                                            yield StreamEvent(
                                                type=StreamEventType.TEXT,
                                                content=text,
                                                task_id=task_id,
                                            )

                                # Tool calls
                                tool_calls = event.get("tool_calls", [])
                                for tc in tool_calls:
                                    fn = tc.get("function", {})
                                    name = fn.get("name", "unknown")
                                    args = fn.get("arguments", "")
                                    display = f"🛠️ {name}"
                                    if args:
                                        try:
                                            arg_obj = json.loads(args)
                                            cmd_str = arg_obj.get("command", "")
                                            if cmd_str:
                                                display += f": {cmd_str[:100]}..."
                                        except json.JSONDecodeError:
                                            pass
                                    yield StreamEvent(
                                        type=StreamEventType.TOOL_USE,
                                        content=display,
                                        task_id=task_id,
                                    )

                            elif role == "tool":
                                content = event.get("content", [])
                                for part in content:
                                    ptype = part.get("type", "")
                                    if ptype == "text":
                                        text = part.get("text", "")
                                        if text and text.startswith("<system>"):
                                            # System wrapper for tool result
                                            continue
                                        if text:
                                            yield StreamEvent(
                                                type=StreamEventType.STATUS,
                                                content=text[:200],
                                                task_id=task_id,
                                            )

                        except json.JSONDecodeError:
                            # Non-JSON line (e.g., resume hint) — ignore
                            pass

                except asyncio.TimeoutError:
                    if process.returncode is not None:
                        break
                    yield StreamEvent(
                        type=StreamEventType.STATUS,
                        content="⏳ Kimi Code 仍在运行，等待输出中...",
                        task_id=task_id,
                    )

            try:
                await asyncio.wait_for(process.wait(), timeout=30.0)
            except asyncio.TimeoutError:
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except Exception:
                    pass
                has_error = True
                task.error = "Kimi Code process did not exit in time after output ended"

            if process.returncode == 0 and not has_error:
                if final_text_parts:
                    final_result = "\n".join(final_text_parts)
                    task.final_result = final_result
                    await self._update_task(task_id, status=TaskStatus.COMPLETED)
                    yield StreamEvent(
                        type=StreamEventType.DONE,
                        content=final_result,
                        task_id=task_id,
                    )
                elif task.output_lines:
                    final_result = "\n".join(task.output_lines)
                    task.final_result = final_result
                    await self._update_task(task_id, status=TaskStatus.COMPLETED)
                    yield StreamEvent(
                        type=StreamEventType.DONE,
                        content=final_result,
                        task_id=task_id,
                    )
                else:
                    error_msg = task.error or "Kimi Code exited with no output"
                    await self._update_task(
                        task_id, status=TaskStatus.FAILED, error=error_msg
                    )
                    yield StreamEvent(
                        type=StreamEventType.ERROR,
                        content=error_msg,
                        task_id=task_id,
                    )
            else:
                error_msg = task.error or f"Kimi Code exited with code {process.returncode}"
                await self._update_task(
                    task_id,
                    status=TaskStatus.FAILED,
                    error=error_msg,
                )
                yield StreamEvent(
                    type=StreamEventType.ERROR,
                    content=error_msg,
                    task_id=task_id,
                )

        except FileNotFoundError:
            error_msg = "Kimi CLI 未找到，请确保已安装 kimi-cli"
            await self._update_task(task_id, status=TaskStatus.FAILED, error=error_msg)
            yield StreamEvent(
                type=StreamEventType.ERROR,
                content=error_msg,
                task_id=task_id,
            )
        except asyncio.TimeoutError as e:
            error_msg = f"任务执行超时: {e}"
            await self._update_task(task_id, status=TaskStatus.FAILED, error=error_msg)
            if process and process.returncode is None:
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except Exception:
                    pass
            yield StreamEvent(
                type=StreamEventType.ERROR,
                content=error_msg,
                task_id=task_id,
            )
        except Exception as e:
            error_msg = f"执行出错: {str(e)}"
            await self._update_task(task_id, status=TaskStatus.FAILED, error=error_msg)
            if process and process.returncode is None:
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except Exception:
                    pass
            yield StreamEvent(
                type=StreamEventType.ERROR,
                content=error_msg,
                task_id=task_id,
            )

    async def cancel_task(self, task_id: str) -> bool:
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if task.process and task.process.returncode is None:
                try:
                    task.process.terminate()
                    await asyncio.wait_for(task.process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    try:
                        task.process.kill()
                        await task.process.wait()
                    except Exception:
                        pass
                except Exception:
                    pass
            task.status = TaskStatus.CANCELLED
            task.updated_at = datetime.now()
            return True

    async def _get_task(self, task_id: str) -> KimiTask | None:
        async with self._lock:
            return self._tasks.get(task_id)

    async def _update_task(self, task_id: str, **kwargs) -> bool:
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            task.updated_at = datetime.now()
            return True
