import json
import mimetypes
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

from .retry_handler import retry_async
from .secure_config import get_secret

load_dotenv()


class FeishuClient:
    def __init__(self):
        self.app_id = os.getenv("FEISHU_APP_ID", "")
        self.app_secret = get_secret("FEISHU_APP_SECRET", "")
        self.default_chat_id = os.getenv("FEISHU_DEFAULT_CHAT_ID", "")
        self.api_base = "https://open.feishu.cn/open-apis"
        self._tenant_access_token: str | None = None
        self._token_expires_at: float = 0

    def clear_token_cache(self):
        """清除缓存的token，强制下次请求获取新token"""
        self._tenant_access_token = None
        self._token_expires_at = 0
        print("[Feishu] Token cache cleared")

    @retry_async(
        max_retries=3,
        base_delay=1.0,
        max_delay=10.0,
        retryable_exceptions=(
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.NetworkError,
            Exception,
        ),
    )
    async def _make_request_with_retry(
        self,
        method: str,
        url: str,
        headers: dict,
        payload: Optional[dict] = None,
        **kwargs,
    ) -> dict[str, Any]:
        """带重试的HTTP请求"""
        async with httpx.AsyncClient() as client:
            if method.upper() == "POST":
                resp = await client.post(url, headers=headers, json=payload, timeout=30.0, **kwargs)
            elif method.upper() == "GET":
                resp = await client.get(url, headers=headers, timeout=30.0, **kwargs)
            elif method.upper() == "PATCH":
                resp = await client.patch(
                    url, headers=headers, json=payload, timeout=30.0, **kwargs
                )
            else:
                raise ValueError(f"Unsupported method: {method}")

            result = resp.json()

            # 检查Feishu API错误
            if result.get("code") != 0:
                error_msg = result.get("msg", "Unknown error")
                error_code = result.get("code")
                print(f"[Feishu] API error: {error_code} - {error_msg}")

                # 检查是否为token失效错误
                token_invalid_codes = [
                    99991663,
                    99991664,
                    99991665,
                ]  # 常见token失效错误码
                if error_code in token_invalid_codes:
                    print(f"[Feishu] Token invalid error detected ({error_code}), clearing cache")
                    self.clear_token_cache()
                    # 抛出异常让重试机制重新获取token
                    raise Exception(f"Feishu token invalid: {error_msg}")

                # 某些错误不应该重试
                if error_code in [200671, 200341]:  # 权限错误
                    return result
                raise Exception(f"Feishu API error: {error_msg}")

            return result

    async def get_tenant_access_token(self) -> str | None:
        import time

        if self._tenant_access_token and time.time() < self._token_expires_at - 60:
            print(
                f"[Feishu] Using cached access token, expires in {self._token_expires_at - time.time():.0f}s"
            )
            return self._tenant_access_token

        print(f"[Feishu] Getting new access token, app_id={self.app_id[:10]}...")
        url = f"{self.api_base}/auth/v3/tenant_access_token/internal"
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    url,
                    json={
                        "app_id": self.app_id,
                        "app_secret": self.app_secret,
                    },
                    timeout=30.0,
                )
                data = resp.json()
                print(f"[Feishu] Token response: {data}")
                if data.get("code") == 0:
                    self._tenant_access_token = data.get("tenant_access_token")
                    self._token_expires_at = time.time() + 7200
                    print(
                        f"[Feishu] Got access token: {self._tenant_access_token[:20]}..., expires at {self._token_expires_at}"
                    )
                    return self._tenant_access_token
                else:
                    print(f"[Feishu] Failed to get access token: {data}")
                    return None
            except Exception as e:
                print(f"[Feishu] Error getting access token: {e}")
                return None

    def get_chat_id(self) -> str | None:
        return self.default_chat_id or None

    async def send_text_message(
        self, receive_id: str | None, text: str, receive_id_type: str = "chat_id"
    ) -> dict[str, Any] | None:
        if not receive_id:
            receive_id = self.default_chat_id
        if not receive_id:
            print(
                f"[Feishu] Error: No receive_id provided for text message (type: {receive_id_type})"
            )
            return {"error": "No receive_id provided"}

        print(
            f"[Feishu] Sending text message to {receive_id[:10]}... (type: {receive_id_type}), length: {len(text)}"
        )
        print(f"[Feishu] Message preview: {text[:100]}...")

        token = await self.get_tenant_access_token()
        if not token:
            print("[Feishu] Error: Failed to get access token")
            return {"error": "Failed to get access token"}

        url = f"{self.api_base}/im/v1/messages?receive_id_type={receive_id_type}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payload = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}),
        }

        try:
            result = await self._make_request_with_retry("POST", url, headers, payload)
            print(f"[Feishu] Text message send result: {result}")
            return result
        except Exception as e:
            print(f"[Feishu] Error sending text message: {e}")
            return {"error": str(e)}

    async def update_text_message(self, message_id: str, text: str) -> dict[str, Any] | None:
        """更新已有的文本消息

        Args:
            message_id: 要更新的消息ID
            text: 新的消息内容

        Returns:
            更新结果，格式: {"code": 0, "data": {...}} 或 {"code": -1, "error": "..."}
        """
        print(f"[Feishu] Updating text message {message_id[:10]}..., length: {len(text)}")
        print(f"[Feishu] Message preview: {text[:100]}...")

        token = await self.get_tenant_access_token()
        if not token:
            print("[Feishu] Error: Failed to get access token")
            return {"code": -1, "error": "Failed to get access token"}

        # 飞书更新消息API: PATCH /im/v1/messages/{message_id}
        url = f"{self.api_base}/im/v1/messages/{message_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        payload = {
            "msg_type": "text",
            "content": json.dumps({"text": text}),
        }

        try:
            result = await self._make_request_with_retry("PATCH", url, headers, payload)
            print(f"[Feishu] Text message update result: {result}")
            return result
        except Exception as e:
            print(f"[Feishu] Error updating text message: {e}")
            return {"code": -1, "error": str(e)}

    async def send_interactive_card(
        self,
        receive_id: str | None,
        card: dict[str, Any],
        receive_id_type: str = "chat_id",
    ) -> dict[str, Any] | None:
        if not receive_id:
            receive_id = self.default_chat_id
        if not receive_id:
            print(f"[Feishu] Error: No receive_id provided (type: {receive_id_type})")
            return {"error": "No receive_id provided"}

        print(f"[Feishu] Getting access token, app_id={self.app_id[:5]}...")
        token = await self.get_tenant_access_token()
        if not token:
            print("[Feishu] Error: Failed to get access token")
            return {"error": "Failed to get access token"}

        url = f"{self.api_base}/im/v1/messages?receive_id_type={receive_id_type}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payload = {
            "receive_id": receive_id,
            "msg_type": "interactive",
            "content": json.dumps(card),
        }

        print(f"[Feishu] Sending interactive card to {receive_id} (type: {receive_id_type})")
        print(f"[Feishu] Card preview: {json.dumps(card)[:200]}...")

        try:
            result = await self._make_request_with_retry("POST", url, headers, payload)
            print("[Feishu] Card send result status: 200")
            print(f"[Feishu] Card send result keys: {list(result.keys())}")
            if "data" in result and isinstance(result["data"], dict):
                print(f"[Feishu] Card send data keys: {list(result['data'].keys())}")
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
        actual_file_name = upload_result.get("file_name", file_name or Path(file_path).name)

        if not file_key:
            return {"error": "No file key returned from upload"}

        # 第二步：发送文件消息
        return await self.send_file_message(receive_id, file_key, actual_file_name)

    async def delete_message(self, message_id: str) -> dict[str, Any] | None:
        """删除消息

        Args:
            message_id: 要删除的消息ID

        Returns:
            删除结果
        """
        print(f"[Feishu] Deleting message {message_id[:10]}...")
        token = await self.get_tenant_access_token()
        if not token:
            print("[Feishu] Error: Failed to get access token")
            return {"code": -1, "error": "Failed to get access token"}

        # 飞书删除消息API: DELETE /im/v1/messages/{message_id}
        url = f"{self.api_base}/im/v1/messages/{message_id}"
        headers = {
            "Authorization": f"Bearer {token}",
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.delete(url, headers=headers, timeout=30.0)
                result = resp.json()
                print(f"[Feishu] Delete message result: {result}")
                if result.get("code") != 0:
                    print(
                        f"[Feishu] Error deleting message: code={result.get('code')}, msg={result.get('msg')}, data={result.get('data')}"
                    )
                return result
        except Exception as e:
            print(f"[Feishu] Error deleting message: {e}")
            return {"code": -1, "error": str(e)}

    async def update_interactive_card(
        self, message_id: str, card: dict[str, Any]
    ) -> dict[str, Any] | None:
        """更新已有的交互卡片

        Args:
            message_id: 要更新的卡片消息ID
            card: 新的卡片内容

        Returns:
            更新结果，格式: {"code": 0, "data": {...}} 或 {"code": -1, "error": "..."}
        """
        print(f"[Feishu] Updating interactive card {message_id[:10]}...")
        print(f"[Feishu] Card preview: {json.dumps(card)[:200]}...")

        token = await self.get_tenant_access_token()
        if not token:
            print("[Feishu] Error: Failed to get access token")
            return {"code": -1, "error": "Failed to get access token"}

        # 飞书更新消息API: PATCH /im/v1/messages/{message_id}
        url = f"{self.api_base}/im/v1/messages/{message_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        payload = {
            "msg_type": "interactive",
            "content": json.dumps(card),
        }

        try:
            result = await self._make_request_with_retry("PATCH", url, headers, payload)
            print(f"[Feishu] Interactive card update result: {result}")
            return result
        except Exception as e:
            print(f"[Feishu] Error updating interactive card: {e}")
            return {"code": -1, "error": str(e)}


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


