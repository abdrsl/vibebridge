"""
自定义指令处理器
处理用户定义的快捷指令
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from .config_manager import get_config_manager


class CommandProcessor:
    """自定义指令处理器"""

    def __init__(self, config_path=None):
        """
        初始化指令处理器

        Args:
            config_path: 配置文件路径，默认使用项目目录下的config/commands.json
        """
        if config_path is None:
            # 默认配置文件路径
            project_dir = Path(__file__).parent.parent.parent
            config_path = project_dir / "config" / "commands.json"

        self.config_path: Path = Path(config_path) if config_path else Path(".")
        self.commands = {}
        self.models = {}
        self.load_config()

    def load_config(self):
        """加载配置文件"""
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.commands = config.get("commands", {})
                    self.models = config.get("models", {})
                print(
                    f"[Commands] Loaded {len(self.commands)} commands "
                    f"from {self.config_path}"
                )
            else:
                print(f"[Commands] Config file not found: {self.config_path}")
                self._create_default_config()
        except Exception as e:
            print(f"[Commands] Error loading config: {e}")
            self._create_default_config()

    def _create_default_config(self):
        """创建默认配置"""
        self.commands = {
            "清空session": {
                "action": "clear_session",
                "description": "清空当前会话",
                "confirm": False,
                "response": "✅ 当前会话已清空",
            }
        }
        self.models = {}

    def save_config(self):
        """保存配置到文件"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            config = {
                "version": "1.0",
                "description": "OpenCode-Feishu Bridge 自定义指令配置",
                "commands": self.commands,
                "models": self.models,
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[Commands] Error saving config: {e}")
            return False

    def match_command(self, text: str) -> Optional[Dict[str, Any]]:
        """
        匹配指令

        Args:
            text: 用户输入的文本

        Returns:
            匹配的指令配置或None
        """
        text_lower = text.lower().strip()

        for cmd_name, cmd_config in self.commands.items():
            if text_lower == cmd_name.lower():
                return cmd_config

        return None

    async def execute_command(
        self, cmd_config: Dict[str, Any], chat_id: str, user_id: str, **kwargs
    ) -> Dict[str, Any]:
        """
        执行指令

        Args:
            cmd_config: 指令配置
            chat_id: 聊天ID
            user_id: 用户ID
            **kwargs: 其他参数

        Returns:
            执行结果
        """
        action = cmd_config.get("action", "")
        background_tasks = kwargs.get("background_tasks")

        try:
            if action == "clear_session":
                return await self._clear_session(user_id, chat_id)
            elif action == "switch_model":
                model = cmd_config.get("model", "default")
                return await self._switch_model(user_id, model)
            elif action == "git_commit":
                return await self._git_commit(chat_id)
            elif action == "start_server":
                return await self._start_server(chat_id)
            elif action == "show_models":
                return await self._show_models()
            elif action == "greeting":
                return await self._greeting(chat_id, background_tasks)
            elif action == "switch_feishu_mode":
                mode = cmd_config.get("mode", "websocket")
                return await self._switch_feishu_mode(mode, chat_id, background_tasks)
            else:
                return {"ok": False, "error": f"Unknown action: {action}"}
        except Exception as e:
            print(f"[Commands] Error executing command: {e}")
            return {"ok": False, "error": str(e)}

    async def _clear_session(self, user_id: str, chat_id: str) -> Dict[str, Any]:
        """清空当前用户的会话"""
        from .session_manager import SessionStatus, get_session_manager

        session_manager = get_session_manager()

        # 查找并关闭用户的活跃会话
        sessions = await session_manager.list_sessions(chat_id=chat_id, user_id=user_id)

        cleared_count = 0
        for session_info in sessions:
            session_id = session_info.get("session_id")
            if session_id:
                await session_manager.close_session(session_id, SessionStatus.CANCELLED)
                cleared_count += 1

        return {
            "ok": True,
            "action": "clear_session",
            "cleared_count": cleared_count,
            "message": f"✅ 已清空 {cleared_count} 个活跃会话",
        }

    async def _switch_model(self, user_id: str, model_key: str) -> Dict[str, Any]:
        """切换模型"""
        model_config = self.models.get(model_key)
        if not model_config:
            return {"ok": False, "error": f"Model not found: {model_key}"}

        # 将当前模型保存到用户会话中
        from .session_manager import get_session_manager

        get_session_manager()

        # 这里我们创建一个特殊的系统消息来记录模型选择
        # 实际模型切换在LLM调用时根据这个配置进行
        return {
            "ok": True,
            "action": "switch_model",
            "model": model_key,
            "model_name": model_config.get("name", model_key),
            "message": f"🤖 已切换到 {model_config.get('name', model_key)} 模型",
        }

    async def _git_commit(self, chat_id: str) -> Dict[str, Any]:
        """执行Git提交 - 带实时CLI输出显示"""
        import asyncio

        from .feishu_client import feishu_client

        # 在后台执行Git提交
        async def do_git_commit():
            try:
                project_dir = Path(__file__).parent.parent

                # 发送开始消息 - 情感化
                await feishu_client.send_text_message(
                    chat_id, "🚀 **Git提交小分队出发！**\n准备将代码送上太空～"
                )
                await asyncio.sleep(0.3)

                # 执行Git命令，带实时输出
                date_str = (
                    subprocess.check_output(["date", "+%Y-%m-%d %H:%M:%S"])
                    .decode()
                    .strip()
                )
                commands = [
                    {"cmd": ["git", "add", "."], "name": "添加文件", "emoji": "📦"},
                    {"cmd": ["git", "status"], "name": "检查状态", "emoji": "🔍"},
                    {
                        "cmd": [
                            "git",
                            "commit",
                            "-m",
                            f"Update from Feishu bot - {date_str}",
                        ],
                        "name": "创建提交",
                        "emoji": "💾",
                    },
                    {"cmd": ["git", "push"], "name": "推送代码", "emoji": "🚀"},
                ]

                results = []
                for i, cmd_info in enumerate(commands):
                    cmd = cmd_info["cmd"]
                    step_name = cmd_info["name"]
                    emoji = cmd_info["emoji"]

                    # 发送步骤开始消息
                    await feishu_client.send_text_message(
                        chat_id,
                        f"{emoji} **步骤 {i + 1}/{len(commands)}: {step_name}**",
                    )
                    await asyncio.sleep(0.2)

                    # 执行命令，实时捕获输出
                    try:
                        # 使用Popen实时获取输出

                        process = subprocess.Popen(
                            cmd,
                            cwd=project_dir,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            bufsize=1,
                            universal_newlines=True,
                        )

                        # 实时读取输出
                        output_lines = []
                        while True:
                            # 检查标准输出
                            if process.stdout:
                                line = process.stdout.readline()
                                if line:
                                    output_lines.append(line.strip())
                                    # 实时发送重要输出（避免刷屏，只发送关键信息）
                                    if line.strip() and not line.strip().startswith(
                                        " "
                                    ):
                                        await feishu_client.send_text_message(
                                            chat_id, f"   📤 {line.strip()[:100]}"
                                        )

                            # 检查标准错误
                            if process.stderr:
                                err_line = process.stderr.readline()
                                if err_line:
                                    output_lines.append(f"STDERR: {err_line.strip()}")
                                    await feishu_client.send_text_message(
                                        chat_id, f"   ⚠️ {err_line.strip()[:100]}"
                                    )

                            # 检查进程是否结束
                            if process.poll() is not None:
                                # 读取剩余输出
                                remaining_stdout, remaining_stderr = (
                                    process.communicate()
                                )
                                if remaining_stdout:
                                    for line in remaining_stdout.strip().split("\n"):
                                        if line:
                                            output_lines.append(line.strip())
                                if remaining_stderr:
                                    for line in remaining_stderr.strip().split("\n"):
                                        if line:
                                            output_lines.append(
                                                f"STDERR: {line.strip()}"
                                            )
                                break

                            await asyncio.sleep(0.1)

                        returncode = process.returncode
                        stdout = "\n".join(
                            [
                                line
                                for line in output_lines
                                if not line.startswith("STDERR:")
                            ]
                        )
                        stderr = "\n".join(
                            [
                                line[8:]
                                for line in output_lines
                                if line.startswith("STDERR:")
                            ]
                        )

                    except Exception as cmd_error:
                        returncode = 1
                        stdout = ""
                        stderr = str(cmd_error)
                        await feishu_client.send_text_message(
                            chat_id, f"   ❌ 命令执行出错: {str(cmd_error)[:100]}"
                        )

                    results.append(
                        {
                            "command": " ".join(cmd),
                            "name": step_name,
                            "emoji": emoji,
                            "returncode": returncode,
                            "stdout": stdout[:500],
                            "stderr": stderr[:500],
                        }
                    )

                    # 发送步骤完成消息
                    if returncode == 0:
                        await feishu_client.send_text_message(
                            chat_id, f"   ✅ {step_name}完成！"
                        )
                    else:
                        await feishu_client.send_text_message(
                            chat_id, f"   ❌ {step_name}失败"
                        )

                    await asyncio.sleep(0.3)

                # 发送最终结果 - 情感化总结
                success = all(r["returncode"] == 0 for r in results)
                if success:
                    commit_message = "🎉 **Git提交大成功！**\n\n"
                    commit_message += "✅ **所有步骤完成：**\n"
                    for r in results:
                        commit_message += f"  {r['emoji']} {r['name']} ✓\n"

                    commit_message += "\n📊 **提交详情：**\n"
                    # 获取最新的提交信息
                    try:
                        latest_commit = subprocess.check_output(
                            ["git", "log", "-1", "--oneline"],
                            cwd=project_dir,
                            text=True,
                        ).strip()
                        commit_message += f"```\n{latest_commit}\n```"
                    except Exception:
                        commit_message += "（获取提交详情失败）"

                    await feishu_client.send_text_message(chat_id, commit_message)
                else:
                    error_count = sum(1 for r in results if r["returncode"] != 0)
                    error_message = (
                        f"😢 **Git提交遇到问题** "
                        f"({error_count}/{len(commands)} 失败)\n\n"
                    )

                    for r in results:
                        status = "✅" if r["returncode"] == 0 else "❌"
                        error_message += f"{status} {r['emoji']} {r['name']}\n"
                        if r["returncode"] != 0 and r["stderr"]:
                            error_message += f"   错误: {r['stderr'][:200]}\n"

                    error_message += "\n🔧 **建议检查：**\n"
                    error_message += "1. Git配置是否正确\n"
                    error_message += "2. 是否有未提交的冲突\n"
                    error_message += "3. 网络连接是否正常"

                    await feishu_client.send_text_message(chat_id, error_message)

            except Exception as e:
                await feishu_client.send_text_message(
                    chat_id, f"😱 **Git提交崩溃啦！**\n❌ 系统错误: {str(e)[:200]}"
                )

        # 启动后台任务
        asyncio.create_task(do_git_commit())

        return {
            "ok": True,
            "action": "git_commit",
            "message": "🤖 Git机器人已启动，正在准备提交代码，请稍候～",
        }

    async def _start_server(self, chat_id: str) -> Dict[str, Any]:
        """启动服务器 - 带情感化实时反馈"""
        import asyncio
        import time

        import httpx

        from .feishu_client import feishu_client

        async def check_server_running() -> bool:
            """检查服务器是否在运行"""
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get("http://127.0.0.1:8000/health")
                    return response.status_code == 200 and '{"ok":true' in response.text
            except Exception:
                return False

        async def wait_for_server_start(timeout: int = 30, interval: int = 2) -> bool:
            """等待服务器启动，带重试和进度反馈"""
            import time

            start_time = time.time()
            attempts = 0

            while time.time() - start_time < timeout:
                attempts += 1
                elapsed = time.time() - start_time

                # 每5秒发送一次等待状态（避免刷屏）
                if attempts % 3 == 1:
                    dots = "." * (attempts % 4)
                    await feishu_client.send_text_message(
                        chat_id, f"⏳ 等待服务器响应{dots} ({elapsed:.0f}s)"
                    )

                if await check_server_running():
                    return True
                await asyncio.sleep(interval)

            return False

        async def do_start_server():
            try:
                project_dir = Path(__file__).parent.parent

                # 检查服务器是否已在运行
                await feishu_client.send_text_message(
                    chat_id, "🔍 **服务器状态检查中...**"
                )
                await asyncio.sleep(0.3)

                if await check_server_running():
                    await feishu_client.send_text_message(
                        chat_id,
                        "😊 **服务器已经在运行啦！**\n\n"
                        "📍 **本地地址:** http://127.0.0.1:8000\n"
                        "🌐 **公网检查:** `./manage.sh status`\n"
                        "💡 想重启吗？先停止再启动哦～",
                    )
                    return

                # 开始启动服务器 - 情感化表达
                await feishu_client.send_text_message(
                    chat_id, "🚀 **服务器启动序列开始！**\n准备点火发射～"
                )
                await asyncio.sleep(0.5)

                # 步骤1: 激活环境
                await feishu_client.send_text_message(
                    chat_id, "1️⃣ **步骤1:** 激活Python虚拟环境..."
                )

                # 使用manage.sh启动服务器，确保虚拟环境正确
                await feishu_client.send_text_message(
                    chat_id, "2️⃣ **步骤2:** 启动UVicorn服务器..."
                )

                subprocess.Popen(
                    [
                        "bash",
                        "-c",
                        "cd /home/user/workspace/opencode-feishu-bridge && "
                        "source .venv/bin/activate && "
                        "python -m uvicorn src.main:app --host 0.0.0.0 --port 8000",
                    ],
                    cwd=project_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )

                # 等待服务器启动，带重试
                await feishu_client.send_text_message(
                    chat_id, "3️⃣ **步骤3:** 等待服务器就绪..."
                )

                start_time = time.time()
                if await wait_for_server_start(timeout=30, interval=2):
                    elapsed = time.time() - start_time
                    await feishu_client.send_text_message(
                        chat_id,
                        f"🎉 **服务器启动成功！** (耗时 {elapsed:.1f}s)\n\n"
                        "🏠 **本地访问:** http://127.0.0.1:8000\n"
                        "🌍 **公网隧道:** `./manage.sh tunnel`\n"
                        "📊 **状态检查:** `./manage.sh status`\n"
                        "💬 **健康检查:** http://127.0.0.1:8000/health",
                    )
                else:
                    await feishu_client.send_text_message(
                        chat_id,
                        "😢 **服务器启动失败**\n\n"
                        "🔧 **可能原因:**\n"
                        "1. 🐍 Python虚拟环境未激活\n"
                        "2. 🔌 端口8000被占用\n"
                        "3. 📜 依赖包缺失\n"
                        "4. 🌐 网络问题\n\n"
                        "🛠️ **解决方案:**\n"
                        "```bash\n"
                        "# 查看日志\n"
                        "tail -f logs/server.log\n\n"
                        "# 手动启动\n"
                        "./manage.sh start\n"
                        "```",
                    )

            except Exception as e:
                await feishu_client.send_text_message(
                    chat_id, f"😱 **启动过程崩溃！**\n❌ 系统错误: {str(e)[:200]}"
                )

        # 启动后台任务
        asyncio.create_task(do_start_server())

        return {
            "ok": True,
            "action": "start_server",
            "message": "🤖 服务器启动程序已激活，正在预热引擎，请稍候～",
        }

    async def _show_models(self) -> Dict[str, Any]:
        """显示可用模型"""
        if not self.models:
            return {"ok": True, "message": "🤖 当前没有配置任何模型"}

        model_list = []
        for model_key, model_config in self.models.items():
            name = model_config.get("name", model_key)
            provider = model_config.get("provider", "未知")
            model_id = model_config.get("model_id", "")
            env_var = model_config.get("api_key_env", "")
            has_key = bool(os.getenv(env_var)) if env_var else False
            status = "✅" if has_key else "⚠️"
            model_list.append(f"{status} **{name}** (`{model_key}`)")
            model_list.append(f"   - 供应商: {provider}")
            if model_id:
                model_list.append(f"   - 模型ID: {model_id}")
            model_list.append("")

        message = "🤖 **可用模型列表**\n\n" + "\n".join(model_list)
        return {"ok": True, "message": message}

    async def _greeting(self, chat_id: str, background_tasks=None) -> Dict[str, Any]:
        """打招呼"""
        from .feishu_client import feishu_client

        message = (
            "👋 你好！我是OpenCode助手，可以帮你完成开发任务。"
            "请发送你要完成的任务，比如：'帮我写一个Python函数' 或 '修复这个bug'"
        )

        # 直接发送消息，确保消息到达
        print(f"[Command] Greeting: sending message directly to {chat_id}")
        try:
            await feishu_client.send_text_message(chat_id, message)
            print("[Command] Greeting: message sent successfully")
            message_sent = True
        except Exception as e:
            print(f"[Command] Greeting: failed to send message: {e}")
            # 如果直接发送失败，尝试通过 background_tasks
            if background_tasks:
                print("[Command] Greeting: falling back to background_tasks")
                background_tasks.add_task(
                    feishu_client.send_text_message, chat_id, message
                )
                message_sent = True
            else:
                message_sent = False

        return {
            "ok": True,
            "action": "greeting",
            "message_sent": message_sent,
            "message": message,  # 保留消息内容供参考
        }

    async def _switch_feishu_mode(
        self, mode: str, chat_id: str, background_tasks=None
    ) -> Dict[str, Any]:
        """切换飞书交互模式 - 带实时情感反馈（动态更新同一消息）"""
        import asyncio
        import time

        # 尝试导入WebSocket客户端，如果失败则使用存根函数
        try:
            from ..feishu_websocket import (
                restart_websocket_client,
                stop_websocket_client,
            )

            WEBSOCKET_AVAILABLE = True
        except ImportError as e:
            print(f"[Command] WebSocket SDK not available: {e}")
            WEBSOCKET_AVAILABLE = False

            # 创建存根函数
            async def restart_websocket_client():
                print("[Command] WebSocket restart not available (SDK missing)")
                return False  # 重启失败，因为SDK缺失

            async def stop_websocket_client():
                print("[Command] WebSocket stop not available (SDK missing)")
                return True  # 停止"成功"，因为没有运行

        from .feishu_client import feishu_client

        # 发送初始消息并获取消息ID
        emotion = "🤔" if mode == "webhook" else "🚀"
        message_content = f"{emotion} 收到指令！正在准备切换到 {mode} 模式，请稍候～\n"
        initial_message = message_content.strip()  # 保存初始消息用于返回
        message_id = None

        print("[Command] switch_feishu_mode: sending initial message")
        try:
            result = await feishu_client.send_text_message(
                chat_id, message_content.strip()
            )
            if result and result.get("code") == 0:
                message_id = result.get("data", {}).get("message_id")
                print(
                    f"[Command] switch_feishu_mode: message sent with ID: {message_id}"
                )
            else:
                print(
                    f"[Command] switch_feishu_mode: failed to get message ID "
                    f"from result: {result}"
                )
        except Exception as e:
            print(f"[Command] switch_feishu_mode: failed to send initial message: {e}")
            # 如果直接发送失败，尝试通过 background_tasks
            if background_tasks:
                print("[Command] switch_feishu_mode: falling back to background_tasks")
                background_tasks.add_task(
                    feishu_client.send_text_message, chat_id, message_content.strip()
                )

        # 消息更新辅助函数
        async def update_message(new_content: str, append: bool = True):
            """更新消息内容 - 通过删除旧消息并发送新消息来模拟更新"""
            nonlocal message_content, message_id
            print(
                f"[Command] switch_feishu_mode: update_message called, "
                f"new_content='{new_content}', append={append}, message_id={message_id}"
            )
            if append:
                message_content += new_content + "\n"
            else:
                message_content = new_content + "\n"

            # 如果有旧消息，尝试删除
            old_message_id = message_id
            if old_message_id:
                try:
                    delete_result = await feishu_client.delete_message(old_message_id)
                    if delete_result and delete_result.get("code") == 0:
                        print(
                            "[Command] switch_feishu_mode: old message "
                            "deleted successfully"
                        )
                    else:
                        print(
                            f"[Command] switch_feishu_mode: failed to delete "
                            f"old message: {delete_result}"
                        )
                except Exception as e:
                    print(
                        f"[Command] switch_feishu_mode: error deleting old message: {e}"
                    )

            # 发送新消息
            try:
                result = await feishu_client.send_text_message(
                    chat_id, message_content.strip()
                )
                print(f"[Command] switch_feishu_mode: new message result: {result}")
                if result and result.get("code") == 0:
                    message_id = result.get("data", {}).get("message_id")
                else:
                    # 发送失败，保留旧message_id（如果还存在）
                    message_id = old_message_id
            except Exception as e:
                print(f"[Command] switch_feishu_mode: failed to send new message: {e}")
                message_id = old_message_id

        # 在后台执行模式切换
        async def do_switch_mode():
            print(
                f"[Command] switch_feishu_mode: do_switch_mode started for mode={mode}"
            )
            try:
                config = get_config_manager()

                # 验证模式
                if mode not in ["websocket", "webhook"]:
                    await update_message(
                        f"🤔 咦？{mode} 是什么模式？我只认识 'websocket' 和 'webhook' 哦～"
                    )
                    return

                # 检查WebSocket SDK是否可用
                if mode == "websocket" and not WEBSOCKET_AVAILABLE:
                    await update_message(
                        "⚠️ **WebSocket功能不可用**\n"
                        "❌ 缺少飞书官方SDK (lark_oapi)\n"
                        "🔧 请安装: `pip install lark-oapi`\n"
                        "📦 或使用Webhook模式"
                    )
                    return

                # 获取当前模式
                current_mode = config.get_feishu_mode()
                await update_message(f"🔍 让我看看... 当前是 {current_mode} 模式")

                if current_mode == mode:
                    await update_message(
                        f"😊 已经是 {mode} 模式啦，不用切换～ 我去喝杯茶 ☕️"
                    )
                    return

                # 开始切换 - 情感化表达
                await update_message(
                    f"🚀 **准备起飞！** 从 {current_mode} 切换到 {mode} 模式..."
                )
                await asyncio.sleep(0.5)

                # 步骤1: 保存配置
                await update_message(f"📝 步骤1: 正在保存 {mode} 配置...")
                success = config.set_feishu_mode(mode, save=True)
                await asyncio.sleep(0.3)

                if not success:
                    await update_message("😱 **糟糕！** 配置保存失败，让我想想办法...")
                    return

                await update_message(f"✅ 配置保存成功！现在切换到 {mode} 模式")
                await asyncio.sleep(0.5)

                # 步骤2: 根据模式执行不同操作
                if mode == "webhook":
                    await update_message(
                        "🔌 **Webhook模式启动！**\n正在停止WebSocket连接..."
                    )
                    # 停止WebSocket
                    stop_success = await stop_websocket_client()
                    await asyncio.sleep(0.5)

                    if stop_success:
                        await update_message(
                            "🛑 WebSocket已停止\n✨ 现在使用Webhook接收事件\n📍 请到飞书控制台配置回调URL: /feishu/webhook/opencode"
                        )
                    else:
                        await update_message(
                            "⚠️ WebSocket停止有点小问题，但Webhook模式已生效\n🔧 可以继续使用，我会在后台处理"
                        )

                else:  # websocket模式
                    await update_message("🔗 **WebSocket模式启动！**\n建立长连接中...")

                    # 重启 WebSocket 客户端
                    await update_message("⏳ 正在连接飞书服务器，稍等片刻～")

                    start_time = time.time()
                    restart_success = await restart_websocket_client()
                    elapsed_time = time.time() - start_time

                    if restart_success:
                        await update_message(
                            f"🎉 **连接成功！** (耗时 {elapsed_time:.1f}s)\n"
                            f"🤖 WebSocket长连接已建立\n"
                            f"📡 实时接收飞书事件中...\n"
                            f"💬 现在可以给我发消息啦！"
                        )
                    else:
                        await update_message(
                            "😅 **连接遇到小麻烦**\n"
                            "❌ WebSocket启动失败\n"
                            "🔍 正在检查原因...\n"
                            "💡 尝试：1. 检查网络 2. 查看日志 3. 重试一次"
                        )

            except Exception as e:
                try:
                    await update_message(
                        f"😨 **哎呀，出错了！**\n"
                        f"❌ 错误信息: {str(e)}\n"
                        f"🤗 别担心，我还在～ 试试重新切换模式？"
                    )
                except Exception:
                    # 如果连错误消息都发不出去...
                    pass

        # 启动后台任务
        print("[Command] switch_feishu_mode: scheduling do_switch_mode task")
        # 使用 background_tasks 确保任务在请求生命周期后继续执行
        if background_tasks:
            background_tasks.add_task(do_switch_mode)
            print("[Command] switch_feishu_mode: added to background_tasks")
        else:
            # 后备方案
            import asyncio

            task = asyncio.create_task(do_switch_mode())
            task.add_done_callback(
                lambda t: print(f"[Command] switch_feishu_mode task done: {t}")
            )
            print(f"[Command] switch_feishu_mode: task created {task}")

        # 立即返回响应（webhook处理器不需要再发送消息）
        return {
            "ok": True,
            "action": "switch_feishu_mode",
            "mode": mode,
            "message_sent": True,  # 表示消息已发送
            "message": initial_message,  # 保留消息内容供参考
        }

    def add_command(self, name: str, config: Dict[str, Any]):
        """添加新指令"""
        self.commands[name] = config
        self.save_config()

    def remove_command(self, name: str):
        """删除指令"""
        if name in self.commands:
            del self.commands[name]
            self.save_config()

    def list_commands(self) -> Dict[str, Dict[str, Any]]:
        """列出所有指令"""
        return self.commands.copy()


# 全局实例
_command_processor = None


def get_command_processor() -> CommandProcessor:
    """获取指令处理器实例"""
    global _command_processor
    if _command_processor is None:
        _command_processor = CommandProcessor()
    return _command_processor
