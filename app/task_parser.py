import json
from typing import Any


def extract_text_from_feishu_payload(body: dict[str, Any]) -> str:
    # 1) 兼容最简单测试格式
    if "text" in body and isinstance(body["text"], str):
        return body["text"].strip()

    # 2) 飞书事件格式：event.message.content 是 JSON 字符串
    event = body.get("event") or {}
    message = event.get("message") or {}
    content = message.get("content")

    if isinstance(content, str):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                text = parsed.get("text", "")
                if isinstance(text, str):
                    return text.strip()
        except json.JSONDecodeError:
            # 如果 content 不是 JSON，就直接返回原始字符串
            return content.strip()

    # 3) 兜底
    return ""


def build_task_from_text(text: str) -> dict[str, Any]:
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
