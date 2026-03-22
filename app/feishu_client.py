import json
import os
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Optional

import httpx
from dotenv import load_dotenv
from app.secure_config import get_secret

load_dotenv()


class FeishuClient:
    def __init__(self):
        self.app_id = os.getenv("FEISHU_APP_ID", "")
        self.app_secret = get_secret("FEISHU_APP_SECRET", "")
        self.default_chat_id = os.getenv("FEISHU_DEFAULT_CHAT_ID", "")
        self.api_base = "https://open.feishu.cn/open-apis"
        self._tenant_access_token: str | None = None
        self._token_expires_at: float = 0

    async def get_tenant_access_token(self) -> str | None:
        import time

        if self._tenant_access_token and time.time() < self._token_expires_at - 60:
            return self._tenant_access_token

        url = f"{self.api_base}/auth/v3/tenant_access_token/internal"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={"app_id": self.app_id, "app_secret": self.app_secret},
                timeout=30.0,
            )
            data = resp.json()
            if data.get("code") == 0:
                self._tenant_access_token = data.get("tenant_access_token")
                import time

                self._token_expires_at = time.time() + 7200
                return self._tenant_access_token
            return None

    def get_chat_id(self) -> str | None:
        return self.default_chat_id or None

    async def send_text_message(
        self, receive_id: str | None, text: str
    ) -> dict[str, Any] | None:
        if not receive_id:
            receive_id = self.default_chat_id
        if not receive_id:
            return {"error": "No chat_id provided"}

        token = await self.get_tenant_access_token()
        if not token:
            return {"error": "Failed to get access token"}

        url = f"{self.api_base}/im/v1/messages?receive_id_type=chat_id"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payload = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": '{"text":"' + text.replace('"', '\\"') + '"}',
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=30.0)
            return resp.json()

    async def send_interactive_card(
        self,
        receive_id: str | None,
        card: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not receive_id:
            receive_id = self.default_chat_id
        if not receive_id:
            print(f"[Feishu] Error: No chat_id provided")
            return {"error": "No chat_id provided"}

        print(f"[Feishu] Getting access token, app_id={self.app_id[:5]}...")
        token = await self.get_tenant_access_token()
        if not token:
            print(f"[Feishu] Error: Failed to get access token")
            return {"error": "Failed to get access token"}

        url = f"{self.api_base}/im/v1/messages?receive_id_type=chat_id"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payload = {
            "receive_id": receive_id,
            "msg_type": "interactive",
            "content": json.dumps(card),
        }

        print(f"[Feishu] Sending interactive card to {receive_id}")
        print(f"[Feishu] Card preview: {json.dumps(card)[:200]}...")

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url, headers=headers, json=payload, timeout=30.0
                )
                result = resp.json()
                print(f"[Feishu] Card send result: {result}")
                return result
        except Exception as e:
            print(f"[Feishu] Error sending card: {e}")
            import traceback

            traceback.print_exc()
            return {"error": f"Failed to send card: {e}"}

    async def upload_file(
        self,
        file_path: str | Path,
        file_name: Optional[str] = None,
        file_type: str = "stream",
    ) -> dict[str, Any] | None:
        """
        上传文件到飞书并获取文件key

        Args:
            file_path: 文件路径
            file_name: 文件名（可选，默认使用路径中的文件名）
            file_type: 文件类型（stream, image, file等）

        Returns:
            包含file_key的字典，可用于发送文件消息
        """
        token = await self.get_tenant_access_token()
        if not token:
            return {"error": "Failed to get access token"}

        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        if not file_name:
            file_name = path.name

        # 获取文件大小和类型
        file_size = path.stat().st_size
        mime_type, _ = mimetypes.guess_type(str(path))

        # 第一步：获取上传信息
        upload_info_url = f"{self.api_base}/im/v1/files/upload_info"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        upload_info_payload = {
            "file_name": file_name,
            "file_size": file_size,
            "file_type": mime_type or "application/octet-stream",
            "parent_type": "message",
            "parent_node": "root",
        }

        async with httpx.AsyncClient() as client:
            # 获取上传信息
            resp = await client.post(
                upload_info_url, headers=headers, json=upload_info_payload, timeout=30.0
            )

            if resp.status_code != 200:
                return {"error": f"Failed to get upload info: {resp.text}"}

            upload_info = resp.json()
            if upload_info.get("code") != 0:
                return {"error": f"Upload info error: {upload_info}"}

            data = upload_info.get("data", {})
            upload_url = data.get("upload_url")
            file_key = data.get("file_key")

            if not upload_url or not file_key:
                return {"error": "Invalid upload info response"}

            # 第二步：上传文件到返回的URL
            with open(path, "rb") as f:
                file_content = f.read()

            upload_headers = {
                "Content-Type": mime_type or "application/octet-stream",
                "Content-Length": str(file_size),
            }

            upload_resp = await client.put(
                upload_url, headers=upload_headers, content=file_content, timeout=60.0
            )

            if upload_resp.status_code not in (200, 201, 204):
                return {"error": f"Failed to upload file: {upload_resp.text}"}

            return {
                "file_key": file_key,
                "file_name": file_name,
                "file_size": file_size,
                "mime_type": mime_type,
            }

    async def send_file_message(
        self,
        receive_id: str | None,
        file_key: str,
        file_name: str,
    ) -> dict[str, Any] | None:
        """
        发送文件消息

        Args:
            receive_id: 接收者ID（群聊ID）
            file_key: 通过upload_file获取的文件key
            file_name: 文件名

        Returns:
            发送结果
        """
        if not receive_id:
            receive_id = self.default_chat_id
        if not receive_id:
            return {"error": "No chat_id provided"}

        token = await self.get_tenant_access_token()
        if not token:
            return {"error": "Failed to get access token"}

        url = f"{self.api_base}/im/v1/messages?receive_id_type=chat_id"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payload = {
            "receive_id": receive_id,
            "msg_type": "file",
            "content": json.dumps(
                {
                    "file_key": file_key,
                    "file_name": file_name,
                }
            ),
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=30.0)
            return resp.json()

    async def send_file_from_path(
        self,
        receive_id: str | None,
        file_path: str | Path,
        file_name: Optional[str] = None,
    ) -> dict[str, Any] | None:
        """
        从文件路径直接发送文件到飞书（两步操作：上传+发送）

        Args:
            receive_id: 接收者ID
            file_path: 文件路径
            file_name: 文件名（可选）

        Returns:
            发送结果
        """
        # 第一步：上传文件
        upload_result = await self.upload_file(file_path, file_name)
        if upload_result and "error" in upload_result:
            return upload_result

        if not upload_result:
            return {"error": "Upload failed"}

        file_key = upload_result.get("file_key")
        actual_file_name = upload_result.get(
            "file_name", file_name or Path(file_path).name
        )

        if not file_key:
            return {"error": "No file key returned from upload"}

        # 第二步：发送文件消息
        return await self.send_file_message(receive_id, file_key, actual_file_name)


