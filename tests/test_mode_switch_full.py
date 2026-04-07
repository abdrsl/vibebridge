#!/usr/bin/env python3
"""
测试完整的模式切换功能
"""

import json
import time

import requests

# 服务器地址
webhook_url = "http://localhost:8000/feishu/webhook/opencode"


def send_feishu_message(chat_id, text, message_id=None):
    """发送飞书消息到webhook"""
    if not message_id:
        message_id = f"om_test_{int(time.time())}"

    payload = {
        "schema": "2.0",
        "header": {
            "event_id": f"test_switch_{int(time.time())}",
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
                "message_id": message_id,
                "root_id": "",
                "parent_id": "",
                "create_time": str(int(time.time() * 1000)),
                "chat_id": chat_id,
                "chat_type": "p2p",
                "message_type": "text",
                "content": json.dumps({"text": text}, ensure_ascii=False),
                "mentions": [],
            },
        },
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=30)
        print(f"响应状态: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"响应内容: {json.dumps(result, ensure_ascii=False)}")
            return result
        else:
            print(f"错误响应: {response.text}")
            return None
    except Exception as e:
        print(f"请求错误: {e}")
        return None


def test_mode_switch():
    """测试模式切换功能"""
    print("=== 测试模式切换功能 ===")
    print(f"服务器: {webhook_url}")
    print("测试聊天ID: oc_REDACTED_CHAT_ID")
    print()

    # 删除session文件
    import os

    session_file = "data/sessions/fs_1775456902_dd137926.json"
    if os.path.exists(session_file):
        os.remove(session_file)
        print(f"已删除session文件: {session_file}")

    # 测试1: 发送"webhook模式"命令
    print("\n测试1: 发送'webhook模式'命令")
    print("-" * 40)
    result = send_feishu_message("oc_REDACTED_CHAT_ID", "webhook模式")

    if result and result.get("ok"):
        print("✅ 命令发送成功")
        print(f"   状态: {result.get('status')}")
        print(f"   action: {result.get('action')}")

        # 检查配置文件
        import json as json_module

        config_file = "config/settings.json"
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                config = json_module.load(f)
            print(f"   当前配置: {config}")

            if config.get("feishu_mode") == "webhook":
                print("✅ 配置已更新为webhook模式")
            else:
                print(f"⚠️  配置未更新: {config.get('feishu_mode')}")
    else:
        print("❌ 命令发送失败")

    # 等待2秒
    print("\n等待2秒...")
    time.sleep(2)

    # 测试2: 发送"websocket模式"命令
    print("\n测试2: 发送'websocket模式'命令")
    print("-" * 40)
    result = send_feishu_message("oc_REDACTED_CHAT_ID", "websocket模式")

    if result and result.get("ok"):
        print("✅ 命令发送成功")
        print(f"   状态: {result.get('status')}")
        print(f"   action: {result.get('action')}")

        # 检查配置文件
        import json as json_module

        config_file = "config/settings.json"
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                config = json_module.load(f)
            print(f"   当前配置: {config}")

            if config.get("feishu_mode") == "websocket":
                print("✅ 配置已更新为websocket模式")
            else:
                print(f"⚠️  配置未更新: {config.get('feishu_mode')}")
    else:
        print("❌ 命令发送失败")

    # 测试3: 发送简单OpenCode任务
    print("\n测试3: 发送简单OpenCode任务")
    print("-" * 40)
    result = send_feishu_message("oc_REDACTED_CHAT_ID", "列出文件")

    if result and result.get("ok"):
        print("✅ 任务发送成功")
        session_id = result.get("session_id")
        status = result.get("status")
        print(f"   session_id: {session_id}")
        print(f"   状态: {status}")

        if status == "pending_confirmation":
            print("   📋 需要用户确认")
            print("   请检查飞书消息查看确认卡片")
        elif status == "running":
            print("   🚀 任务正在执行")
            print("   请检查飞书消息查看实时输出")
        else:
            print(f"   ❓ 未知状态: {status}")
    else:
        print("❌ 任务发送失败")


if __name__ == "__main__":
    test_mode_switch()
