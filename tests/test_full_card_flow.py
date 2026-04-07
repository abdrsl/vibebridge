#!/usr/bin/env python3
"""
测试完整的卡片流程
"""

import asyncio
import json

from src.legacy.feishu_card_handler import process_feishu_webhook
from src.legacy.session_manager import SessionStatus, get_session_manager


class MockBackgroundTasks:
    """模拟BackgroundTasks"""

    def __init__(self):
        self.tasks = []

    def add_task(self, func, *args, **kwargs):
        self.tasks.append((func, args, kwargs))
        print(f"   后台任务添加: {func.__name__}")

        # 立即执行任务（模拟FastAPI行为）
        try:
            if asyncio.iscoroutinefunction(func):
                asyncio.create_task(func(*args, **kwargs))
            else:
                func(*args, **kwargs)
        except Exception as e:
            print(f"   任务执行错误: {e}")

    async def run_all(self):
        """运行所有任务"""
        for func, args, kwargs in self.tasks:
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)


async def test_full_card_flow():
    """测试完整的卡片流程"""
    print("测试完整的飞书卡片流程")
    print("=" * 60)

    background_tasks = MockBackgroundTasks()

    # 步骤1: 用户发送文本消息
    print("\n1. 用户发送文本消息:")
    text_message = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "message": {
                "message_id": "msg_001",
                "chat_id": "oc_chat_123",
                "message_type": "text",
                "content": json.dumps({"text": "请帮我创建一个HTML页面"}),
            },
            "sender": {
                "sender_id": {
                    "open_id": "ou_user_123",
                },
            },
        },
    }

    result1 = await process_feishu_webhook(text_message, background_tasks)
    print(f"   响应: {result1}")

    # 获取创建的session_id
    session_id = result1.get("session_id")
    if not session_id:
        print("   错误: 没有创建session")
        return

    print(f"   Session创建: {session_id}")

    # 步骤2: 用户点击确认卡片
    print("\n2. 用户点击确认卡片:")
    card_click = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "message": {
                "message_id": "msg_card_001",
                "chat_id": "oc_chat_123",
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
                    "open_id": "ou_user_123",
                },
            },
        },
    }

    result2 = await process_feishu_webhook(card_click, background_tasks)
    print(f"   响应: {result2}")
    print("   预期: {} (空对象)")

    # 步骤3: 用户点击取消卡片
    print("\n3. 用户点击取消卡片:")

    # 创建另一个session
    session_manager = get_session_manager()
    session2 = await session_manager.get_or_create_session(
        chat_id="oc_chat_123", user_id="ou_user_123"
    )
    await session_manager.add_message_to_session(
        session2.session_id, "user", "另一个测试任务"
    )

    cancel_click = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "message": {
                "message_id": "msg_card_002",
                "chat_id": "oc_chat_123",
                "message_type": "interactive",
                "content": json.dumps(
                    {
                        "value": json.dumps(
                            {
                                "action": "cancel",
                                "session_id": session2.session_id,
                            }
                        )
                    }
                ),
            },
            "sender": {
                "sender_id": {
                    "open_id": "ou_user_123",
                },
            },
        },
    }

    result3 = await process_feishu_webhook(cancel_click, background_tasks)
    print(f"   响应: {result3}")
    print("   预期: {} (空对象)")

    # 清理
    await session_manager.close_session(session_id, SessionStatus.COMPLETED)
    await session_manager.close_session(session2.session_id, SessionStatus.COMPLETED)

    print("\n" + "=" * 60)
    print("测试完成")

    print("\n✅ 总结:")
    print("1. 文本消息 → 创建session，返回session信息")
    print("2. 卡片确认点击 → 返回 {} (空对象)")
    print("3. 卡片取消点击 → 返回 {} (空对象)")
    print("\n📋 飞书错误码200340解决方案:")
    print("   - 卡片动作必须返回 {} 或 {'error': '...', 'code': 200340}")
    print("   - 必须在5秒内响应")
    print("   - 耗时操作使用后台任务")


def main():
    """主函数"""
    asyncio.run(test_full_card_flow())


if __name__ == "__main__":
    main()
