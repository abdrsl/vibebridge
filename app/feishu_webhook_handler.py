"""
飞书Webhook处理器 - 支持session管理的消息处理
"""

import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import BackgroundTasks

from app.feishu_client import (
    feishu_client,
    build_start_card,
    build_progress_card,
    build_result_card,
    build_error_card,
    build_help_card,
    build_confirmation_card,
    build_session_continue_card,
    build_session_status_card,
)
from app.opencode_integration import opencode_manager, TaskStatus
from app.session_manager import get_session_manager, SessionStatus


async def handle_feishu_webhook(
    body: Dict[str, Any],
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """
    处理飞书webhook请求

    Args:
        body: 飞书webhook请求体
        background_tasks: FastAPI后台任务

    Returns:
        处理结果
    """
    # 支持飞书事件订阅 v1 和 v2 格式
    schema = body.get("schema", "")
    event = {}
    event_type = ""

    if schema == "2.0":
        # v2 格式: {"schema":"2.0","header":{...},"event":{...}}
        header = body.get("header", {})
        event_type = header.get("event_type", "")
        event = body.get("event", {})
    else:
        # v1 格式: {"event":{...}} 或简化格式 {"event_type":...,"event":...}
        event = body.get("event", {})
        event_type = body.get("event_type", "")

    if event_type == "im.message.receive_v1":
        return await handle_feishu_message(event, background_tasks)

    return {
        "ok": True,
        "skipped": True,
        "reason": f"Event type {event_type} not handled",
    }


async def handle_feishu_message(
    event: Dict[str, Any],
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """处理飞书消息"""
    message = event.get("message", {})
    sender = event.get("sender", {})
    content_str = message.get("content", "{}")

    try:
        content_obj = json.loads(content_str)
    except json.JSONDecodeError:
        content_obj = {}

    text = content_obj.get("text", "").strip()
    chat_id = message.get("chat_id", "")
    sender_id = sender.get("sender_id", {}).get("open_id", "unknown")

    if not text:
        # 在后台发送提示消息，立即返回响应
        background_tasks.add_task(
            feishu_client.send_text_message,
            chat_id,
            "🤖 请发送你要完成的开发任务，我会帮你处理！",
        )
        return {"ok": True, "skipped": True, "reason": "Empty message"}

    # 检查是否是特殊命令
    if text.lower() in ["help", "帮助", "/help"]:
        # 在后台发送帮助卡片，立即返回响应
        help_card = build_help_card()
        background_tasks.add_task(
            feishu_client.send_interactive_card, chat_id, help_card
        )
        return {"ok": True, "handled": True, "action": "help"}

    # 检查是否是session操作
    if text.lower() in ["status", "状态", "/status"]:
        return await handle_session_status(chat_id, sender_id, background_tasks)

    if text.lower() in ["cancel", "取消", "/cancel"]:
        return await handle_session_cancel(chat_id, sender_id, background_tasks)

    # 获取或创建session
    session_manager = get_session_manager()
    session = await session_manager.get_or_create_session(chat_id, sender_id)

    if not session:
        return {"ok": True, "error": "Failed to create session"}

    # 添加用户消息到session
    await session_manager.add_message_to_session(
        session.session_id,
        "user",
        text,
        message_id=message.get("message_id"),
    )

    # 根据session状态处理
    if session.status == SessionStatus.PENDING:
        # 新session，发送确认卡片
        confirmation_card = build_confirmation_card(
            session_id=session.session_id,
            user_message=text,
        )

        print(f"[Session] Sending confirmation card for session {session.session_id}")
        print(f"[Session] Card will be sent to chat_id: {chat_id}")

        background_tasks.add_task(
            feishu_client.send_interactive_card,
            chat_id,
            confirmation_card,
        )

        # 更新session状态为等待确认
        await session_manager.update_session(
            session.session_id,
            status=SessionStatus.PENDING,
        )

        return {
            "ok": True,
            "session_id": session.session_id,
            "status": "pending_confirmation",
        }

    elif session.status == SessionStatus.CONFIRMED:
        # 用户已确认，开始执行任务
        return await start_opencode_task(session, text, chat_id, background_tasks)

    elif session.status == SessionStatus.RUNNING:
        # 任务正在执行中，提示用户等待
        background_tasks.add_task(
            feishu_client.send_text_message,
            chat_id,
            "⏳ 当前有任务正在执行中，请等待完成后再发送新任务。",
        )
        return {
            "ok": True,
            "session_id": session.session_id,
            "status": "already_running",
        }

    elif session.status in [
        SessionStatus.COMPLETED,
        SessionStatus.FAILED,
        SessionStatus.CANCELLED,
    ]:
        # 之前的任务已完成/失败/取消，询问是否继续
        previous_task = (
            session.messages[-2].content if len(session.messages) >= 2 else "未知任务"
        )

        continue_card = build_session_continue_card(
            session_id=session.session_id,
            previous_task=previous_task,
            user_message=text,
        )

        background_tasks.add_task(
            feishu_client.send_interactive_card,
            chat_id,
            continue_card,
        )

        return {
            "ok": True,
            "session_id": session.session_id,
            "status": "awaiting_continuation_choice",
        }

    else:
        # 未知状态，重置session
        await session_manager.update_session(
            session.session_id,
            status=SessionStatus.PENDING,
        )

        confirmation_card = build_confirmation_card(
            session_id=session.session_id,
            user_message=text,
        )

        background_tasks.add_task(
            feishu_client.send_interactive_card,
            chat_id,
            confirmation_card,
        )

        return {
            "ok": True,
            "session_id": session.session_id,
            "status": "reset_to_pending",
        }


async def start_opencode_task(
    session,
    user_message: str,
    chat_id: str,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """开始OpenCode任务"""
    # 创建OpenCode任务
    task_id = await opencode_manager.create_task(
        user_message=user_message,
        feishu_chat_id=chat_id,
    )

    # 更新session状态和任务ID
    session_manager = get_session_manager()
    await session_manager.update_session(
        session.session_id,
        status=SessionStatus.RUNNING,
        task_id=task_id,
    )

    # 添加助手消息
    await session_manager.add_message_to_session(
        session.session_id,
        "assistant",
        f"开始执行任务: {user_message[:50]}...",
        task_id=task_id,
    )

    # 在后台执行任务
    background_tasks.add_task(
        run_opencode_with_session,
        task_id,
        session.session_id,
        chat_id,
        True,
    )

    return {
        "ok": True,
        "session_id": session.session_id,
        "task_id": task_id,
        "status": "started",
    }


async def run_opencode_with_session(
    task_id: str,
    session_id: str,
    chat_id: str,
    notify: bool = True,
):
    """使用session运行OpenCode任务"""
    print(f"[Session] Starting task {task_id} for session {session_id}")

    session_manager = get_session_manager()

    try:
        if notify:
            print(f"[Session] Sending start card to {chat_id}")
            task = await opencode_manager.get_task(task_id)
            if task:
                start_card = build_start_card(task_id, task.user_message)
                result = await feishu_client.send_interactive_card(chat_id, start_card)
                print(f"[Session] Start card result: {result}")

        # 只收集事件，不实时发送
        final_result = None
        error_result = None

        async for event in opencode_manager.run_opencode(task_id):
            event_type = event.get("type", "")
            content = event.get("content", "")
            print(f"[Session] Event: {event_type} - {content[:50]}...")

            if event_type == "done":
                final_result = content
            elif event_type == "error":
                error_result = content

        # 任务完成后更新session状态
        if final_result:
            await session_manager.update_session(
                session_id,
                status=SessionStatus.COMPLETED,
            )

            # 添加完成消息
            await session_manager.add_message_to_session(
                session_id,
                "assistant",
                f"任务完成: {final_result[:100]}...",
                task_id=task_id,
                result_type="completed",
            )

            if notify:
                print(f"[Session] Building result card for session {session_id}")
                task = await opencode_manager.get_task(task_id)
                if task:
                    final_card = build_result_card(
                        task_id, task.user_message, task.output_lines, final_result
                    )
                    result = await feishu_client.send_interactive_card(
                        chat_id, final_card
                    )
                    print(f"[Session] Result card sent: {result}")

        elif error_result:
            await session_manager.update_session(
                session_id,
                status=SessionStatus.FAILED,
            )

            # 添加失败消息
            await session_manager.add_message_to_session(
                session_id,
                "assistant",
                f"任务失败: {error_result[:100]}",
                task_id=task_id,
                result_type="failed",
            )

            if notify:
                print(f"[Session] Building error card for session {session_id}")
                card = build_error_card(task_id, error_result)
                result = await feishu_client.send_interactive_card(chat_id, card)
                print(f"[Session] Error card sent: {result}")

    except Exception as e:
        print(f"[Session] Error: {e}")
        import traceback

        traceback.print_exc()

        # 更新session状态为失败
        await session_manager.update_session(
            session_id,
            status=SessionStatus.FAILED,
        )


async def handle_session_status(
    chat_id: str,
    user_id: str,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """处理session状态查询"""
    session_manager = get_session_manager()

    # 获取用户的活跃session
    sessions = await session_manager.list_sessions(
        chat_id=chat_id,
        user_id=user_id,
    )

    if not sessions:
        background_tasks.add_task(
            feishu_client.send_text_message,
            chat_id,
            "📭 当前没有活跃的任务session。",
        )
        return {"ok": True, "has_sessions": False}

    # 发送状态卡片
    for session_info in sessions:
        status_card = build_session_status_card(
            session_id=session_info["session_id"],
            status=session_info["status"],
            task_description=session_info.get("metadata", {}).get(
                "last_task", "未知任务"
            ),
            progress=f"创建时间: {datetime.fromtimestamp(session_info['created_at']).strftime('%H:%M:%S')}",
            actions_available=True,
        )

        background_tasks.add_task(
            feishu_client.send_interactive_card,
            chat_id,
            status_card,
        )

    return {"ok": True, "has_sessions": True, "count": len(sessions)}


async def handle_session_cancel(
    chat_id: str,
    user_id: str,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """处理session取消"""
    session_manager = get_session_manager()

    # 获取用户的活跃session
    sessions = await session_manager.list_sessions(
        chat_id=chat_id,
        user_id=user_id,
        status=SessionStatus.RUNNING,
    )

    if not sessions:
        background_tasks.add_task(
            feishu_client.send_text_message,
            chat_id,
            "📭 当前没有正在运行的任务。",
        )
        return {"ok": True, "cancelled": False}

    # 取消所有运行中的session
    cancelled_count = 0
    for session_info in sessions:
        success = await session_manager.close_session(
            session_info["session_id"],
            SessionStatus.CANCELLED,
        )
        if success:
            cancelled_count += 1

            # 如果有对应的OpenCode任务，尝试中止
            task_id = session_info.get("current_task_id")
            if task_id:
                try:
                    task = await opencode_manager.get_task(task_id)
                    if task and task.process and task.process.poll() is None:
                        task.process.terminate()
                        await opencode_manager.update_task(
                            task_id,
                            status=TaskStatus.FAILED,
                            error="Task cancelled by user",
                        )
                except Exception as e:
                    print(f"[Session] Error cancelling task {task_id}: {e}")

    background_tasks.add_task(
        feishu_client.send_text_message,
        chat_id,
        f"✅ 已取消 {cancelled_count} 个运行中的任务。",
    )

    return {"ok": True, "cancelled": True, "count": cancelled_count}


async def start_opencode_task_in_background(
    session,
    user_message: str,
    chat_id: str,
    background_tasks: BackgroundTasks,
):
    """在后台开始OpenCode任务（用于卡片交互立即响应）"""
    await start_opencode_task(session, user_message, chat_id, background_tasks)


async def handle_card_action(
    action_data: Dict[str, Any],
    chat_id: str,
    user_id: str,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """
    处理卡片按钮动作

    Args:
        action_data: 动作数据
        chat_id: 群聊ID
        user_id: 用户ID
        background_tasks: 后台任务

    Returns:
        处理结果
    """
    action = action_data.get("action")
    session_id = action_data.get("session_id")

    if not action or not session_id:
        return {"ok": False, "error": "Missing action or session_id", "action": "error"}

    session_manager = get_session_manager()
    session = await session_manager.get_session(session_id)

    if not session:
        return {"ok": False, "error": "Session not found", "action": "error"}

    # 验证用户权限
    if session.user_id != user_id or session.chat_id != chat_id:
        return {"ok": False, "error": "Permission denied", "action": "error"}

    if action == "confirm":
        # 用户确认执行
        await session_manager.update_session(
            session_id,
            status=SessionStatus.CONFIRMED,
        )

        # 获取最后一条用户消息
        user_messages = [m for m in session.messages if m.role == "user"]
        if user_messages:
            last_user_message = user_messages[-1].content

            # 在后台开始执行任务，立即返回响应
            background_tasks.add_task(
                start_opencode_task_in_background,
                session,
                last_user_message,
                chat_id, background_tasks,
            )

            # 立即返回成功响应
            return {"ok": True, "action": "confirmed", "immediate": True}

        return {"ok": True, "action": "confirmed"}

    elif action == "cancel":
        # 用户取消
        await session_manager.close_session(session_id, SessionStatus.CANCELLED)

        background_tasks.add_task(
            feishu_client.send_text_message,
            chat_id,
            "❌ 任务已取消。",
        )

        return {"ok": True, "action": "cancelled"}

    elif action == "continue":
        # 用户选择继续当前session
        await session_manager.update_session(
            session_id,
            status=SessionStatus.CONFIRMED,
        )

        # 获取最后一条用户消息
        user_messages = [m for m in session.messages if m.role == "user"]
        if user_messages:
            last_user_message = user_messages[-1].content

            # 在后台开始执行任务，立即返回响应
            background_tasks.add_task(
                start_opencode_task_in_background,
                session,
                last_user_message,
                chat_id, background_tasks,
            )

            # 立即返回成功响应
            return {"ok": True, "action": "continued", "immediate": True}

        return {"ok": True, "action": "continued"}

    elif action == "new":
        # 用户选择开始新任务
        await session_manager.close_session(session_id, SessionStatus.COMPLETED)

        # 创建新session
        new_session = await session_manager.get_or_create_session(chat_id, user_id)

        if new_session:
            # 获取最后一条用户消息
            user_messages = [m for m in session.messages if m.role == "user"]
            if user_messages:
                last_user_message = user_messages[-1].content

                # 发送确认卡片
                confirmation_card = build_confirmation_card(
                    session_id=new_session.session_id,
                    user_message=last_user_message,
                )

        print(f"[Session] Adding card send task to background")
        background_tasks.add_task(
            feishu_client.send_interactive_card,
            chat_id,
            confirmation_card,
        )
        print(f"[Session] Card send task added")

        return {"ok": True, "action": "new_session_created"}

    elif action == "start":
        # 手动开始执行
        user_messages = [m for m in session.messages if m.role == "user"]
        if user_messages:
            last_user_message = user_messages[-1].content

            # 在后台开始执行任务，立即返回响应
            background_tasks.add_task(
                start_opencode_task_in_background,
                session,
                last_user_message,
                chat_id, background_tasks,
            )

            # 立即返回成功响应
            return {"ok": True, "action": "started", "immediate": True}

        return {"ok": True, "action": "started"}

    elif action == "stop":
        # 停止任务
        task_id = session.current_task_id
        if task_id:
            task = await opencode_manager.get_task(task_id)
            if task and task.process and task.process.poll() is None:
                task.process.terminate()
                await opencode_manager.update_task(
                    task_id, status=TaskStatus.FAILED, error="Task stopped by user"
                )

        await session_manager.close_session(session_id, SessionStatus.CANCELLED)

        background_tasks.add_task(
            feishu_client.send_text_message,
            chat_id,
            "⏹️ 任务已停止。",
        )

        return {"ok": True, "action": "stopped"}

    elif action == "retry":
        # 重新执行
        user_messages = [m for m in session.messages if m.role == "user"]
        if user_messages:
            last_user_message = user_messages[-1].content

            # 重置session状态
            await session_manager.update_session(
                session_id,
                status=SessionStatus.CONFIRMED,
            )

            # 在后台开始执行任务，立即返回响应
            background_tasks.add_task(
                start_opencode_task_in_background,
                session,
                last_user_message,
                chat_id, background_tasks,
            )

            # 立即返回成功响应
            return {"ok": True, "action": "retry", "immediate": True}

        return {"ok": True, "action": "retry"}

    elif action == "cleanup":
        # 清理session
        await session_manager.close_session(session_id, SessionStatus.COMPLETED)

        background_tasks.add_task(
            feishu_client.send_text_message,
            chat_id,
            "🗑️ Session已清理。",
        )

        return {"ok": True, "action": "cleaned_up"}

    return {"ok": False, "error": f"Unknown action: {action}", "action": "error"}
