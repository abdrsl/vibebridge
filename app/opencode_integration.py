import asyncio
import json
import os
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import AsyncGenerator, Optional

import httpx

# Optional skill integration
try:
    from skills.skill_manager import get_skill_manager

    SKILLS_AVAILABLE = True
except ImportError:
    SKILLS_AVAILABLE = False

    # Create a dummy function that raises ImportError when called
    def get_skill_manager():  # type: ignore
        raise ImportError("Skills module not available")


PROJECT_ROOT = Path(__file__).parent.parent


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class OpenCodeTask:
    task_id: str
    user_message: str
    status: TaskStatus = TaskStatus.PENDING
    session_id: str | None = None
    process: subprocess.Popen | None = None
    output_lines: list[str] = field(default_factory=list)
    final_result: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    feishu_chat_id: str | None = None
    feishu_message_id: str | None = None


class OpenCodeManager:
    def __init__(self):
        self.tasks: dict[str, OpenCodeTask] = {}
        self._lock = asyncio.Lock()

    async def create_task(
        self,
        user_message: str,
        feishu_chat_id: str | None = None,
        feishu_message_id: str | None = None,
        check_constitution: bool = True,
        generate_session_name: bool = True,
    ) -> str:
        task_id = (
            f"oc_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        )

        session_id = None

        # Apply skills if available and requested
        if SKILLS_AVAILABLE and (check_constitution or generate_session_name):
            try:
                skill_manager = get_skill_manager()

                # Check constitution if requested
                if check_constitution:
                    constitution_result = skill_manager.check_constitution(user_message)
                    if constitution_result.get("has_violations", False):
                        # Log violation but don't block (for now)
                        print(
                            f"[Security] Constitutional violation detected in task {task_id}"
                        )
                        for violation in constitution_result.get("violations", []):
                            print(
                                f"  - {violation.get('message', 'Unknown violation')}"
                            )

                # Generate session name if requested
                if generate_session_name:
                    session_id = skill_manager.generate_session_name(user_message)
                    print(f"[Skills] Generated session name: {session_id}")

            except Exception as e:
                print(f"[Skills] Error applying skills: {e}")
                # Continue without skills if they fail

        task = OpenCodeTask(
            task_id=task_id,
            user_message=user_message,
            session_id=session_id,
            feishu_chat_id=feishu_chat_id,
            feishu_message_id=feishu_message_id,
        )
        async with self._lock:
            self.tasks[task_id] = task
        return task_id

    async def get_task(self, task_id: str) -> OpenCodeTask | None:
        async with self._lock:
            return self.tasks.get(task_id)

    async def update_task(self, task_id: str, **kwargs) -> bool:
        async with self._lock:
            if task_id not in self.tasks:
                return False
            task = self.tasks[task_id]
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            task.updated_at = datetime.now()
            return True

    async def run_opencode(self, task_id: str) -> AsyncGenerator[dict, None]:
        task = await self.get_task(task_id)
        if not task:
            yield {"type": "error", "content": f"Task {task_id} not found"}
            return

        await self.update_task(task_id, status=TaskStatus.RUNNING)
        yield {
            "type": "status",
            "content": "正在启动 OpenCode...",
            "task_id": task_id,
        }

        try:
            cmd = [
                "opencode",
                "run",
                "--format",
                "json",
                "--model",
                "deepseek/deepseek-chat",
                "--title",
                f"Feishu Task {task_id}",
                task.user_message,
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(PROJECT_ROOT),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env={**os.environ, "OPENCODE_DISABLE_AUTOCOMPACT": "true"},
            )

            await self.update_task(task_id, process=process)

            buffer = ""
            stdout = process.stdout
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

                            if event_type == "step_start":
                                snapshot = event.get("snapshot", "")[:50]
                                yield {
                                    "type": "status",
                                    "content": f"🔄 开始执行步骤...",
                                }

                            elif event_type == "tool_use":
                                part = event.get("part", {})
                                state = part.get("state", {})
                                tool = state.get("title", part.get("tool", "unknown"))
                                input_data = state.get("input", {})
                                if isinstance(input_data, dict):
                                    desc = input_data.get("description", "")
                                    cmd = input_data.get("command", "")
                                    if cmd:
                                        display = f"🛠️ {tool}: {cmd[:100]}..."
                                    else:
                                        display = f"🛠️ {tool}: {desc[:100]}"
                                else:
                                    display = f"🛠️ {tool}: {str(input_data)[:100]}"
                                task.output_lines.append(display)
                                yield {
                                    "type": "tool",
                                    "content": display,
                                    "detail": state,
                                }

                            elif event_type == "text":
                                part = event.get("part", {})
                                text = part.get("text", "")
                                if text:
                                    task.output_lines.append(text)
                                    yield {"type": "output", "content": text}

                            elif event_type == "step_finish":
                                reason = event.get("part", {}).get("reason", "")
                                tokens = event.get("part", {}).get("tokens", {})
                                cost = event.get("part", {}).get("cost", 0)
                                yield {
                                    "type": "status",
                                    "content": f"✅ 步骤完成 ({reason})",
                                }

                            elif event_type == "error":
                                yield {
                                    "type": "error",
                                    "content": event.get("message", "Unknown error"),
                                }

                            elif event_type == "done":
                                final_content = event.get("content", {})
                                if isinstance(final_content, dict):
                                    final_text = final_content.get(
                                        "text", str(final_content)
                                    )
                                else:
                                    final_text = str(final_content)
                                task.final_result = final_text
                                yield {"type": "done", "content": final_text}

                            else:
                                part = event.get("part", {})
                                if part:
                                    text = part.get("text", "")
                                    if text:
                                        task.output_lines.append(text)
                                        yield {"type": "output", "content": text}

                        except json.JSONDecodeError:
                            pass

                except asyncio.TimeoutError:
                    if process.returncode is not None:
                        break

            await process.wait()

            if process.returncode == 0:
                await self.update_task(task_id, status=TaskStatus.COMPLETED)
                yield {"type": "status", "content": "任务完成", "task_id": task_id}
            else:
                await self.update_task(
                    task_id,
                    status=TaskStatus.FAILED,
                    error=f"OpenCode exited with code {process.returncode}",
                )
                yield {
                    "type": "error",
                    "content": f"任务失败，退出码: {process.returncode}",
                }

        except FileNotFoundError:
            error_msg = "OpenCode CLI 未找到，请确保已安装 opencode"
            await self.update_task(task_id, status=TaskStatus.FAILED, error=error_msg)
            yield {"type": "error", "content": error_msg}

        except Exception as e:
            error_msg = f"执行出错: {str(e)}"
            await self.update_task(task_id, status=TaskStatus.FAILED, error=error_msg)
            yield {"type": "error", "content": error_msg}

    async def list_tasks(self, limit: int = 20) -> list[dict]:
        tasks = sorted(self.tasks.values(), key=lambda t: t.created_at, reverse=True)[
            :limit
        ]
        return [
            {
                "task_id": t.task_id,
                "status": t.status.value,
                "user_message": t.user_message,
                "created_at": t.created_at.isoformat(),
                "output_count": len(t.output_lines),
                "has_result": t.final_result is not None,
            }
            for t in tasks
        ]


opencode_manager = OpenCodeManager()
