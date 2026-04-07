#!/usr/bin/env python3
"""
快速创建测试session的简单脚本
"""

import asyncio
import sys
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from legacy.session_manager import get_session_manager


async def create_simple_test_session():
    """创建简单的测试session"""
    print("🚀 创建测试session...")

    # 获取session管理器
    manager = get_session_manager()

    # 创建测试session
    session = await manager.get_or_create_session(
        chat_id="test_chat_" + str(int(asyncio.get_event_loop().time())),
        user_id="test_user_001",
    )

    if not session:
        print("❌ 创建session失败")
        return None

    print("✅ Session创建成功!")
    print(f"   ID: {session.session_id}")
    print(f"   聊天: {session.chat_id}")
    print(f"   用户: {session.user_id}")
    print(f"   状态: {session.status}")

    # 添加示例消息
    await manager.add_message_to_session(
        session.session_id, "user", "这是一个测试消息，用于测试session功能。"
    )

    await manager.add_message_to_session(
        session.session_id, "assistant", "收到！这是一个测试回复。session功能正常。"
    )

    print("✅ 添加了2条测试消息")

    # 显示session信息
    session_dict = session.to_dict()
    print("\n📊 Session信息:")
    print(f"   创建时间: {session_dict['created_at']}")
    print(f"   更新时间: {session_dict['updated_at']}")
    print(f"   过期时间: {session_dict['expires_at']}")
    print(f"   消息数量: {session_dict['message_count']}")

    return session.session_id


async def list_all_sessions():
    """列出所有session"""
    print("\n📋 所有session列表:")
    print("=" * 60)

    manager = get_session_manager()
    sessions = await manager.list_sessions()

    if not sessions:
        print("没有找到任何session")
        return

    for i, sess in enumerate(sessions, 1):
        print(f"{i:2d}. {sess['session_id']}")
        print(f"     聊天: {sess['chat_id']}")
        print(f"     用户: {sess['user_id']}")
        print(f"     状态: {sess['status']}")
        print(f"     消息: {sess['message_count']}条")
        print()


async def main():
    """主函数"""
    try:
        # 创建测试session
        session_id = await create_simple_test_session()

        if session_id:
            # 列出所有session
            await list_all_sessions()

            print("\n🎉 测试完成！")
            print(f"测试session ID: {session_id}")
            print(f"session数据保存在: data/sessions/{session_id}.json")

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
