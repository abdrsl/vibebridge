import json
import os
from datetime import datetime
from typing import Any

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
            "msg_type": "interactive",
            "content": json.dumps(card),
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=30.0)
            return resp.json()


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


feishu_client = FeishuClient()
