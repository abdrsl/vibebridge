#!/usr/bin/env python3
"""
简单命令行创建测试session
用法: python3 create_test_session_simple.py [chat_id] [user_id] [task_description]
"""

import asyncio
import os
import sys

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from legacy.session_manager import SessionStatus, get_session_manager


async def create_session(
    chat_id="test_chat", user_id="test_user", task_description="创建一个HTML页面"
):
    """创建session"""
    print(f"创建session: 聊天={chat_id}, 用户={user_id}, 任务={task_description}")

    manager = get_session_manager()

    # 创建session
    session = await manager.get_or_create_session(
        chat_id=chat_id,
        user_id=user_id,
    )

    # 添加消息
    await manager.add_message_to_session(
        session.session_id,
        "user",
        task_description,
        message_id=f"msg_{session.session_id}",
    )

    await manager.add_message_to_session(
        session.session_id,
        "assistant",
        f"好的，我会帮你{task_description}。请确认是否开始执行？",
        card_sent=True,
    )

    # 更新状态
    await manager.update_session(
        session.session_id,
        status=SessionStatus.CONFIRMED,
        task_id=f"task_{session.session_id}",
    )

    return session


async def list_sessions():
    """列出所有sessions"""
    manager = get_session_manager()
    sessions = await manager.list_sessions()
    return sessions


async def show_session(session_id):
    """显示session详情"""
    manager = get_session_manager()
    session = await manager.get_session(session_id)
    return session


def main():
    """主函数"""
    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help"]:
        print("用法:")
        print(
            "  python3 create_test_session_simple.py create [chat_id] [user_id] [task_description]"
        )
        print("  python3 create_test_session_simple.py list")
        print("  python3 create_test_session_simple.py show <session_id>")
        print("\n示例:")
        print(
            "  python3 create_test_session_simple.py create my_chat my_user '创建一个登录页面'"
        )
        print("  python3 create_test_session_simple.py list")
        print("  python3 create_test_session_simple.py show fs_1775480895_f5637439")
        return

    command = sys.argv[1]

    if command == "create":
        chat_id = sys.argv[2] if len(sys.argv) > 2 else "test_chat"
        user_id = sys.argv[3] if len(sys.argv) > 3 else "test_user"
        task_description = sys.argv[4] if len(sys.argv) > 4 else "创建一个HTML页面"

        session = asyncio.run(create_session(chat_id, user_id, task_description))

        print("\n✅ Session创建成功!")
        print(f"   Session ID: {session.session_id}")
        print(f"   聊天ID: {session.chat_id}")
        print(f"   用户ID: {session.user_id}")
        print(f"   状态: {session.status}")
        print(f"   任务描述: {task_description}")
        print(f"\n📁 Session文件: data/sessions/{session.session_id}.json")

    elif command == "list":
        sessions = asyncio.run(list_sessions())
        print(f"\n📊 当前所有sessions: {len(sessions)}个")
        print("=" * 80)
        for s in sessions:
            print(f"ID: {s['session_id']}")
            print(f"  状态: {s['status']}")
            print(f"  聊天: {s['chat_id']}")
            print(f"  用户: {s['user_id']}")
            print(f"  消息数: {s['message_count']}")
            print(f"  创建时间: {s['created_at']}")
            print("-" * 40)

    elif command == "show":
        if len(sys.argv) < 3:
            print("❌ 请提供session_id")
            return

        session_id = sys.argv[2]
        session = asyncio.run(show_session(session_id))

        if not session:
            print(f"❌ 找不到session: {session_id}")
            return

        print("\n📋 Session详情:")
        print(f"   ID: {session.session_id}")
        print(f"   聊天ID: {session.chat_id}")
        print(f"   用户ID: {session.user_id}")
        print(f"   状态: {session.status}")
        print(f"   任务ID: {session.current_task_id}")
        print(f"   创建时间: {session.created_at}")
        print(f"   更新时间: {session.updated_at}")
        print(f"   过期时间: {session.expires_at}")
        print(f"   消息数量: {len(session.messages)}")

        if session.messages:
            print("\n📨 消息历史:")
            for i, msg in enumerate(session.messages, 1):
                print(f"   {i}. [{msg.role}] {msg.content}")
                if msg.metadata:
                    print(f"      元数据: {msg.metadata}")

    else:
        print(f"❌ 未知命令: {command}")
        print("使用 -h 查看帮助")


if __name__ == "__main__":
    main()
