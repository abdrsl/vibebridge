import json
from typing import Any


def extract_text_from_feishu_payload(body: dict[str, Any]) -> dict[str, Any]:
    import re

    # 兼容最简单测试输入：{"text": "..."}
    if "text" in body and isinstance(body["text"], str):
        text = body["text"].strip()
        # 清理飞书@mention标签格式
        text = re.sub(r"<at[^>]*>.*?</at>", "", text)
        text = re.sub(r"^\s*@[^\s]+\s*", "", text)
        text = text.strip()

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
            # 清理飞书@mention标签格式
            import re

            text = re.sub(r"<at[^>]*>.*?</at>", "", text)
            text = re.sub(r"^\s*@\s*", "", text)
            text = text.strip()
        except Exception:
            text = content.strip()
            # 清理飞书@mention标签格式
            import re

            text = re.sub(r"<at[^>]*>.*?</at>", "", text)
            text = re.sub(r"^\s*@\s*", "", text)
            text = text.strip()

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
