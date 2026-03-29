import json
from typing import Any


def extract_text_from_feishu_payload(body: dict[str, Any]) -> dict[str, Any]:
    # 兼容最简单测试输入：{"text": "..."}
    if "text" in body and isinstance(body["text"], str):
        text = body["text"].strip()
        if not text:
            return {
                "task_type": "unknown",
                "raw_text": "",
                "status": "ignored",
            }

        return {
            "task_type": "design_request",
            "raw_text": text,
            "status": "queued",
        }

    # 兼容飞书消息结构
    event = body.get("event", {})
    message = event.get("message", {})
    content = message.get("content", "")

    text = ""

    if isinstance(content, str) and content:
        try:
            content_json = json.loads(content)
            text = content_json.get("text", "").strip()
        except Exception:
            text = content.strip()

    if not text:
        return {
            "task_type": "unknown",
            "raw_text": "",
            "status": "ignored",
        }

    return {
        "task_type": "design_request",
        "raw_text": text,
        "status": "queued",
    }