def build_start_card(task_id: str, user_message: str) -> dict:
    return {
        "config": {"wide_screen_mode": True},
        "elements": [
            {
                "tag": "markdown",
                "content": f"## 🚀 **OpenCode 任务已启动**\n\n**任务ID:** `{task_id}`\n\n**任务描述:**\n{user_message[:200]}{'...' if len(user_message) > 200 else ''}",
            },
            {"tag": "hr"},
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": f"⏱️ {datetime.now().strftime('%H:%M:%S')} 开始执行...",
                    }
                ],
            },
        ],
        "header": {
            "title": {"tag": "plain_text", "content": "🔨 OpenCode 工作中"},
            "template": "blue",
        },
    }


def build_progress_card(
    task_id: str, status: str, latest_output: str, tool_count: int = 0
) -> dict:
    status_config = {
        "pending": {"emoji": "⏳", "template": "grey", "text": "等待中"},
        "running": {"emoji": "🔄", "template": "blue", "text": "执行中"},
        "completed": {"emoji": "✅", "template": "green", "text": "已完成"},
        "failed": {"emoji": "❌", "template": "red", "text": "失败"},
    }
    config = status_config.get(
        status, {"emoji": "📋", "template": "grey", "text": status}
    )

    truncated_output = (
        latest_output[:800] if len(latest_output) > 800 else latest_output
    )
    if len(latest_output) > 800:
        truncated_output += "\n\n📝 *(输出过长已截断)*"

    card = {
        "config": {"wide_screen_mode": True},
        "elements": [
            {
                "tag": "markdown",
                "content": f"## {config['emoji']} **OpenCode 任务 {config['text']}**\n\n"
                f"**任务ID:** `{task_id}`\n\n"
                f"**最新操作:**\n"
                f"```\n{truncated_output}\n```",
            },
            {"tag": "hr"},
            {
                "tag": "markdown",
                "content": f"🛠️ 已执行 {tool_count} 个操作",
            },
        ],
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"{config['emoji']} OpenCode 工作中",
            },
            "template": config["template"],
        },
    }
    return card


