import asyncio
import json
import os
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import AsyncGenerator, List

# Optional skill integration
SKILLS_AVAILABLE = False
get_skill_manager = None
OPENCODE_SKILLS_AVAILABLE = False
get_opencode_skill_manager = None

# Try to load OpenCode-style skills from workspace/.skills/
try:
    from .opencode_skill_manager import (
        get_opencode_skill_manager as _get_opencode_skill_manager,
    )

    get_opencode_skill_manager = _get_opencode_skill_manager
    OPENCODE_SKILLS_AVAILABLE = True
    SKILLS_AVAILABLE = True
    print("[Skills] OpenCode skill manager loaded")
except ImportError as e:
    print(f"[Skills] OpenCode skill manager not available: {e}")

# Fallback to Python skill manager
if not OPENCODE_SKILLS_AVAILABLE:
    try:
        from skills.skill_manager import get_skill_manager as _get_skill_manager

        get_skill_manager = _get_skill_manager
        SKILLS_AVAILABLE = True
        print("[Skills] Python skill manager loaded (fallback)")
    except ImportError:
        print("[Skills] No skill managers available")

# Fallback to simple skill manager
if not SKILLS_AVAILABLE:
    try:
        from .simple_skill_manager import (
            get_simple_skill_manager as _get_simple_skill_manager,
        )

        get_simple_skill_manager = _get_simple_skill_manager
        SKILLS_AVAILABLE = True
        print("[Skills] Simple skill manager loaded (fallback)")
    except ImportError as e:
        print(f"[Skills] Simple skill manager not available: {e}")


PROJECT_ROOT = Path(__file__).parent.parent


