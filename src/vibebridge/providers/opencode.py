"""OpenCode provider implementation."""

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
class OpenCodeTask:
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


class OpenCodeProvider(BaseProvider):
    name = "opencode"
    display_name = "OpenCode"

    def __init__(
        self,
        binary: str | None = None,
        model: str = "deepseek/deepseek-chat",
        default_workdir: str = "~/workspace",
    ):
        self.binary = binary or self._auto_detect_binary()
        self.model = model
        self._default_workdir = os.path.expanduser(default_workdir)
        self._tasks: dict[str, OpenCodeTask] = {}
        self._lock = asyncio.Lock()

    def _auto_detect_binary(self) -> str:
        if env := os.getenv("OPENCODE_BINARY"):
            return env
        if path := shutil.which("opencode"):
            return path
        home = Path.home()
        candidates = [
            home / ".nvm/versions/node/v24.14.0/bin/opencode",
            home / ".nvm/versions/node/v22.14.0/bin/opencode",
            home / ".nvm/versions/node/v20.11.0/bin/opencode",
            home / ".local/bin/opencode",
            home / ".npm-global/bin/opencode",
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        raise FileNotFoundError(
            "OpenCode CLI not found. Please install opencode or set OPENCODE_BINARY."
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
                return True, f"OpenCode {stdout.decode().strip()}"
            return False, f"Error: {stderr.decode().strip()}"
        except Exception as e:
            return False, str(e)

    async def create_task(
        self,
        prompt: str,
        workdir: str,
        session_id: str,
        chat_id: str | None = None,
    ) -> str:
        task_id = (
            f"oc_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{session_id[-8:]}"
        )
        task = OpenCodeTask(
            task_id=task_id,
            user_message=prompt,
            workdir=workdir or self._default_workdir,
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
            content="正在启动 OpenCode...",
            task_id=task_id,
        )

        try:
            cmd = [
                self.binary,
                "run",
                "--format",
                "json",
                "--model",
                self.model,
                "--title",
                f"VibeBridge Task {task_id}",
                task.user_message,
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=task.workdir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env={**os.environ, "OPENCODE_DISABLE_AUTOCOMPACT": "true"},
            )
            await self._update_task(task_id, process=process)

            buffer = ""
            stdout = process.stdout
            final_result: str | None = None
            has_error = False

            while True:
                try:
                    assert stdout is not None
                    chunk = await asyncio.wait_for(stdout.read(1024), timeout=60.0)
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

                            if event_type == "tool_use":
                                part = event.get("part", {})
                                state = part.get("state", {})
                                tool = state.get("title", part.get("tool", "unknown"))
                                input_data = state.get("input", {})
                                if isinstance(input_data, dict):
                                    desc = input_data.get("description", "")
                                    command = input_data.get("command", "")
                                    if command:
                                        display = f"🛠️ {tool}: {command[:100]}..."
                                    else:
                                        display = f"🛠️ {tool}: {desc[:100]}"
                                else:
                                    display = f"🛠️ {tool}: {str(input_data)[:100]}"
                                task.output_lines.append(display)
                                yield StreamEvent(
                                    type=StreamEventType.TOOL_USE,
                                    content=display,
                                    task_id=task_id,
                                )

                            elif event_type == "text":
                                part = event.get("part", {})
                                text = part.get("text", "")
                                if text:
                                    task.output_lines.append(text)
                                    yield StreamEvent(
                                        type=StreamEventType.TEXT,
                                        content=text,
                                        task_id=task_id,
                                    )

                            elif event_type == "error":
                                error_msg = event.get("message", "Unknown error")
                                has_error = True
                                task.error = error_msg
                                yield StreamEvent(
                                    type=StreamEventType.ERROR,
                                    content=error_msg,
                                    task_id=task_id,
                                )

                            elif event_type == "done":
                                final_content = event.get("content", {})
                                if isinstance(final_content, dict):
                                    final_text = final_content.get(
                                        "text", str(final_content)
                                    )
                                else:
                                    final_text = str(final_content)
                                final_result = final_text
                                task.final_result = final_text

                        except json.JSONDecodeError:
                            pass

                except asyncio.TimeoutError:
                    if process.returncode is not None:
                        break

            await process.wait()

            if process.returncode == 0:
                if final_result and not has_error:
                    await self._update_task(task_id, status=TaskStatus.COMPLETED)
                    yield StreamEvent(
                        type=StreamEventType.DONE,
                        content=final_result,
                        task_id=task_id,
                    )
                else:
                    if task.output_lines and not has_error:
                        final_result = "\n".join(task.output_lines)
                        task.final_result = final_result
                        await self._update_task(task_id, status=TaskStatus.COMPLETED)
                        yield StreamEvent(
                            type=StreamEventType.DONE,
                            content=final_result,
                            task_id=task_id,
                        )
                    else:
                        error_msg = (
                            task.error
                            or f"OpenCode exited with code {process.returncode}"
                        )
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
            else:
                error_msg = (
                    task.error or f"OpenCode exited with code {process.returncode}"
                )
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
            error_msg = "OpenCode CLI 未找到，请确保已安装 opencode"
            await self._update_task(task_id, status=TaskStatus.FAILED, error=error_msg)
            yield StreamEvent(
                type=StreamEventType.ERROR,
                content=error_msg,
                task_id=task_id,
            )
        except Exception as e:
            error_msg = f"执行出错: {str(e)}"
            await self._update_task(task_id, status=TaskStatus.FAILED, error=error_msg)
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
                task.process.terminate()
                try:
                    await asyncio.wait_for(task.process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    task.process.kill()
                    await task.process.wait()
            task.status = TaskStatus.CANCELLED
            task.updated_at = datetime.now()
            return True

    def default_workdir(self) -> str:
        return self._default_workdir

    async def _get_task(self, task_id: str) -> OpenCodeTask | None:
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
