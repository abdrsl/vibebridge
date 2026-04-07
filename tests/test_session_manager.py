#!/usr/bin/env python3
"""
测试Session管理器功能
"""

import asyncio
import json

from src.legacy.feishu_webhook_handler import (
    handle_card_action,
    handle_feishu_message,
    handle_session_cancel,
    handle_session_status,
)
from src.legacy.session_manager import SessionStatus, get_session_manager


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


async def test_session_manager():
    """测试Session管理器"""
    print("测试Session管理器")
    print("=" * 60)

    manager = get_session_manager()

    # 1. 创建session
    session = await manager.get_or_create_session(
        chat_id="test_chat_123",
        user_id="test_user_456",
    )

    print(f"1. 创建session: {session.session_id}")
    print(f"   状态: {session.status}")
    print(f"   聊天ID: {session.chat_id}")
    print(f"   用户ID: {session.user_id}")

    # 2. 添加消息
    await manager.add_message_to_session(
        session.session_id,
        "user",
        "请帮我创建一个HTML页面",
        message_id="msg_001",
    )

    await manager.add_message_to_session(
        session.session_id,
        "assistant",
        "好的，我会帮你创建一个漂亮的HTML页面。请确认是否开始执行？",
        card_sent=True,
    )

    print("\n2. 添加消息后:")
    print(f"   消息数量: {len(session.messages)}")
    print(f"   最后消息: {session.messages[-1].content[:50]}...")

    # 3. 更新session状态
    await manager.update_session(
        session.session_id,
        status=SessionStatus.CONFIRMED,
        task_id="task_123",
    )

    updated = await manager.get_session(session.session_id)
    print("\n3. 更新状态后:")
    print(f"   状态: {updated.status}")
    print(f"   任务ID: {updated.current_task_id}")

    # 4. 列出sessions
    sessions = await manager.list_sessions(chat_id="test_chat_123")
    print("\n4. 列出sessions:")
    print(f"   数量: {len(sessions)}")
    for s in sessions:
        print(f"   - {s['session_id']}: {s['status']}")

    # 5. 关闭session
    success = await manager.close_session(
        session.session_id,
        SessionStatus.COMPLETED,
    )
    print("\n5. 关闭session:")
    print(f"   成功: {success}")

    # 6. 清理过期session
    cleaned = await manager.cleanup_expired_sessions()
    print("\n6. 清理过期session:")
    print(f"   清理数量: {cleaned}")

    print("\n" + "=" * 60)
    print("Session管理器测试完成")


async def test_webhook_handler():
    """测试Webhook处理器"""
    print("\n测试Webhook处理器")
    print("=" * 60)

    background_tasks = MockBackgroundTasks()

    # 模拟飞书消息事件
    test_event = {
        "message": {
            "message_id": "msg_test_001",
            "chat_id": "test_chat_789",
            "content": json.dumps({"text": "请帮我创建一个个人网页"}),
        },
        "sender": {
            "sender_id": {
                "open_id": "test_user_999",
            },
        },
    }

    print("1. 处理新消息（应该创建新session并发送确认卡片）")
    result = await handle_feishu_message(test_event, background_tasks)
    print(f"   结果: {result}")
    print(f"   后台任务数量: {len(background_tasks.tasks)}")

    # 运行后台任务
    await background_tasks.run_all()

    # 2. 测试session状态查询
    print("\n2. 测试session状态查询")
    status_result = await handle_session_status(
        "test_chat_789",
        "test_user_999",
        background_tasks,
    )
    print(f"   结果: {status_result}")

    # 3. 测试卡片动作处理
    print("\n3. 测试卡片动作处理（确认执行）")
    if "session_id" in result:
        action_result = await handle_card_action(
            {
                "action": "confirm",
                "session_id": result["session_id"],
            },
            "test_chat_789",
            "test_user_999",
            background_tasks,
        )
        print(f"   结果: {action_result}")

    # 4. 测试取消
    print("\n4. 测试session取消")
    cancel_result = await handle_session_cancel(
        "test_chat_789",
        "test_user_999",
        background_tasks,
    )
    print(f"   结果: {cancel_result}")

    print("\n" + "=" * 60)
    print("Webhook处理器测试完成")


