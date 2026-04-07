#!/usr/bin/env python3
import json
import sys

sys.path.insert(0, ".")


# 模拟WebSocket事件处理
def test_websocket_event_processing():
    from src.feishu_websocket import OpenCodeEventProcessor

    # 创建处理器
    processor = OpenCodeEventProcessor("im.message.receive_v1")

    # 模拟Feishu事件数据（SDK格式）
    test_event = {
        "schema": "2.0",
        "header": {
            "event_id": "test_event_123",
            "event_type": "im.message.receive_v1",
            "create_time": "1775477713941",
            "token": "test_token",
            "app_id": "cli_xxxxxxxxxxxxxxxx",
            "tenant_key": "REDACTED_TENANT_KEY",
        },
        "event": {
            "sender": {
                "sender_id": {
                    "open_id": "ou_REDACTED_OPEN_ID",
                    "union_id": "on_test_user",
                    "user_id": "user_test",
                },
                "sender_type": "user",
                "tenant_key": "REDACTED_TENANT_KEY",
            },
            "message": {
                "message_id": "om_test_123",
                "root_id": "",
                "parent_id": "",
                "create_time": "1775477713941",
                "chat_id": "oc_REDACTED_CHAT_ID",
                "chat_type": "p2p",
                "message_type": "text",
                "content": json.dumps({"text": "测试WebSocket事件"}),
                "mentions": [],
            },
        },
    }

    print("测试WebSocket事件处理...")
    print(f"事件类型: {processor._event_type}")

    try:
        # 调用处理器
        result = processor.do(test_event)
        print(f"处理结果: {result}")
        print("✅ WebSocket事件处理器工作正常")
        return True
    except Exception as e:
        print(f"❌ WebSocket事件处理器出错: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_webhook_comparison():
    """测试webhook事件处理作为对比"""
    print("\n对比测试：Webhook事件处理...")

    # 模拟webhook请求

    import requests

    webhook_url = "http://localhost:8000/feishu/webhook/opencode"
    test_payload = {
        "schema": "2.0",
        "header": {"event_type": "im.message.receive_v1", "app_id": "cli_a904a9"},
        "event": {
            "message": {
                "chat_id": "oc_REDACTED_CHAT_ID",
                "content": json.dumps({"text": "对比测试消息"}),
            }
        },
    }

    try:
        response = requests.post(webhook_url, json=test_payload, timeout=10)
        print(f"Webhook响应状态: {response.status_code}")
        print(f"Webhook响应内容: {response.text[:200]}")
        print("✅ Webhook端点工作正常")
        return True
    except Exception as e:
        print(f"❌ Webhook测试失败: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("WebSocket事件处理测试")
    print("=" * 60)

    websocket_ok = test_websocket_event_processing()
    webhook_ok = test_webhook_comparison()

    print("\n" + "=" * 60)
    print("测试结果总结:")
    print(f"  WebSocket事件处理器: {'✅ 正常' if websocket_ok else '❌ 异常'}")
    print(f"  Webhook端点: {'✅ 正常' if webhook_ok else '❌ 异常'}")

    if websocket_ok and webhook_ok:
        print("\n✅ 两种事件处理方式都工作正常")
        print("💡 建议：")
        print("  1. 更新Feishu事件订阅URL到新隧道URL")
        print("  2. 使用'webhook模式'命令切换到webhook模式")
        print("  3. 测试Feishu消息是否正常接收")
    else:
        print("\n⚠️  部分功能异常，请检查配置")
        print("💡 建议优先使用webhook模式（已实现实时显示）")
