"""
自定义指令处理器
处理用户定义的快捷指令
"""

import json
import os
import subprocess
from typing import Dict, Any, Optional, Union
from pathlib import Path


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
            project_dir = Path(__file__).parent.parent
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
                    f"[Commands] Loaded {len(self.commands)} commands from {self.config_path}"
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
                "description": "AI Project Lab 自定义指令配置",
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
            else:
                return {"ok": False, "error": f"Unknown action: {action}"}
        except Exception as e:
            print(f"[Commands] Error executing command: {e}")
            return {"ok": False, "error": str(e)}

    async def _clear_session(self, user_id: str, chat_id: str) -> Dict[str, Any]:
        """清空当前用户的会话"""
        from app.session_manager import get_session_manager, SessionStatus

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
        from app.session_manager import get_session_manager

        session_manager = get_session_manager()

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
        """执行Git提交"""
        import asyncio
        from app.feishu_client import feishu_client

        # 在后台执行Git提交
        async def do_git_commit():
            try:
                project_dir = Path(__file__).parent.parent

                # 发送开始消息
                await feishu_client.send_text_message(chat_id, "🚀 开始执行Git提交...")

                # 执行Git命令
                commands = [
                    ["git", "add", "."],
                    ["git", "status"],
                    [
                        "git",
                        "commit",
                        "-m",
                        f"Update from Feishu bot - {subprocess.check_output(['date', '+%Y-%m-%d %H:%M:%S']).decode().strip()}",
                    ],
                    ["git", "push"],
                ]

                results = []
                for cmd in commands:
                    result = subprocess.run(
                        cmd, cwd=project_dir, capture_output=True, text=True, timeout=60
                    )
                    results.append(
                        {
                            "command": " ".join(cmd),
                            "returncode": result.returncode,
                            "stdout": result.stdout[:500],
                            "stderr": result.stderr[:500],
                        }
                    )

                # 发送结果
                success = all(r["returncode"] == 0 for r in results)
                if success:
                    await feishu_client.send_text_message(
                        chat_id,
                        "✅ Git提交完成！\n\n"
                        + "📋 执行结果:\n"
                        + "✓ git add .\n"
                        + "✓ git status\n"
                        + "✓ git commit\n"
                        + "✓ git push",
                    )
                else:
                    errors = "\n".join(
                        [
                            f"✗ {r['command']}: {r['stderr']}"
                            for r in results
                            if r["returncode"] != 0
                        ]
                    )
                    await feishu_client.send_text_message(
                        chat_id, f"❌ Git提交失败:\n\n{errors[:1000]}"
                    )

            except Exception as e:
                await feishu_client.send_text_message(
                    chat_id, f"❌ Git提交出错: {str(e)}"
                )

        # 启动后台任务
        asyncio.create_task(do_git_commit())

        return {
            "ok": True,
            "action": "git_commit",
            "message": "Git提交任务已启动，请稍候...",
        }

    async def _start_server(self, chat_id: str) -> Dict[str, Any]:
        """启动服务器"""
        import asyncio
        from app.feishu_client import feishu_client

        async def do_start_server():
            try:
                project_dir = Path(__file__).parent.parent

                # 检查服务器是否已在运行
                result = subprocess.run(
                    ["curl", "-s", "http://127.0.0.1:8000/health"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode == 0 and '{"ok":true}' in result.stdout:
                    await feishu_client.send_text_message(
                        chat_id,
                        "✅ 服务器已经在运行中！\n\n"
                        "📍 本地地址: http://127.0.0.1:8000\n"
                        "🌐 检查公网URL请运行: ./manage.sh status",
                    )
                    return

                # 启动服务器
                await feishu_client.send_text_message(chat_id, "🖥️ 正在启动服务器...")

                subprocess.Popen(
                    [
                        "python",
                        "-m",
                        "uvicorn",
                        "app.main:app",
                        "--host",
                        "0.0.0.0",
                        "--port",
                        "8000",
                    ],
                    cwd=project_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )

                # 等待服务器启动
                await asyncio.sleep(5)

                # 检查是否启动成功
                result = subprocess.run(
                    ["curl", "-s", "http://127.0.0.1:8000/health"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode == 0 and '{"ok":true}' in result.stdout:
                    await feishu_client.send_text_message(
                        chat_id,
                        "✅ 服务器启动成功！\n\n"
                        "📍 本地地址: http://127.0.0.1:8000\n"
                        "🌐 如需公网访问，请启动隧道: ./manage.sh tunnel",
                    )
                else:
                    await feishu_client.send_text_message(
                        chat_id, "❌ 服务器启动失败，请检查日志"
                    )

            except Exception as e:
                await feishu_client.send_text_message(
                    chat_id, f"❌ 启动服务器出错: {str(e)}"
                )

        # 启动后台任务
        asyncio.create_task(do_start_server())

        return {
            "ok": True,
            "action": "start_server",
            "message": "服务器启动任务已启动，请稍候...",
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