async def test_integration_flow():
    """测试完整集成流程"""
    print("\n测试完整集成流程")
    print("=" * 60)

    manager = get_session_manager()
    background_tasks = MockBackgroundTasks()

    # 模拟用户交互流程
    print("模拟用户交互流程:")
    print("1. 用户发送消息 → 创建session并发送确认卡片")

    # 第一次消息
    event1 = {
        "message": {
            "message_id": "msg_flow_001",
            "chat_id": "chat_flow_123",
            "content": json.dumps({"text": "创建一个登录页面"}),
        },
        "sender": {
            "sender_id": {
                "open_id": "user_flow_456",
            },
        },
    }

    result1 = await handle_feishu_message(event1, background_tasks)
    print(
        f"   结果: session_id={result1.get('session_id')}, status={result1.get('status')}"
    )

    # 模拟用户确认
    if "session_id" in result1:
        print("\n2. 用户确认执行 → 开始OpenCode任务")

        action_result = await handle_card_action(
            {
                "action": "confirm",
                "session_id": result1["session_id"],
            },
            "chat_flow_123",
            "user_flow_456",
            background_tasks,
        )
        print(f"   结果: {action_result}")

        # 检查session状态
        session = await manager.get_session(result1["session_id"])
        print(f"   Session状态: {session.status if session else 'None'}")

        # 模拟任务完成后的新消息
        print("\n3. 任务完成后用户发送新消息 → 询问是否继续")

        # 先更新session状态为完成
        if session:
            await manager.update_session(
                session.session_id,
                status=SessionStatus.COMPLETED,
            )

        event2 = {
            "message": {
                "message_id": "msg_flow_002",
                "chat_id": "chat_flow_123",
                "content": json.dumps({"text": "再帮我添加一个注册页面"}),
            },
            "sender": {
                "sender_id": {
                    "open_id": "user_flow_456",
                },
            },
        }

        result2 = await handle_feishu_message(event2, background_tasks)
        print(f"   结果: status={result2.get('status')}")

        # 模拟用户选择继续
        print("\n4. 用户选择继续当前session")

        continue_result = await handle_card_action(
            {
                "action": "continue",
                "session_id": result1["session_id"],
            },
            "chat_flow_123",
            "user_flow_456",
            background_tasks,
        )
        print(f"   结果: {continue_result}")

    print("\n" + "=" * 60)
    print("集成流程测试完成")


def main():
    """主函数"""
    print("OpenCode Session管理功能测试套件")
    print("=" * 60)

    # 运行测试
    asyncio.run(test_session_manager())
    asyncio.run(test_webhook_handler())
    asyncio.run(test_integration_flow())

    print("\n" + "=" * 60)
    print("所有测试完成！")

    # 显示功能总结
    print("\n功能总结:")
    print("✅ 1. Session状态管理")
    print("   - 创建、获取、更新、关闭session")
    print("   - 消息历史记录")
    print("   - 自动过期清理")

    print("\n✅ 2. 交互式确认流程")
    print("   - 新任务需要用户确认")
    print("   - 卡片按钮交互")
    print("   - 继续/新建/取消选择")

    print("\n✅ 3. Session状态查询")
    print("   - 查看当前session状态")
    print("   - 管理运行中的任务")

    print("\n✅ 4. 完整集成")
    print("   - 与OpenCode任务集成")
    print("   - 与飞书消息集成")
    print("   - 后台任务管理")

    print("\n使用说明:")
    print("1. 用户发送消息 → 创建session并发送确认卡片")
    print("2. 用户确认 → 开始执行OpenCode任务")
    print("3. 任务完成后 → session状态更新")
    print("4. 用户再次发送消息 → 询问是否继续当前session")
    print("5. 用户选择 → 继续或开始新session")


if __name__ == "__main__":
    main()