def build_result_card(
    task_id: str,
    user_message: str,
    output_lines: list[str],
    final_result: str | None = None,
) -> dict:
    summary = "\n".join(output_lines[-5:]) if output_lines else "无输出"

    card = {
        "config": {"wide_screen_mode": True},
        "elements": [
            {
                "tag": "markdown",
                "content": f"## ✅ **OpenCode 任务完成**\n\n"
                f"**任务ID:** `{task_id}`\n\n"
                f"**任务:** {user_message[:150]}{'...' if len(user_message) > 150 else ''}",
            },
        ],
        "header": {
            "title": {"tag": "plain_text", "content": "🎉 OpenCode 完成"},
            "template": "green",
        },
    }

    if final_result:
        card["elements"].append(
            {
                "tag": "markdown",
                "content": f"**最终结果:**\n{final_result[:1000]}",
            }
        )

    card["elements"].append({"tag": "hr"})
    card["elements"].append(
        {
            "tag": "markdown",
            "content": f"📊 **统计:** {len(output_lines)} 个操作步骤\n"
            f"⏱️ 完成时间: {datetime.now().strftime('%H:%M:%S')}",
        }
    )

    return card


def build_error_card(task_id: str, error_message: str) -> dict:
    return {
        "config": {"wide_screen_mode": True},
        "elements": [
            {
                "tag": "markdown",
                "content": f"## ❌ **OpenCode 任务失败**\n\n"
                f"**任务ID:** `{task_id}`\n\n"
                f"**错误信息:**\n"
                f"```\n{error_message}\n```",
            },
            {"tag": "hr"},
            {
                "tag": "note",
                "elements": [{"tag": "plain_text", "content": "请检查任务配置或重试"}],
            },
        ],
        "header": {
            "title": {"tag": "plain_text", "content": "⚠️ OpenCode 错误"},
            "template": "red",
        },
    }


def build_help_card() -> dict:
    return {
        "config": {"wide_screen_mode": True},
        "elements": [
            {
                "tag": "markdown",
                "content": "## 🤖 **OpenCode AI 助手**\n\n"
                "发送消息给我，我会帮你完成代码开发任务！\n\n"
                "**使用方法:**\n"
                "直接发送你的开发需求，例如：\n"
                "- `请在 app 目录创建一个新的 API 路由`\n"
                "- `帮我优化这个函数的性能`\n"
                "- `添加用户认证功能`",
            },
            {"tag": "hr"},
            {
                "tag": "markdown",
                "content": "**示例命令:**\n```\n请在 data 目录创建一个配置文件\n```",
            },
        ],
        "header": {
            "title": {"tag": "plain_text", "content": "🤖 OpenCode 助手"},
            "template": "indigo",
        },
    }


def build_confirmation_card(
    session_id: str,
    user_message: str,
    task_summary: str = "",
    show_cancel: bool = True,
) -> dict:
    """
    构建确认卡片

    Args:
        session_id: Session ID
        user_message: 用户原始消息
        task_summary: 任务摘要（可选）
        show_cancel: 是否显示取消按钮

    Returns:
        卡片配置
    """
    # 生成任务摘要（如果未提供）
    if not task_summary:
        if len(user_message) > 100:
            task_summary = f"{user_message[:100]}..."
        else:
            task_summary = user_message

    elements = [
        {
            "tag": "markdown",
            "content": f"## 🤖 **OpenCode 任务确认**\n\n"
            f"**任务描述:**\n{task_summary}\n\n"
            f"请确认是否开始执行此任务？",
        },
        {"tag": "hr"},
        {
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "✅ 确认执行"},
                    "type": "primary",
                    "value": json.dumps(
                        {
                            "action": "confirm",
                            "session_id": session_id,
                        }
                    ),
                },
            ],
        },
    ]

    if show_cancel:
        elements[2]["actions"].append(
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "❌ 取消"},
                "type": "danger",
                "value": json.dumps(
                    {
                        "action": "cancel",
                        "session_id": session_id,
                    }
                ),
            }
        )

    return {
        "config": {"wide_screen_mode": True},
        "elements": elements,
        "header": {
            "title": {"tag": "plain_text", "content": "🔍 任务确认"},
            "template": "blue",
        },
    }


