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
from ..constitution_guard import is_dangerous_command, format_auth_prompt


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
    session_id: str = ""
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
        model: str = "deepseek/deepseek-reasoner",
        default_workdir: str = "~/workspace",
    ):
        self.binary = binary or self._auto_detect_binary()
        self.model = model
        self._default_workdir = os.path.expanduser(default_workdir)
        self._tasks: dict[str, OpenCodeTask] = {}
        self._lock = asyncio.Lock()
        self._authorized_operations: dict[str, list[str]] = {}
        self._session_mapping: dict[str, str] = {}

    def authorize(self, session_id: str, operation: str) -> None:
        """Authorize a dangerous operation for a session."""
        ops = self._authorized_operations.setdefault(session_id, [])
        op = operation.strip()
        if op and op not in ops:
            ops.append(op)

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

    def default_workdir(self) -> str:
        return self._default_workdir

    async def create_task(
        self,
        prompt: str,
        workdir: str,
        session_id: str,
        chat_id: str | None = None,
    ) -> str:
        # Ensure workdir exists
        wd = Path(workdir).expanduser()
        try:
            wd.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            # If custom workdir fails, fallback to default
            wd = Path(self._default_workdir)
            try:
                wd.mkdir(parents=True, exist_ok=True)
            except Exception as e2:
                raise RuntimeError(
                    f"Cannot create workdir {workdir} or fallback {self._default_workdir}: {e2}"
                ) from e2

        task_id = f"oc_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{session_id[-8:]}"
        task = OpenCodeTask(
            task_id=task_id,
            user_message=prompt,
            workdir=str(wd),
            session_id=session_id,
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

        process: asyncio.subprocess.Process | None = None
        try:
            # v2026: Session continuity — map VibeBridge session_id to OpenCode session
            # OpenCode requires --session to reference an EXISTING session;
            # passing a non-existent session ID causes "Session not found" (exit code 1).
            # Strategy:
            #   - First call for a vibebridge session: run WITHOUT --session so OpenCode
            #     auto-creates one. We extract the sessionID from the first JSON event.
            #   - Subsequent calls: use --session <id> --continue to resume context.
            session_mapping: dict[str, str] = getattr(self, "_session_mapping", {})
            oc_session = session_mapping.get(task.session_id)
            if oc_session:
                # Continue existing OpenCode session
                session_args = ["--session", oc_session, "--continue"]
            else:
                # First call: let OpenCode create the session; we'll capture its ID
                session_args = []

            cmd = [
                self.binary,
                "run",
                "--format",
                "json",
                "--model",
                self.model,
                "--dangerously-skip-permissions",  # 自动批准权限，避免手动确认
                "--title",
                f"VibeBridge Task {task_id}",
                *session_args,
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
            total_deadline = asyncio.get_event_loop().time() + 1200  # 20 min total
            # Collect non-JSON stderr/stdout lines for diagnostics
            non_json_lines: list[str] = []

            if stdout is None:
                raise RuntimeError("Subprocess stdout is None")

            while True:
                # Global deadline guard
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

                            # Capture OpenCode session ID on first event (step_start)
                            if not oc_session and event_type == "step_start":
                                sid = event.get("sessionID", "")
                                if not sid:
                                    sid = event.get("part", {}).get("sessionID", "")
                                if sid:
                                    oc_session = sid
                                    session_mapping[task.session_id] = sid
                                    self._session_mapping = session_mapping

                            if event_type == "tool_use":
                                part = event.get("part", {})
                                state = part.get("state", {})
                                tool = state.get("title", part.get("tool", "unknown"))
                                input_data = state.get("input", {})
                                if isinstance(input_data, dict):
                                    desc = input_data.get("description", "")
                                    command = input_data.get("command", "")
                                    if command:
                                        display = f"🛠️ {tool}: {command[:300]}"
                                    else:
                                        display = f"🛠️ {tool}: {desc[:300]}"
                                else:
                                    display = f"🛠️ {tool}: {str(input_data)[:300]}"

                                # ── Constitutional Guard: intercept dangerous commands ──
                                cmd_to_check = command if command else desc
                                is_danger, danger_desc = is_dangerous_command(cmd_to_check)
                                if is_danger:
                                    auth_ops = self._authorized_operations.get(task.session_id, [])
                                    authorized = False
                                    for auth in auth_ops:
                                        if auth in cmd_to_check or cmd_to_check in auth:
                                            authorized = True
                                            break
                                    if not authorized:
                                        # Kill the subprocess immediately
                                        if process and process.returncode is None:
                                            try:
                                                process.kill()
                                                await process.wait()
                                            except Exception:
                                                pass
                                        auth_msg = format_auth_prompt(cmd_to_check, danger_desc)
                                        task.error = auth_msg
                                        yield StreamEvent(
                                            type=StreamEventType.ERROR,
                                            content=auth_msg,
                                            task_id=task_id,
                                        )
                                        return  # Stop streaming

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
                                # Try multiple fields for a meaningful error message
                                error_msg = event.get("message", "")
                                if not error_msg:
                                    error_msg = event.get("error", "")
                                if not error_msg:
                                    part = event.get("part", {})
                                    error_msg = part.get("message", "") if isinstance(part, dict) else ""
                                if not error_msg:
                                    error_msg = "OpenCode 返回错误，未提供具体信息"
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
                                    final_text = final_content.get("text", str(final_content))
                                else:
                                    final_text = str(final_content)
                                final_result = final_text
                                task.final_result = final_text

                        except json.JSONDecodeError:
                            # Keep non-JSON output for later error diagnostics
                            non_json_lines.append(line)
                            pass

                except asyncio.TimeoutError:
                    if process.returncode is not None:
                        break
                    # If process is still running but silent for 60s, yield a heartbeat
                    yield StreamEvent(
                        type=StreamEventType.STATUS,
                        content="⏳ OpenCode 仍在运行，等待输出中...",
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
                task.error = "OpenCode process did not exit in time after output ended"

            # Build a diagnostic message from non-JSON stderr/stdout output
            diagnostic = ""
            if non_json_lines:
                combined = " ".join(non_json_lines)
                # Detect known error patterns from opencode logs
                if "Insufficient Balance" in combined:
                    diagnostic = "DeepSeek API 余额不足，请充值后重试"
                elif "AI_APICallError" in combined:
                    # Try to extract the actual error from the log line
                    for line in non_json_lines:
                        if "error=" in line:
                            import re as _re
                            m = _re.search(r'error=\{.*?"error"\s*:\s*\{.*?"message"\s*:\s*"([^"]+)"', line)
                            if m:
                                diagnostic = f"API 调用错误: {m.group(1)}"
                                break
                    if not diagnostic:
                        diagnostic = "API 调用失败（可能是密钥无效或网络问题）"
                elif "ECONNREFUSED" in combined or "connect" in combined.lower():
                    diagnostic = "网络连接失败，无法连接到 API 服务器"
                elif "timeout" in combined.lower():
                    diagnostic = "API 请求超时"
                else:
                    # Keep the last few non-JSON lines as hint
                    diagnostic = "OpenCode 输出解析失败: " + " | ".join(non_json_lines[-3:])

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
                        if not diagnostic:
                            diagnostic = (
                                "OpenCode 在 headless 模式下未返回任何文本内容。"
                                "这是 OpenCode v1.16.x 的已知限制。"
                                "建议切换到 Kimi 或 Claude provider：发送 /kimi 或 /claude"
                            )
                        error_msg = task.error or diagnostic
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
                error_msg = task.error or diagnostic or f"OpenCode 进程异常退出（退出码 {process.returncode}）"
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
