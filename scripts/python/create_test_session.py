#!/usr/bin/env python3
"""
创建测试session的脚本
"""

import asyncio
import sys
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from legacy.session_manager import get_session_manager, SessionStatus


async def create_test_session():
    """创建测试session"""
    print("创建测试session...")
    print("=" * 60)

    # 获取session管理器
    manager = get_session_manager()

    # 创建测试session
    session = await manager.get_or_create_session(
        chat_id="test_chat_001", user_id="test_user_001"
    )

    if not session:
        print("❌ 创建session失败")
        return

    print(f"✅ 创建session成功:")
    print(f"   Session ID: {session.session_id}")
    print(f"   聊天ID: {session.chat_id}")
    print(f"   用户ID: {session.user_id}")
    print(f"   状态: {session.status}")
    print(f"   创建时间: {session.created_at}")
    print(f"   过期时间: {session.expires_at}")

    # 添加测试消息
    print("\n添加测试消息...")
    await manager.add_message_to_session(
        session.session_id, "user", "请帮我创建一个简单的Python脚本"
    )

    await manager.add_message_to_session(
        session.session_id,
        "assistant",
        "好的，我会帮你创建一个Python脚本。你想要实现什么功能？",
    )

    await manager.add_message_to_session(
        session.session_id, "user", "我想创建一个计算器程序，支持加减乘除"
    )

    # 更新session状态
    print("\n更新session状态...")
    await manager.update_session(
        session.session_id, status=SessionStatus.RUNNING, task_id="calc_task_001"
    )

    # 获取更新后的session
    updated_session = await manager.get_session(session.session_id)
    if updated_session:
        print(f"✅ Session状态已更新:")
        print(f"   状态: {updated_session.status}")
        print(f"   当前任务ID: {updated_session.current_task_id}")
        print(f"   消息数量: {len(updated_session.messages)}")

        # 显示消息历史
        print("\n消息历史:")
        for i, msg in enumerate(updated_session.messages[-3:], 1):
            print(f"  {i}. [{msg.role}] {msg.content[:50]}...")

    # 列出所有session
    print("\n列出所有session...")
    all_sessions = await manager.list_sessions()
    print(f"总session数量: {len(all_sessions)}")

    for i, sess in enumerate(all_sessions[:5], 1):
        print(f"  {i}. {sess['session_id']} - {sess['status']} - {sess['chat_id']}")

    print("\n" + "=" * 60)
    print("测试完成！")

    return session.session_id


async def test_session_operations(session_id: str):
    """测试session操作"""
    print(f"\n测试session操作 (ID: {session_id})...")
    print("=" * 60)

    manager = get_session_manager()

    # 1. 获取session
    session = await manager.get_session(session_id)
    if session:
        print(f"✅ 获取session成功")
        print(f"   状态: {session.status}")
        print(f"   消息数量: {len(session.messages)}")
    else:
        print("❌ 获取session失败")
        return

    # 2. 添加更多消息
    print("\n添加更多消息...")
    await manager.add_message_to_session(
        session_id,
        "assistant",
        "我已经创建了一个计算器程序，支持加减乘除运算。这是代码:",
        code_type="python",
    )

    await manager.add_message_to_session(
        session_id, "user", "谢谢！能再添加一个平方根功能吗？"
    )

    # 3. 获取对话历史
    print("\n获取对话历史...")
    history = session.get_conversation_history(max_messages=5)
    print(f"最近 {len(history)} 条消息:")
    for i, msg in enumerate(history, 1):
        role = msg["role"].ljust(10)
        content = (
            msg["content"][:60] + "..." if len(msg["content"]) > 60 else msg["content"]
        )
        print(f"  {i}. [{role}] {content}")

    # 4. 检查是否过期
    print(f"\n检查session是否过期: {'是' if session.is_expired() else '否'}")

    # 5. 续期session
    print("\n续期session...")
    session.renew(duration=7200)  # 2小时
    print(f"新的过期时间: {session.expires_at}")

    # 6. 转换为字典
    session_dict = session.to_dict()
    print(f"\nSession字典表示:")
    print(f"  Session ID: {session_dict['session_id']}")
    print(f"  状态: {session_dict['status']}")
    print(f"  消息数量: {session_dict['message_count']}")

    print("\n" + "=" * 60)
    print("session操作测试完成！")


async def cleanup_test_sessions():
    """清理测试session"""
    print("\n清理测试session...")
    print("=" * 60)

    manager = get_session_manager()

    # 列出所有session
    all_sessions = await manager.list_sessions()
    print(f"清理前session数量: {len(all_sessions)}")

    # 关闭测试session
    test_sessions = [s for s in all_sessions if s["chat_id"] == "test_chat_001"]
    closed_count = 0

    for sess in test_sessions:
        success = await manager.close_session(
            sess["session_id"], SessionStatus.COMPLETED
        )
        if success:
            closed_count += 1
            print(f"  ✅ 关闭session: {sess['session_id']}")
        else:
            print(f"  ❌ 关闭session失败: {sess['session_id']}")

    # 清理过期session
    cleaned = await manager.cleanup_expired_sessions()
    print(f"清理过期session数量: {cleaned}")

    # 再次列出
    remaining = await manager.list_sessions()
    print(f"清理后session数量: {len(remaining)}")

    print("\n" + "=" * 60)
    print("清理完成！")


async def main():
    """主函数"""
    print("测试Session管理器")
    print("=" * 60)

    try:
        # 创建测试session
        session_id = await create_test_session()

        if session_id:
            # 测试session操作
            await test_session_operations(session_id)

        # 清理测试session（可选）- 在非交互式环境中默认保留
        print("\n测试session已创建并保留。")
        print("如需清理，请运行: python3 create_test_session.py --cleanup")

        print("\n所有测试完成！")

    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
