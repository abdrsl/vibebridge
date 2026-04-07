#!/usr/bin/env python3
"""
测试真实的OpenCode实时显示功能
"""

import asyncio
import json
import time

import requests

# 服务器地址
webhook_url = "http://localhost:8000/feishu/webhook/opencode"


async def test_realtime_opencode():
    """测试OpenCode实时显示功能"""
    print("=== 测试OpenCode实时显示功能 ===")
    print(f"服务器: {webhook_url}")
    print()

    # 测试1: 发送一个真实的任务
    print("测试1: 发送OpenCode任务")
    print("-" * 40)

    # 创建一个完整的飞书webhook消息
    payload = {
        "schema": "2.0",
        "header": {
            "event_id": f"test_realtime_{int(time.time())}",
            "event_type": "im.message.receive_v1",
            "create_time": str(int(time.time() * 1000)),
            "token": "test_token",
            "app_id": "cli_xxxxxxxxxxxxxxxx",
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
                "message_id": f"om_realtime_{int(time.time())}",
                "root_id": "",
                "parent_id": "",
                "create_time": str(int(time.time() * 1000)),
                "chat_id": "oc_REDACTED_CHAT_ID",  # 测试聊天ID
                "chat_type": "p2p",
                "message_type": "text",
                "content": json.dumps(
                    {"text": "列出当前目录的文件和详细信息"}, ensure_ascii=False
                ),
                "mentions": [],
            },
        },
    }

    print(f"发送任务到聊天: {payload['event']['message']['chat_id']}")
    print(f"任务内容: {json.loads(payload['event']['message']['content'])['text']}")

    try:
        response = requests.post(webhook_url, json=payload, timeout=30)
        print(f"响应状态: {response.status_code}")
        print(f"响应内容: {response.text}")

        response_json = response.json()
        if response_json.get("ok"):
            session_id = response_json.get("session_id")
            status = response_json.get("status")
            print(f"Session ID: {session_id}")
            print(f"状态: {status}")

            if status == "pending_confirmation":
                print("✅ 任务已创建，等待用户确认")
                print("注意: 检查飞书消息查看确认卡片")
            elif status == "running":
                print("✅ 任务正在运行")
                print("注意: 检查飞书消息查看实时输出")
            else:
                print(f"❓ 未知状态: {status}")
        else:
            print(f"❌ 请求失败: {response_json.get('error', 'unknown error')}")

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback

        traceback.print_exc()

    print()

    # 测试2: 检查session状态
    print("测试2: 检查session状态")
    print("-" * 40)
    try:
        status_url = "http://localhost:8000/feishu/session/status"
        status_response = requests.get(status_url, timeout=10)
        print(f"状态响应: {status_response.status_code}")
        print(f"状态内容: {status_response.text}")
    except Exception as e:
        print(f"状态检查失败: {e}")


if __name__ == "__main__":
    asyncio.run(test_realtime_opencode())
