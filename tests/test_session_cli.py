#!/usr/bin/env python3
"""
测试session的CLI工具
用法:
  python3 test_session_cli.py create [chat_id] [user_id]
  python3 test_session_cli.py list
  python3 test_session_cli.py show <session_id>
  python3 test_session_cli.py add <session_id> <role> <message>
  python3 test_session_cli.py update <session_id> <status>
  python3 test_session_cli.py delete <session_id>
  python3 test_session_cli.py cleanup
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from legacy.session_manager import SessionStatus, get_session_manager


def print_session(session):
    """打印session信息"""
    if not session:
        print("❌ Session不存在")
        return

    print("\n📋 Session信息:")
    print(f"   ID: {session.session_id}")
    print(f"   聊天ID: {session.chat_id}")
    print(f"   用户ID: {session.user_id}")
    print(f"   状态: {session.status}")
    print(f"   当前任务: {session.current_task_id or '无'}")
    print(f"   创建时间: {session.created_at}")
    print(f"   更新时间: {session.updated_at}")
    print(f"   过期时间: {session.expires_at}")
    print(f"   是否过期: {'是' if session.is_expired() else '否'}")
    print(f"   消息数量: {len(session.messages)}")

    if session.messages:
        print("\n💬 最近消息:")
        for i, msg in enumerate(session.messages[-5:], 1):
            role = msg.role.ljust(10)
            content = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
            print(f"   {i}. [{role}] {content}")


async def cmd_create(args):
    """创建session命令"""
    manager = get_session_manager()

    chat_id = args.chat_id or f"test_chat_{int(asyncio.get_event_loop().time())}"
    user_id = args.user_id or "test_user_001"

    session = await manager.get_or_create_session(chat_id=chat_id, user_id=user_id)

    if session:
        print(f"✅ 创建session成功: {session.session_id}")
        print_session(session)
        return session.session_id
    else:
        print("❌ 创建session失败")
        return None


async def cmd_list(args):
    """列出session命令"""
    manager = get_session_manager()

    sessions = await manager.list_sessions(
        chat_id=args.chat_id,
        user_id=args.user_id,
        status=SessionStatus(args.status) if args.status else None,
    )

    if not sessions:
        print("📭 没有找到session")
        return

    print(f"📋 找到 {len(sessions)} 个session:")
    print("=" * 80)

    for i, sess in enumerate(sessions, 1):
        print(f"{i:3d}. {sess['session_id']}")
        print(f"     聊天: {sess['chat_id']}")
        print(f"     用户: {sess['user_id']}")
        print(f"     状态: {sess['status']}")
        print(f"     任务: {sess['current_task_id'] or '无'}")
        print(f"     消息: {sess['message_count']}条")
        print(f"     创建: {sess['created_at']:.0f}")
        print(f"     更新: {sess['updated_at']:.0f}")
        print()


async def cmd_show(args):
    """显示session详情命令"""
    manager = get_session_manager()

    session = await manager.get_session(args.session_id)
    print_session(session)


async def cmd_add(args):
    """添加消息命令"""
    manager = get_session_manager()

    success = await manager.add_message_to_session(
        args.session_id, args.role, args.message
    )

    if success:
        print("✅ 消息添加成功")

        # 显示更新后的session
        session = await manager.get_session(args.session_id)
        print_session(session)
    else:
        print("❌ 添加消息失败")


async def cmd_update(args):
    """更新session状态命令"""
    manager = get_session_manager()

    try:
        status = SessionStatus(args.status)
    except ValueError:
        print(f"❌ 无效的状态: {args.status}")
        print(f"   有效状态: {[s.value for s in SessionStatus]}")
        return

    success = await manager.update_session(
        args.session_id, status=status, task_id=args.task_id
    )

    if success:
        print(f"✅ Session状态更新为: {status.value}")

        # 显示更新后的session
        session = await manager.get_session(args.session_id)
        print_session(session)
    else:
        print("❌ 更新session失败")


async def cmd_delete(args):
    """删除session命令"""
    manager = get_session_manager()

    success = await manager.close_session(
        args.session_id,
        SessionStatus.COMPLETED if not args.force else SessionStatus.CANCELLED,
    )

    if success:
        print(f"✅ Session已删除: {args.session_id}")
    else:
        print("❌ 删除session失败")


async def cmd_cleanup(args):
    """清理过期session命令"""
    manager = get_session_manager()

    cleaned = await manager.cleanup_expired_sessions()
    print(f"🧹 清理了 {cleaned} 个过期session")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="测试session的CLI工具")
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # create 命令
    create_parser = subparsers.add_parser("create", help="创建session")
    create_parser.add_argument("chat_id", nargs="?", help="聊天ID")
    create_parser.add_argument("user_id", nargs="?", help="用户ID")

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出session")
    list_parser.add_argument("--chat-id", help="按聊天ID过滤")
    list_parser.add_argument("--user-id", help="按用户ID过滤")
    list_parser.add_argument("--status", help="按状态过滤")

    # show 命令
    show_parser = subparsers.add_parser("show", help="显示session详情")
    show_parser.add_argument("session_id", help="Session ID")

    # add 命令
    add_parser = subparsers.add_parser("add", help="添加消息到session")
    add_parser.add_argument("session_id", help="Session ID")
    add_parser.add_argument(
        "role", choices=["user", "assistant", "system"], help="消息角色"
    )
    add_parser.add_argument("message", help="消息内容")

    # update 命令
    update_parser = subparsers.add_parser("update", help="更新session状态")
    update_parser.add_argument("session_id", help="Session ID")
    update_parser.add_argument("status", help="新状态")
    update_parser.add_argument("--task-id", help="任务ID")

    # delete 命令
    delete_parser = subparsers.add_parser("delete", help="删除session")
    delete_parser.add_argument("session_id", help="Session ID")
    delete_parser.add_argument("--force", action="store_true", help="强制删除")

    # cleanup 命令
    cleanup_parser = subparsers.add_parser("cleanup", help="清理过期session")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 执行命令
    try:
        if args.command == "create":
            asyncio.run(cmd_create(args))
        elif args.command == "list":
            asyncio.run(cmd_list(args))
        elif args.command == "show":
            asyncio.run(cmd_show(args))
        elif args.command == "add":
            asyncio.run(cmd_add(args))
        elif args.command == "update":
            asyncio.run(cmd_update(args))
        elif args.command == "delete":
            asyncio.run(cmd_delete(args))
        elif args.command == "cleanup":
            asyncio.run(cmd_cleanup(args))
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
