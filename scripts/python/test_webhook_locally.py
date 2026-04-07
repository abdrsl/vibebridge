#!/usr/bin/env python3
"""
简单测试本地webhook
"""

import json
import time

import requests

# 使用本地服务器
webhook_url = "http://localhost:8000/feishu/webhook/opencode"

# 创建测试消息
payload = {
    "schema": "2.0",
    "header": {
        "event_id": f"test_{int(time.time())}",
        "event_type": "im.message.receive_v1",
        "create_time": str(int(time.time() * 1000)),
        "token": "test_token",
        "app_id": "cli_test",
        "tenant_key": "test_tenant",
    },
    "event": {
        "sender": {
            "sender_id": {
                "open_id": "ou_test_user",
                "union_id": "on_test_user",
                "user_id": "user_test",
            },
            "sender_type": "user",
            "tenant_key": "test_tenant",
        },
        "message": {
            "message_id": f"om_{int(time.time())}",
            "root_id": "",
            "parent_id": "",
            "create_time": str(int(time.time() * 1000)),
            "chat_id": "oc_test_chat",
            "chat_type": "p2p",
            "message_type": "text",
            "content": json.dumps(
                {"text": "测试本地webhook，请回复我"}, ensure_ascii=False
            ),
            "mentions": [],
        },
    },
}

print(f"测试本地webhook: {webhook_url}")
print(f"消息内容: {json.loads(payload['event']['message']['content'])['text']}")

try:
    response = requests.post(webhook_url, json=payload, timeout=10)
    print(f"响应状态: {response.status_code}")
    print(f"响应内容: {response.text}")
except Exception as e:
    print(f"错误: {e}")
    import traceback

    traceback.print_exc()
