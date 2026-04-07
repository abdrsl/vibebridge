#!/usr/bin/env python3
import asyncio
import json

import httpx


async def test_greeting():
    """测试 greeting 命令"""
    url = "http://localhost:8000/feishu/webhook/opencode"

    # 模拟飞书 webhook v2 格式
    payload = {
        "schema": "2.0",
        "header": {
            "event_id": "test_1775000008",
            "event_type": "im.message.receive_v1",
            "create_time": "1775000008000",
            "token": "test_token",
            "app_id": "cli_xxxxxxxxxxxxxxxx",
            "tenant_key": "REDACTED_TENANT_KEY",
        },
        "event": {
            "sender": {
                "sender_id": {
                    "open_id": "ou_REDACTED_OPEN_ID",
                    "union_id": "on_3cd4b324749566c06113b05b3aa4d6aa",
                    "user_id": "ec31c933",
                },
                "sender_type": "user",
                "tenant_key": "REDACTED_TENANT_KEY",
            },
            "message": {
                "message_id": "om_test_1775000008",
                "root_id": "",
                "parent_id": "",
                "create_time": "1775000008000",
                "chat_id": "oc_REDACTED_CHAT_ID",
                "chat_type": "p2p",
                "message_type": "text",
                "content": json.dumps({"text": "hello"}),
            },
        },
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=30.0)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code, response.text


if __name__ == "__main__":
    asyncio.run(test_greeting())
