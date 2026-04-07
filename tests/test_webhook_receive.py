#!/usr/bin/env python3
"""
测试飞书webhook接收功能
"""

import json
import time

import requests


def test_webhook_receive():
    print("测试飞书webhook接收功能")
    print("=" * 60)

    webhook_url = "http://127.0.0.1:8000/feishu/webhook/opencode"

    # 测试1: URL验证请求
    print("\n1. 测试URL验证请求:")
    challenge_data = {"challenge": "test_challenge_123", "type": "url_verification"}

    try:
        response = requests.post(webhook_url, json=challenge_data, timeout=5)
        print(f"   状态码: {response.status_code}")
        print(f"   响应: {response.text}")
        expected = {"challenge": "test_challenge_123"}
        if response.json() == expected:
            print("   ✅ URL验证通过")
        else:
            print("   ❌ URL验证失败")
    except Exception as e:
        print(f"   错误: {e}")

    # 测试2: 文本消息webhook
    print("\n2. 测试文本消息webhook:")
    text_message = {
        "schema": "2.0",
        "header": {
            "event_id": "test_event_webhook",
            "event_type": "im.message.receive_v1",
            "create_time": "1774127000000",
            "token": "test_token",
            "app_id": "test_app",
            "tenant_key": "test_tenant",
        },
        "event": {
            "message": {
                "message_id": "test_msg_webhook",
                "chat_id": "oc_test_chat_webhook",
                "chat_type": "p2p",
                "content": json.dumps({"text": "测试webhook接收功能"}),
                "message_type": "text",
                "create_time": "1774127000000",
            },
            "sender": {
                "sender_id": {
                    "open_id": "ou_test_user_webhook",
                    "union_id": "on_test_user_webhook",
                    "user_id": "test_user_webhook",
                },
                "sender_type": "user",
                "tenant_key": "test_tenant",
            },
        },
    }

    try:
        response = requests.post(webhook_url, json=text_message, timeout=10)
        print(f"   状态码: {response.status_code}")
        print(f"   响应: {response.text}")

        if response.status_code == 200:
            data = response.json()
            if data.get("ok") and data.get("session_id"):
                print(f"   ✅ Webhook接收成功，创建session: {data['session_id']}")
            else:
                print("   ❌ Webhook接收但未创建session")
        else:
            print("   ❌ Webhook接收失败")
    except Exception as e:
        print(f"   错误: {e}")

    # 测试3: 卡片交互webhook
    print("\n3. 测试卡片交互webhook:")

    # 先创建一个session
    session_message = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "message": {
                "message_id": "test_msg_for_card",
                "chat_id": "oc_chat_card_test",
                "message_type": "text",
                "content": json.dumps({"text": "创建测试session用于卡片点击"}),
            },
            "sender": {
                "sender_id": {
                    "open_id": "ou_user_card_test",
                },
            },
        },
    }

    try:
        session_response = requests.post(webhook_url, json=session_message, timeout=10)
        if session_response.status_code == 200:
            session_data = session_response.json()
            session_id = session_data.get("session_id")

            if session_id:
                print(f"   Session创建成功: {session_id}")

                # 测试卡片点击
                card_click = {
                    "schema": "2.0",
                    "header": {
                        "event_type": "im.message.receive_v1",
                    },
                    "event": {
                        "message": {
                            "message_id": "test_card_click_webhook",
                            "chat_id": "oc_chat_card_test",
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
                                "open_id": "ou_user_card_test",
                            },
                        },
                    },
                }

                card_response = requests.post(webhook_url, json=card_click, timeout=10)
                print(f"   卡片点击状态码: {card_response.status_code}")
                print(f"   卡片点击响应: {card_response.text}")

                if card_response.status_code == 200:
                    card_data = card_response.text
                    if card_data == "{}" or card_data.strip() == "":
                        print("   ✅ 卡片点击返回空对象（正确）")
                    else:
                        print(f"   ❓ 卡片点击返回: {card_data}")
                else:
                    print("   ❌ 卡片点击失败")
            else:
                print("   ❌ 未获取到session_id")
        else:
            print(f"   ❌ Session创建失败: {session_response.status_code}")
    except Exception as e:
        print(f"   错误: {e}")

    print("\n" + "=" * 60)
    print("检查服务器日志...")
    time.sleep(1)
    try:
        with open("server.log", "r") as f:
            lines = f.readlines()
            print("   最近相关日志:")
            for line in lines[-15:]:
                if "Webhook" in line or "Session" in line or "Feishu" in line:
                    print(f"   {line.strip()}")
    except Exception as e:
        print(f"   读取日志错误: {e}")

    print("\n" + "=" * 60)
    print("测试完成")


if __name__ == "__main__":
    test_webhook_receive()
