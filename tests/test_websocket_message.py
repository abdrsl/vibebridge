#!/usr/bin/env python3
"""
测试WebSocket模式下的消息接收
"""

import json
import time

import requests

webhook_url = "http://localhost:8000/feishu/webhook/opencode"


def send_test_message():
    """发送测试消息到webhook"""
    message_id = f"om_ws_test_{int(time.time())}"

    payload = {
        "schema": "2.0",
        "header": {
            "event_id": f"ws_test_{int(time.time())}",
            "event_type": "im.message.receive_v1",
            "create_time": str(int(time.time() * 1000)),
            "token": "test_token",
            "app_id": "cli_xxxxxxxxxxxxxxxx",
            "tenant_key": "REDACTED_TENANT_KEY",  # 真实tenant_key
        },
        "event": {
            "sender": {
                "sender_id": {
                    "open_id": "ou_REDACTED_OPEN_ID",  # 测试用户ID
                    "union_id": "on_test_user",
                    "user_id": "user_test",
                },
                "sender_type": "user",
                "tenant_key": "REDACTED_TENANT_KEY",
            },
            "message": {
                "message_id": message_id,
                "root_id": "",
                "parent_id": "",
                "create_time": str(int(time.time() * 1000)),
                "chat_id": "oc_REDACTED_CHAT_ID",  # 测试聊天ID
                "chat_type": "p2p",
                "message_type": "text",
                "content": json.dumps(
                    {"text": "test websocket message"}, ensure_ascii=False
                ),
                "mentions": [],
            },
        },
    }

    print("发送测试消息...")
    print(f"聊天ID: {payload['event']['message']['chat_id']}")
    print(f"用户ID: {payload['event']['sender']['sender_id']['open_id']}")

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        print(f"响应状态: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"响应内容: {json.dumps(result, indent=2)}")
            return result
        else:
            print(f"错误响应: {response.text}")
            return None
    except Exception as e:
        print(f"请求错误: {e}")
        return None


def check_websocket_status():
    """检查WebSocket状态"""
    print("\n检查WebSocket状态...")
    try:
        # 尝试访问状态端点
        status_resp = requests.get(
            "http://localhost:8000/feishu/websocket/status", timeout=5
        )
        print(f"WebSocket状态: {status_resp.status_code}")
        if status_resp.status_code == 200:
            status_data = status_resp.json()
            print(f"状态信息: {json.dumps(status_data, indent=2)}")
        else:
            print("WebSocket状态端点不存在或错误")
    except:
        print("WebSocket状态端点不可用")


if __name__ == "__main__":
    print("=== 测试WebSocket模式消息处理 ===")

    # 检查状态
    check_websocket_status()

    # 发送测试消息
    result = send_test_message()

    if result:
        print("\n✅ 测试消息发送成功")
        if result.get("ok"):
            print("消息已被WebSocket处理器接收")
        else:
            print(f"消息处理失败: {result.get('error', 'unknown')}")
    else:
        print("\n❌ 测试消息发送失败")
