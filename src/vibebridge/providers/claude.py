"""Claude Code provider implementation."""

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
class ClaudeTask:
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


class ClaudeProvider(BaseProvider):
    name = "claude"
    display_name = "Claude Code"

    def __init__(
        self,
        binary: str | None = None,
        default_workdir: str = "~/workspace",
    ):
        self.binary = binary or self._auto_detect_binary()
        self._default_workdir = os.path.expanduser(default_workdir)
        self._tasks: dict[str, ClaudeTask] = {}
        self._lock = asyncio.Lock()
        # Session continuity: workdir -> session_id
        self._session_mapping: dict[str, str] = {}

    def _auto_detect_binary(self) -> str:
        if env := os.getenv("CLAUDE_BINARY"):
            return env
        if path := shutil.which("claude"):
            return path
        home = Path.home()
        candidates = [
            home / ".nvm/versions/node/v24.14.0/bin/claude",
            home / ".nvm/versions/node/v22.14.0/bin/claude",
            home / ".nvm/versions/node/v20.11.0/bin/claude",
            home / ".local/bin/claude",
            home / ".npm-global/bin/claude",
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        raise FileNotFoundError(
            "Claude Code CLI not found. Please install claude-code or set CLAUDE_BINARY."
        )

    async def health_check(self) -> tuple[bool, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                self.binary,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            if proc.returncode == 0:
                return True, f"Claude Code {stdout.decode().strip()}"
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

        task_id = f"claude_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{session_id[-8:]}"
        task = ClaudeTask(
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
            content="正在启动 Claude Code...",
            task_id=task_id,
        )

        process: asyncio.subprocess.Process | None = None
        try:
            # Session continuity
            wd = task.workdir
            session_args = []
            if wd in self._session_mapping:
                session_args = ["-c"]  # --continue: reuse latest session in cwd

            cmd = [
                self.binary,
                "-p",
                "--output-format",
                "stream-json",
                "--dangerously-skip-permissions",
                "--verbose",
                *session_args,
                task.user_message,
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=task.workdir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env={**os.environ, "CLAUDE_CODE_DISABLE_AUTOCOMPACT": "true"},
            )
            await self._update_task(task_id, process=process)

            buffer = ""
            stdout = process.stdout
            final_result: str | None = None
            has_error = False
            total_deadline = asyncio.get_event_loop().time() + 1200  # 20 min total

            if stdout is None:
                raise RuntimeError("Subprocess stdout is None")

            while True:
                remaining = total_deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    raise asyncio.TimeoutError("Total execution time exceeded 1200s")

                try:
                    chunk = await asyncio.wait_for(stdout.read(1024), timeout=min(60.0, remaining))
                    if not chunk:
                        break
                    buffer += chunk.decode("utf-8", errors="replace")

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue

                        try:
                            event = json.loads(line)
                            event_type = event.get("type", "")

                            if event_type == "system":
                                subtype = event.get("subtype", "")
                                if subtype == "init":
                                    sid = event.get("session_id", "")
                                    if sid:
                                        self._session_mapping[wd] = sid

                            elif event_type == "assistant":
                                msg = event.get("message", {})
                                content = msg.get("content", [])
                                for part in content:
                                    ptype = part.get("type", "")
                                    if ptype == "text":
                                        text = part.get("text", "")
                                        if text:
                                            task.output_lines.append(text)
                                            yield StreamEvent(
                                                type=StreamEventType.TEXT,
                                                content=text,
                                                task_id=task_id,
                                            )
                                # Check for tool_use inside message (if present)
                                tool_use = msg.get("tool_use") or msg.get("tool_calls")
                                if tool_use:
                                    if isinstance(tool_use, list):
                                        for tu in tool_use:
                                            name = tu.get("name", "unknown")
                                            yield StreamEvent(
                                                type=StreamEventType.TOOL_USE,
                                                content=f"🛠️ {name}",
                                                task_id=task_id,
                                            )
                                    elif isinstance(tool_use, dict):
                                        name = tool_use.get("name", "unknown")
                                        yield StreamEvent(
                                            type=StreamEventType.TOOL_USE,
                                            content=f"🛠️ {name}",
                                            task_id=task_id,
                                        )

                                # Detect API errors embedded in assistant message
                                error_field = event.get("error", "")
                                if error_field:
                                    has_error = True
                                    # Extract error text from content
                                    for part in content:
                                        if part.get("type") == "text":
                                            err_text = part.get("text", "")
                                            if err_text and not task.error:
                                                task.error = err_text

                            elif event_type == "tool_use":
                                name = event.get("name", "unknown")
                                yield StreamEvent(
                                    type=StreamEventType.TOOL_USE,
                                    content=f"🛠️ {name}",
                                    task_id=task_id,
                                )

                            elif event_type == "result":
                                is_error = event.get("is_error", False)
                                result_text = event.get("result", "")
                                if is_error:
                                    has_error = True
                                    if result_text:
                                        task.error = result_text
                                else:
                                    final_result = result_text
                                    task.final_result = result_text

                        except json.JSONDecodeError:
                            pass

                except asyncio.TimeoutError:
                    if process.returncode is not None:
                        break
                    yield StreamEvent(
                        type=StreamEventType.STATUS,
                        content="⏳ Claude Code 仍在运行，等待输出中...",
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
                task.error = "Claude Code process did not exit in time after output ended"

            if process.returncode == 0 and not has_error:
                if final_result:
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
                    error_msg = task.error or "Claude Code exited with no output"
                    await self._update_task(
                        task_id, status=TaskStatus.FAILED, error=error_msg
                    )
                    yield StreamEvent(
                        type=StreamEventType.ERROR,
                        content=error_msg,
                        task_id=task_id,
                    )
            else:
                error_msg = task.error or f"Claude Code exited with code {process.returncode}"
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
            error_msg = "Claude Code CLI 未找到，请确保已安装 claude-code"
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

    async def _get_task(self, task_id: str) -> ClaudeTask | None:
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
