#!/usr/bin/env python3
"""
测试当前服务器状态
"""

import json
import time

import requests

# 测试服务器是否响应
print("1. 测试服务器健康检查...")
try:
    health_response = requests.get("http://127.0.0.1:8000/health", timeout=5)
    print(f"   状态码: {health_response.status_code}")
    print(f"   响应: {health_response.text}")
except Exception as e:
    print(f"   错误: {e}")

print("\n2. 测试发送消息到webhook...")
webhook_url = "http://127.0.0.1:8000/feishu/webhook/opencode"

# 创建一个测试消息
test_message = {
    "schema": "2.0",
    "header": {
        "event_id": "test_event_current",
        "event_type": "im.message.receive_v1",
        "create_time": "1774125000000",
        "token": "test_token",
        "app_id": "test_app",
        "tenant_key": "test_tenant",
    },
    "event": {
        "message": {
            "message_id": "test_msg_current",
            "chat_id": "oc_test_chat_current",
            "chat_type": "p2p",
            "content": json.dumps({"text": "测试当前状态"}),
            "message_type": "text",
            "create_time": "1774125000000",
        },
        "sender": {
            "sender_id": {
                "open_id": "ou_test_user_current",
                "union_id": "on_test_user_current",
                "user_id": "test_user_current",
            },
            "sender_type": "user",
            "tenant_key": "test_tenant",
        },
    },
}

try:
    response = requests.post(webhook_url, json=test_message, timeout=10)
    print(f"   状态码: {response.status_code}")
    print(f"   响应: {response.text}")
except Exception as e:
    print(f"   错误: {e}")

print("\n3. 检查服务器日志...")
time.sleep(1)
try:
    with open("server.log", "r") as f:
        lines = f.readlines()
        print("   最后10行日志:")
        for line in lines[-10:]:
            print(f"   {line.strip()}")
except Exception as e:
    print(f"   读取日志错误: {e}")

print("\n4. 测试卡片点击响应...")
# 先创建一个session
session_test = {
    "schema": "2.0",
    "header": {
        "event_type": "im.message.receive_v1",
    },
    "event": {
        "message": {
            "message_id": "test_msg_for_session",
            "chat_id": "oc_chat_for_card",
            "message_type": "text",
            "content": json.dumps({"text": "创建测试session"}),
        },
        "sender": {
            "sender_id": {
                "open_id": "ou_user_for_card",
            },
        },
    },
}

try:
    session_response = requests.post(webhook_url, json=session_test, timeout=10)
    print(f"   创建session响应: {session_response.text}")

    # 解析响应获取session_id
    if session_response.status_code == 200:
        data = session_response.json()
        session_id = data.get("session_id")
        if session_id:
            print(f"   Session ID: {session_id}")

            # 现在测试卡片点击
            card_click = {
                "schema": "2.0",
                "header": {
                    "event_type": "im.message.receive_v1",
                },
                "event": {
                    "message": {
                        "message_id": "test_card_click",
                        "chat_id": "oc_chat_for_card",
                        "message_type": "interactive",
                        "content": json.dumps(
                            {
                                "value": json.dumps(
                                    {
                                        "action": "confirm",
                                        "session_id": session_id,
                                    }
                                )
                            }
                        ),
                    },
                    "sender": {
                        "sender_id": {
                            "open_id": "ou_user_for_card",
                        },
                    },
                },
            }

            card_response = requests.post(webhook_url, json=card_click, timeout=10)
            print(f"   卡片点击响应状态码: {card_response.status_code}")
            print(f"   卡片点击响应: {card_response.text}")

except Exception as e:
    print(f"   错误: {e}")

print("\n" + "=" * 60)
print("测试完成")