def build_session_continue_card(
    session_id: str,
    previous_task: str,
    user_message: str,
) -> dict:
    """
    构建继续session卡片

    Args:
        session_id: Session ID
        previous_task: 上一个任务描述
        user_message: 当前用户消息

    Returns:
        卡片配置
    """
    return {
        "config": {"wide_screen_mode": True},
        "elements": [
            {
                "tag": "markdown",
                "content": f"## 🔄 **继续当前任务**\n\n"
                f"**上一个任务:** {previous_task[:80]}...\n\n"
                f"**新消息:** {user_message[:100]}...\n\n"
                f"请选择操作：",
            },
            {"tag": "hr"},
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "🔄 继续当前任务"},
                        "type": "primary",
                        "value": json.dumps(
                            {
                                "action": "continue",
                                "session_id": session_id,
                            }
                        ),
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "🆕 开始新任务"},
                        "type": "default",
                        "value": json.dumps(
                            {
                                "action": "new",
                                "session_id": session_id,
                            }
                        ),
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "❌ 取消当前任务"},
                        "type": "danger",
                        "value": json.dumps(
                            {
                                "action": "cancel",
                                "session_id": session_id,
                            }
                        ),
                    },
                ],
            },
        ],
        "header": {
            "title": {"tag": "plain_text", "content": "🔄 任务管理"},
            "template": "purple",
        },
    }


def build_session_status_card(
    session_id: str,
    status: str,
    task_description: str,
    progress: str = "",
    actions_available: bool = True,
) -> dict:
    """
    构建session状态卡片

    Args:
        session_id: Session ID
        status: 状态（running, completed, failed等）
        task_description: 任务描述
        progress: 进度信息（可选）
        actions_available: 是否显示操作按钮

    Returns:
        卡片配置
    """
    status_config = {
        "pending": {"emoji": "⏳", "template": "grey", "text": "等待确认"},
        "confirmed": {"emoji": "✅", "template": "blue", "text": "已确认"},
        "running": {"emoji": "🔄", "template": "blue", "text": "执行中"},
        "completed": {"emoji": "🎉", "template": "green", "text": "已完成"},
        "failed": {"emoji": "❌", "template": "red", "text": "失败"},
        "cancelled": {"emoji": "🚫", "template": "grey", "text": "已取消"},
    }

    config = status_config.get(
        status, {"emoji": "📋", "template": "grey", "text": status}
    )

    elements = [
        {
            "tag": "markdown",
            "content": f"## {config['emoji']} **任务状态: {config['text']}**\n\n"
            f"**任务:** {task_description[:150]}...\n\n"
            f"**Session ID:** `{session_id}`",
        },
    ]

    if progress:
        elements.append(
            {
                "tag": "markdown",
                "content": f"**进度:**\n{progress}",
            }
        )

    elements.append({"tag": "hr"})

    if actions_available:
        action_elements = []

        if status in ["pending", "confirmed"]:
            action_elements.extend(
                [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "▶️ 开始执行"},
                        "type": "primary",
                        "value": json.dumps(
                            {
                                "action": "start",
                                "session_id": session_id,
                            }
                        ),
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "❌ 取消"},
                        "type": "danger",
                        "value": json.dumps(
                            {
                                "action": "cancel",
                                "session_id": session_id,
                            }
                        ),
                    },
                ]
            )
        elif status == "running":
            action_elements.append(
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "⏹️ 停止"},
                    "type": "danger",
                    "value": json.dumps(
                        {
                            "action": "stop",
                            "session_id": session_id,
                        }
                    ),
                }
            )
        elif status in ["completed", "failed"]:
            action_elements.extend(
                [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "🔄 重新执行"},
                        "type": "primary",
                        "value": json.dumps(
                            {
                                "action": "retry",
                                "session_id": session_id,
                            }
                        ),
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "🗑️ 清理"},
                        "type": "default",
                        "value": json.dumps(
                            {
                                "action": "cleanup",
                                "session_id": session_id,
                            }
                        ),
                    },
                ]
            )

        if action_elements:
            elements.append(
                {
                    "tag": "action",
                    "actions": action_elements,
                }
            )

    return {
        "config": {"wide_screen_mode": True},
        "elements": elements,
        "header": {
            "title": {"tag": "plain_text", "content": f"{config['emoji']} 任务状态"},
            "template": config["template"],
        },
    }


feishu_client = FeishuClient()
