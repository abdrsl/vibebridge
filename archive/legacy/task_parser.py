import json
from typing import Any


def extract_text_from_feishu_payload(body: dict[str, Any]) -> dict[str, Any]:
    import re

    result: dict[str, Any] = {
        "task_type": "unknown",
        "raw_text": "",
        "status": "ignored",
    }

    # Extract Feishu chat / user context for reply routing
    event = body.get("event", {})
    message = event.get("message", {})
    sender = event.get("sender", {})

    chat_id = message.get("chat_id") or message.get("open_chat_id")
    user_id = sender.get("sender_id", {}).get("open_id") or sender.get("sender_id", {}).get("user_id")
    message_id = message.get("message_id")

    if chat_id:
        result["chat_id"] = chat_id
    if user_id:
        result["user_id"] = user_id
    if message_id:
        result["message_id"] = message_id

    # 兼容最简单测试输入：{"text": "..."}
    if "text" in body and isinstance(body["text"], str):
        text = body["text"].strip()
        # 清理飞书@mention标签格式
        text = re.sub(r"<at[^>]*>.*?</at>", "", text)
        text = re.sub(r"^\s*@[^\s]+\s*", "", text)
        text = text.strip()

        if text:
            result["task_type"] = "design_request"
            result["raw_text"] = text
            result["status"] = "queued"
        return result

    # 兼容飞书消息结构
    content = message.get("content", "")
    text = ""

    if isinstance(content, str) and content:
        try:
            content_json = json.loads(content)
            text = content_json.get("text", "").strip()
            # 清理飞书@mention标签格式
            text = re.sub(r"<at[^>]*>.*?</at>", "", text)
            text = re.sub(r"^\s*@\s*", "", text)
            text = text.strip()
        except Exception:
            text = content.strip()
            text = re.sub(r"<at[^>]*>.*?</at>", "", text)
            text = re.sub(r"^\s*@\s*", "", text)
            text = text.strip()

    if text:
        result["task_type"] = "design_request"
        result["raw_text"] = text
        result["status"] = "queued"

    return result