def build_progress_card(task_id: str, status: str, latest_output: str, tool_count: int = 0) -> dict:
    status_config = {
        "pending": {"emoji": "⏳", "template": "grey", "text": "等待中"},
        "running": {"emoji": "🔄", "template": "blue", "text": "执行中"},
        "completed": {"emoji": "✅", "template": "green", "text": "已完成"},
        "failed": {"emoji": "❌", "template": "red", "text": "失败"},
    }
    config = status_config.get(status, {"emoji": "📋", "template": "grey", "text": status})

    truncated_output = latest_output[:1500] if len(latest_output) > 1500 else latest_output
    if len(latest_output) > 1500:
        truncated_output += "\n\n📝 *(输出过长已截断，完整结果请查看终端或日志)*"

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
    "\n".join(output_lines[-5:]) if output_lines else "无输出"

    card = {
        "config": {"wide_screen_mode": True},
        "elements": [
            {
                "tag": "markdown",
                "content": f"## ✅ **OpenCode 任务完成**\n\n"
                f"**任务ID:** `{task_id}`\n\n"
                f"**任务:** {user_message[:300]}{'...' if len(user_message) > 300 else ''}",
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
                "content": f"**最终结果:**\n{final_result[:2000]}{'...\n\n📝 *(结果过长已截断，完整结果请查看终端或日志)*' if len(final_result) > 2000 else ''}",
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

    config = status_config.get(status, {"emoji": "📋", "template": "grey", "text": status})

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


def build_dynamic_progress_card(
    task_id: str,
    user_message: str,
    phase: str = "analyzing",
    progress: int = 0,
    thought_summary: str = "",
    recent_output: str = "",
    tool_count: int = 0,
    output_count: int = 0,
    status: str = "running",
    timeline: list[str] = None,
) -> dict:
    """构建动态进度卡片，支持阶段、进度条、思考摘要等

    Args:
        task_id: 任务ID
        user_message: 用户原始消息
        phase: 当前阶段 (analyzing, planning, reading, coding, testing, fixing, summarizing)
        progress: 进度百分比 (0-100)
        thought_summary: 思考摘要 (简短，不泄露内部推理)
        recent_output: 最近输出/日志
        tool_count: 工具使用次数
        output_count: 输出行数
        status: 状态 (pending, running, completed, failed)
        timeline: 阶段时间线，用于显示已完成阶段
    """
    from datetime import datetime

    # 阶段配置
    phase_config = {
        "analyzing": {"emoji": "🔍", "name": "分析需求", "color": "blue"},
        "planning": {"emoji": "📋", "name": "规划步骤", "color": "blue"},
        "reading": {"emoji": "📖", "name": "读取代码", "color": "purple"},
        "coding": {"emoji": "💻", "name": "生成代码", "color": "green"},
        "testing": {"emoji": "🧪", "name": "测试运行", "color": "yellow"},
        "fixing": {"emoji": "🔧", "name": "修复问题", "color": "orange"},
        "summarizing": {"emoji": "📝", "name": "整理结果", "color": "teal"},
    }

    phase_info = phase_config.get(phase, {"emoji": "🔄", "name": phase, "color": "blue"})

    # 状态配置
    status_config = {
        "pending": {"emoji": "⏳", "template": "grey", "text": "等待中"},
        "running": {"emoji": "🔄", "template": "blue", "text": "执行中"},
        "completed": {"emoji": "✅", "template": "green", "text": "已完成"},
        "failed": {"emoji": "❌", "template": "red", "text": "失败"},
    }
    status_info = status_config.get(status, {"emoji": "📋", "template": "grey", "text": status})

    # 构建卡片元素
    elements = []

    # 标题和基本信息
    elements.append(
        {
            "tag": "markdown",
            "content": f"## {status_info['emoji']} **OpenCode 任务 {status_info['text']}**\n\n"
            f"**任务ID:** `{task_id}`\n"
            f"**任务:** {user_message[:300]}{'...' if len(user_message) > 300 else ''}",
        }
    )

    elements.append({"tag": "hr"})

    # 进度条（如果状态是运行中）
    if status == "running":
        progress_bar = "▰" * (progress // 10) + "▱" * (10 - progress // 10)
        elements.append(
            {
                "tag": "markdown",
                "content": f"### {phase_info['emoji']} **当前阶段: {phase_info['name']}**\n\n"
                f"{progress_bar} **{progress}%**",
            }
        )
    else:
        elements.append(
            {
                "tag": "markdown",
                "content": f"### {phase_info['emoji']} **当前阶段: {phase_info['name']}**",
            }
        )

    # 思考摘要（如果有）
    if thought_summary:
        elements.append(
            {
                "tag": "markdown",
                "content": f"**💭 思考摘要:**\n{thought_summary[:500]}{'...' if len(thought_summary) > 500 else ''}",
            }
        )

    # 最近输出（如果有）
    if recent_output:
        truncated_output = recent_output[:3000] if len(recent_output) > 3000 else recent_output
        elements.append(
            {
                "tag": "markdown",
                "content": f"**📤 最近输出:**\n```\n{truncated_output}\n```{'...(已截断，完整结果请查看终端或日志)' if len(recent_output) > 3000 else ''}",
            }
        )

    elements.append({"tag": "hr"})

    # 统计信息
    stats_content = "**📊 统计:**\n"
    stats_content += f"• 🛠️ 工具使用: {tool_count} 次\n"
    stats_content += f"• 📝 输出行数: {output_count}\n"
    stats_content += f"• 🕐 更新时间: {datetime.now().strftime('%H:%M:%S')}"

    if timeline:
        stats_content += f"\n• 📋 已完成阶段: {' → '.join(timeline[:3])}"
        if len(timeline) > 3:
            stats_content += " → ..."

    elements.append({"tag": "markdown", "content": stats_content})

    # 添加阶段时间线（如果提供）
    if timeline and len(timeline) > 0:
        elements.append({"tag": "hr"})
        timeline_text = "**⏱️ 阶段进展:**\n"
        for i, stage in enumerate(timeline):
            timeline_text += f"{i + 1}. ✅ {stage}\n"
        timeline_text += f"**当前:** ▶️ {phase_info['name']}"
        elements.append({"tag": "markdown", "content": timeline_text})

    return {
        "config": {"wide_screen_mode": True},
        "elements": elements,
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"{phase_info['emoji']} OpenCode {phase_info['name']}",
            },
            "template": phase_info["color"],
        },
    }


feishu_client = FeishuClient()
