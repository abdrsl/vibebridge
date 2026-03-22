#!/usr/bin/env python3
"""
测试真实的飞书卡片点击
"""

import json
import asyncio
from app.feishu_card_handler import process_feishu_webhook
from fastapi import BackgroundTasks


class MockBackgroundTasks:
    """模拟BackgroundTasks"""

    def __init__(self):
        self.tasks = []

    def add_task(self, func, *args, **kwargs):
        self.tasks.append((func, args, kwargs))
        print(f"   后台任务添加: {func.__name__}")

    async def run_all(self):
        """运行所有任务"""
        for func, args, kwargs in self.tasks:
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)


async def test_real_card_click():
    """测试真实的卡片点击"""
    print("测试真实的飞书卡片点击")
    print("=" * 60)

    background_tasks = MockBackgroundTasks()

    # 根据飞书文档，卡片交互的实际格式
    # 用户点击卡片按钮时，飞书会发送这样的webhook
    card_click_webhook = {
        "schema": "2.0",
        "header": {
            "event_id": "fce6f3a0-7b4c-4b3b-8f3a-0c7b4c3b8f3a",
            "event_type": "im.message.receive_v1",
            "create_time": "2025-03-22T04:00:00Z",
            "token": "test_token",
            "app_id": "test_app_id",
            "tenant_key": "test_tenant",
        },
        "event": {
            "sender": {
                "sender_id": {
                    "union_id": "on_123456",
                    "user_id": "user_123",
                    "open_id": "ou_123456",
                },
                "sender_type": "user",
                "tenant_key": "test_tenant",
            },
            "message": {
                "message_id": "om_123456",
                "root_id": None,
                "parent_id": None,
                "create_time": "2025-03-22T04:00:00Z",
                "chat_id": "oc_123456",
                "chat_type": "group",
                "message_type": "interactive",  # 注意：卡片交互的消息类型是interactive
                "content": json.dumps(
                    {
                        # 卡片交互的内容格式
                        "value": json.dumps(
                            {
                                "action": "confirm",
                                "session_id": "test_session_123",
                            }
                        )
                    }
                ),
                "mentions": [],
            },
        },
    }

    print("1. 模拟飞书卡片点击webhook:")
    print(f"   event_type: {card_click_webhook['header']['event_type']}")
    print(f"   message_type: {card_click_webhook['event']['message']['message_type']}")
    print(f"   content: {card_click_webhook['event']['message']['content']}")

    result = await process_feishu_webhook(card_click_webhook, background_tasks)
    print(f"\n   处理结果: {result}")
    print(f"   预期: {{}} (空对象) 或 {{'error': '...', 'code': 200340}}")

    # 测试另一个场景：卡片交互但value不是有效的JSON
    print("\n2. 测试无效的卡片交互:")
    invalid_card_webhook = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "message": {
                "message_id": "om_invalid",
                "chat_id": "oc_123456",
                "message_type": "interactive",
                "content": json.dumps({"value": "这不是有效的JSON"}),
            },
            "sender": {
                "sender_id": {
                    "open_id": "ou_123456",
                },
            },
        },
    }

    result2 = await process_feishu_webhook(invalid_card_webhook, background_tasks)
    print(f"   处理结果: {result2}")
    print(f"   预期: {{}} (空对象，因为无法解析但返回成功)")

    # 测试文本消息（不是卡片交互）
    print("\n3. 测试文本消息（不是卡片交互）:")
    text_message_webhook = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "message": {
                "message_id": "om_text",
                "chat_id": "oc_123456",
                "message_type": "text",  # 文本消息
                "content": json.dumps({"text": "请帮我创建一个HTML页面"}),
            },
            "sender": {
                "sender_id": {
                    "open_id": "ou_123456",
                },
            },
        },
    }

    result3 = await process_feishu_webhook(text_message_webhook, background_tasks)
    print(f"   处理结果: {result3}")
    print(f"   预期: 包含session_id和status的字典，不是空对象")

    print("\n" + "=" * 60)
    print("测试完成")


def main():
    """主函数"""
    asyncio.run(test_real_card_click())


if __name__ == "__main__":
    main()
