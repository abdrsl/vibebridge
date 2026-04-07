#!/usr/bin/env python3
"""
测试发送消息到服务器
"""

import json

import requests

# 模拟飞书webhook
webhook_url = "http://127.0.0.1:8000/feishu/webhook/opencode"

# 创建一个测试消息
test_message = {
    "schema": "2.0",
    "header": {
        "event_id": "test_event_001",
        "event_type": "im.message.receive_v1",
        "create_time": "1774124128000",
        "token": "test_token",
        "app_id": "test_app",
        "tenant_key": "test_tenant",
    },
    "event": {
        "message": {
            "message_id": "test_msg_001",
            "chat_id": "oc_test_chat_123",
            "chat_type": "p2p",
            "content": json.dumps({"text": "请帮我测试卡片功能"}),
            "message_type": "text",
            "create_time": "1774124128000",
        },
        "sender": {
            "sender_id": {
                "open_id": "ou_test_user_123",
                "union_id": "on_test_user_123",
                "user_id": "test_user_123",
            },
            "sender_type": "user",
            "tenant_key": "test_tenant",
        },
    },
}

print("发送测试消息到服务器...")
response = requests.post(webhook_url, json=test_message, timeout=10)
print(f"响应状态码: {response.status_code}")
print(f"响应内容: {response.text}")

print("\n等待卡片发送...")
import time

time.sleep(2)

print("\n检查服务器日志...")
import subprocess

result = subprocess.run(["tail", "-50", "server.log"], capture_output=True, text=True)
print(result.stdout)
