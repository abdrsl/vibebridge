#!/usr/bin/env python3
import asyncio
import sys

sys.path.insert(0, ".")
from src.legacy.feishu_client import feishu_client


async def test_send():
    chat_id = "oc_REDACTED_CHAT_ID"
    message = "测试消息 from standalone script"
    print(f"Sending to {chat_id}")
    result = await feishu_client.send_text_message(chat_id, message)
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(test_send())
