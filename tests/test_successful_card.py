#!/usr/bin/env python3
"""
测试成功的卡片交互
"""

import json
import asyncio
from src.legacy.feishu_card_handler import process_feishu_webhook
from fastapi import BackgroundTasks
from src.legacy.session_manager import get_session_manager, SessionStatus


class MockBackgroundTasks:
    """模拟BackgroundTasks"""

    def __init__(self):
        self.tasks = []

    def add_task(self, func, *args, **kwargs):
        self.tasks.append((func, args, kwargs))

    async def run_all(self):
        """运行所有任务"""
        for func, args, kwargs in self.tasks:
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)


async def test_successful_card_action():
    """测试成功的卡片动作"""
    print("测试成功的卡片动作")
    print("=" * 60)

    background_tasks = MockBackgroundTasks()

    # 先创建一个测试session
    session_manager = get_session_manager()
    session = await session_manager.get_or_create_session(
        chat_id="chat_test_123", user_id="user_test_456"
    )
    # 添加初始消息
    await session_manager.add_message_to_session(session.session_id, "user", "测试任务")

    print(f"创建测试session: {session.session_id}")

    # 测试成功的确认动作
    print("\n1. 测试成功的确认动作")
    card_action_body = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "message": {
                "message_id": "msg_card_001",
                "chat_id": "chat_test_123",
                "message_type": "interactive",
                "content": json.dumps(
                    {
                        "value": json.dumps(
                            {
                                "action": "confirm",
                                "session_id": session.session_id,
                            }
                        )
                    }
                ),
            },
            "sender": {
                "sender_id": {
                    "open_id": "user_test_456",
                },
            },
        },
    }

    result = await process_feishu_webhook(card_action_body, background_tasks)
    print(f"   结果: {result}")
    print(f"   预期: {{}} (空对象)")

    # 测试成功的取消动作
    print("\n2. 测试成功的取消动作")

    # 创建另一个session
    session2 = await session_manager.get_or_create_session(
        chat_id="chat_test_123", user_id="user_test_456"
    )
    # 添加初始消息
    await session_manager.add_message_to_session(
        session2.session_id, "user", "测试取消任务"
    )

    cancel_action_body = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "message": {
                "message_id": "msg_card_002",
                "chat_id": "chat_test_123",
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
                    "open_id": "user_test_456",
                },
            },
        },
    }

    result2 = await process_feishu_webhook(cancel_action_body, background_tasks)
    print(f"   结果: {result2}")
    print(f"   预期: {{}} (空对象)")

    # 清理测试数据
    await session_manager.close_session(session.session_id, SessionStatus.COMPLETED)
    await session_manager.close_session(session2.session_id, SessionStatus.COMPLETED)

    print("\n" + "=" * 60)
    print("测试完成")


def main():
    """主函数"""
    asyncio.run(test_successful_card_action())


if __name__ == "__main__":
    main()