def filter_final_output(output_lines: list[str]) -> str:
    """过滤输出行，移除工具调用行和中间过程，返回最终结果"""
    filtered_lines = []
    skip_patterns = [
        # 工具调用行
        "🛠️",
        # 中间过程描述
        "我将",
        "正在",
        "首先",
        "接下来",
        "然后",
        "最后",
        "开始",
        "继续",
        "接着",
        "现在",
        "正在启动",
        "正在解析",
        "正在分析",
        "正在执行",
        "正在处理",
        "正在搜索",
        "正在查找",
        "正在检查",
        "正在验证",
        "正在读取",
        "正在写入",
        "正在更新",
        "正在创建",
        "正在删除",
        "正在修改",
        "正在优化",
        "正在整理",
        "正在清理",
        "正在计算",
        "正在统计",
        "正在汇总",
        "正在生成",
        "正在构建",
        "正在编译",
        "正在安装",
        "正在配置",
        "正在初始化",
        "正在准备",
        "正在等待",
        "正在连接",
        "正在发送",
        "正在接收",
        "正在加载",
        "正在保存",
        "正在导出",
        "正在导入",
        "正在备份",
        "正在恢复",
        "正在重启",
        "正在停止",
        "正在启动",
        "正在运行",
        "正在测试",
        "正在调试",
        "正在评估",
        "正在比较",
        "正在合并",
        "正在分割",
        "正在转换",
        "正在格式化",
        "正在排序",
        "正在过滤",
        "正在提取",
        "正在压缩",
        "正在解压",
        "正在加密",
        "正在解密",
        # 其他常见中间行
        "---",
        "====",
        "####",
        "****",
        ">>>>",
        "<<<<",
        "~~~~",
        "....",
        "......",
    ]

    for line in output_lines:
        line_stripped = line.strip()

        # 跳过空行
        if not line_stripped:
            continue

        # 检查是否匹配跳过模式
        skip = False
        for pattern in skip_patterns:
            if line_stripped.startswith(pattern):
                skip = True
                break
            if pattern in line_stripped and len(line_stripped) < 100:  # 短行中包含模式
                skip = True
                break

        # 跳过思考/分析/执行等前缀
        if (
            line_stripped.startswith("[思考]")
            or line_stripped.startswith("[分析]")
            or line_stripped.startswith("[执行]")
            or line_stripped.startswith("[步骤]")
        ):
            skip = True

        # 跳过以表情符号开头后接中文动词的行
        if any(
            line_stripped.startswith(emoji)
            for emoji in [
                "🔍",
                "📊",
                "📝",
                "🔄",
                "⚙️",
                "🔧",
                "🔨",
                "🛠️",
                "🚀",
                "✅",
                "❌",
                "⚠️",
                "ℹ️",
                "📌",
                "📍",
                "🔗",
                "📎",
                "📄",
                "📁",
                "📂",
                "📅",
                "📆",
                "📋",
                "📒",
                "📓",
                "📔",
                "📕",
                "📖",
                "📗",
                "📘",
                "📙",
                "📚",
                "📛",
                "📜",
                "📝",
            ]
        ):
            if any(
                word in line_stripped
                for word in ["正在", "将", "开始", "继续", "然后", "接下来", "最后"]
            ):
                skip = True

        if not skip:
            filtered_lines.append(line)

    # 如果过滤后没有内容，返回原始输出的最后有意义部分
    if not filtered_lines:
        # 返回最后10行非空行
        non_empty = [line for line in output_lines if line.strip()]
        return "\n".join(non_empty[-10:]) if non_empty else "无输出"

    return "\n".join(filtered_lines)


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
    generated_files: List[str] = field(default_factory=list)  # 生成的文件路径列表


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
        task_id = f"oc_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        session_id = None

        # Apply skills if available and requested
        if SKILLS_AVAILABLE and (check_constitution or generate_session_name):
            try:
                # Try OpenCode skill manager first if available
                if OPENCODE_SKILLS_AVAILABLE and get_opencode_skill_manager:
                    skill_manager = get_opencode_skill_manager()
                    manager_type = "OpenCode"
                elif get_skill_manager:
                    skill_manager = get_skill_manager()
                    manager_type = "Python"
                elif get_simple_skill_manager:
                    skill_manager = get_simple_skill_manager()
                    manager_type = "Simple"
                else:
                    skill_manager = None
                    manager_type = None

                if skill_manager:
                    print(f"[Skills] Using {manager_type} skill manager")

                    # Check constitution if requested
                    if check_constitution:
                        constitution_result = skill_manager.check_constitution(user_message)
                        if constitution_result.get("has_violations", False):
                            # Log violation but don't block (for now)
                            print(f"[Security] Constitutional violation detected in task {task_id}")
                            for violation in constitution_result.get("violations", []):
                                print(f"  - {violation.get('message', 'Unknown violation')}")

                    # Generate session name if requested
                    if generate_session_name:
                        session_id = skill_manager.generate_session_name(user_message)
                        print(f"[Skills] Generated session name: {session_id}")
                else:
                    print("[Skills] No skill manager available")

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
            # 使用绝对路径确保找到 opencode
            opencode_path = "/home/user/.nvm/versions/node/v24.14.0/bin/opencode"
            cmd = [
                opencode_path,
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
            final_result = None
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
                                    cmd = input_data.get("command", "")
                                    if cmd:
                                        display = f"🛠️ {tool}: {cmd[:100]}..."
                                    else:
                                        display = f"🛠️ {tool}: {desc[:100]}"
                                else:
                                    display = f"🛠️ {tool}: {str(input_data)[:100]}"
                                task.output_lines.append(display)
                                yield {"type": "tool_use", "content": display}

                            elif event_type == "text":
                                part = event.get("part", {})
                                text = part.get("text", "")
                                if text:
                                    task.output_lines.append(text)
                                    yield {"type": "text", "content": text}

                            elif event_type == "error":
                                error_msg = event.get("message", "Unknown error")
                                has_error = True
                                task.error = error_msg
                                yield {"type": "error", "content": error_msg}

                            elif event_type == "done":
                                final_content = event.get("content", {})
                                if isinstance(final_content, dict):
                                    final_text = final_content.get("text", str(final_content))
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
                    await self.update_task(task_id, status=TaskStatus.COMPLETED)
                    yield {"type": "done", "content": final_result}
                else:
                    # 如果没有收到done事件但有输出，使用输出作为结果
                    if task.output_lines and not has_error:
                        # 收集所有输出作为结果，过滤掉工具调用行
                        final_result = filter_final_output(task.output_lines)
                        task.final_result = final_result
                        await self.update_task(task_id, status=TaskStatus.COMPLETED)
                        yield {"type": "done", "content": final_result}
                    else:
                        error_msg = task.error or f"OpenCode exited with code {process.returncode}"
                        await self.update_task(
                            task_id,
                            status=TaskStatus.FAILED,
                            error=error_msg,
                        )
                        yield {"type": "error", "content": error_msg}
            else:
                error_msg = task.error or f"OpenCode exited with code {process.returncode}"
                await self.update_task(
                    task_id,
                    status=TaskStatus.FAILED,
                    error=error_msg,
                )
                yield {"type": "error", "content": error_msg}

        except FileNotFoundError:
            error_msg = "OpenCode CLI 未找到，请确保已安装 opencode"
            await self.update_task(task_id, status=TaskStatus.FAILED, error=error_msg)
            yield {"type": "error", "content": error_msg}

        except Exception as e:
            error_msg = f"执行出错: {str(e)}"
            await self.update_task(task_id, status=TaskStatus.FAILED, error=error_msg)
            yield {"type": "error", "content": error_msg}

    async def list_tasks(self, limit: int = 20) -> list[dict]:
        tasks = sorted(self.tasks.values(), key=lambda t: t.created_at, reverse=True)[:limit]
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

    async def cancel_task(self, task_id: str) -> bool:
        async with self._lock:
            task = self.tasks.get(task_id)
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


opencode_manager = OpenCodeManager()
