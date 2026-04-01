"""
飞书Webhook处理器 - 支持session管理的消息处理
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict

from fastapi import BackgroundTasks

from .feishu_client import (
    build_confirmation_card,
    build_error_card,
    build_help_card,
    build_progress_card,
    build_result_card,
    build_session_continue_card,
    build_session_status_card,
    build_start_card,
    feishu_client,
)
from .opencode_integration import TaskStatus, opencode_manager
from .session_manager import SessionStatus, get_session_manager


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

    # 消息去重检查
    message_id = message.get("message_id", "")
    if message_id:
        from .message_deduplicator import get_deduplicator

        deduplicator = get_deduplicator()

        if deduplicator.is_duplicate(message_id):
            print(f"[Webhook] Duplicate message ignored: {message_id}")
            return {"ok": True, "skipped": True, "reason": "Duplicate message"}

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

    # 检查自定义指令
    from .command_processor import get_command_processor

    command_processor = get_command_processor()
    cmd_config = command_processor.match_command(text)

    if cmd_config:
        print(f"[Command] Matched custom command: {text}")
        result = await command_processor.execute_command(
            cmd_config, chat_id, sender_id, background_tasks=background_tasks
        )

        if result.get("ok"):
            # 如果需要确认，发送确认卡片
            if cmd_config.get("confirm", False):
                # 发送确认卡片
                confirm_card = {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "title": {"tag": "plain_text", "content": "⚠️ 确认操作"},
                        "template": "orange",
                    },
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": f"**{cmd_config.get('description', '确认执行')}**\n\n{cmd_config.get('confirm_message', '确定要执行此操作吗？')}",
                        },
                        {"tag": "hr"},
                        {
                            "tag": "action",
                            "actions": [
                                {
                                    "tag": "button",
                                    "text": {"tag": "plain_text", "content": "✅ 确认"},
                                    "type": "primary",
                                    "value": json.dumps(
                                        {
                                            "action": cmd_config["action"],
                                            "command": text,
                                            "confirmed": True,
                                        }
                                    ),
                                },
                                {
                                    "tag": "button",
                                    "text": {"tag": "plain_text", "content": "❌ 取消"},
                                    "type": "danger",
                                    "value": json.dumps(
                                        {"action": "cancel_command", "command": text}
                                    ),
                                },
                            ],
                        },
                    ],
                }
                background_tasks.add_task(
                    feishu_client.send_interactive_card, chat_id, confirm_card
                )
                return {"ok": True, "action": "command_confirm", "command": text}
            else:
                # 直接执行，检查是否需要发送响应消息
                print(
                    f"[Command] Processing immediate command, message_sent: {result.get('message_sent', False)}"
                )
                if not result.get("message_sent", False):
                    # 命令处理器未发送消息，发送响应消息
                    response_msg = result.get("message") or cmd_config.get(
                        "response", "指令已执行"
                    )
                    print(f"[Command] Sending response message: {response_msg[:50]}...")

                    # 直接使用asyncio.create_task发送消息，避免background_tasks问题
                    async def send_message_task():
                        try:
                            print(
                                "[Command] Starting to send message via feishu_client..."
                            )
                            result = await feishu_client.send_text_message(
                                chat_id, response_msg
                            )
                            print(f"[Command] Message send result: {result}")
                        except Exception as e:
                            print(f"[Command] Error sending message: {e}")

                    # 同时使用background_tasks和asyncio.create_task以确保消息发送
                    background_tasks.add_task(send_message_task)
                    # 也直接启动任务
                    asyncio.create_task(send_message_task())
                else:
                    print("[Command] Message already sent by command processor")
                # 返回结果，保留所有字段
                response_data = {
                    "ok": True,
                    "action": cmd_config["action"],
                    "immediate": True,
                }
                # 合并result中的额外字段（如mode, message_sent等）
                for key, value in result.items():
                    if key not in ["ok", "action"]:  # 避免覆盖
                        response_data[key] = value
                print(f"[Command] Returning response: {response_data}")
                return response_data
        else:
            # 执行失败
            error_msg = result.get("error", "指令执行失败")
            background_tasks.add_task(
                feishu_client.send_text_message, chat_id, f"❌ {error_msg}"
            )
            return {"ok": False, "error": error_msg}

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
    """使用session运行OpenCode任务 - 实时卡片更新版本"""
    print(f"[Session] Starting task {task_id} for session {session_id}")

    session_manager = get_session_manager()
    card_message_id = None
    output_lines = []
    tool_count = 0

    try:
        if notify:
            print(f"[Session] Sending start card to {chat_id}")
            task = await opencode_manager.get_task(task_id)
            if task:
                start_card = build_start_card(task_id, task.user_message)
                result = await feishu_client.send_interactive_card(chat_id, start_card)
                print(f"[Session] Start card result: {result}")
                print(f"[Session] Result type: {type(result)}, keys: {list(result.keys()) if isinstance(result, dict) else 'not dict'}")

                # 保存卡片消息ID用于后续更新
                if result and result.get("code") == 0:
                    data = result.get("data", {})
                    print(f"[Session] Data keys: {list(data.keys()) if isinstance(data, dict) else 'not dict'}")
                    card_message_id = data.get("message_id")
                    print(f"[Session] Card message ID: {card_message_id}")

        # 实时处理事件并更新卡片
        final_result = None
        error_result = None

        async for event in opencode_manager.run_opencode(task_id):
            event_type = event.get("type", "")
            content = event.get("content", "")
            print(f"[Session] Event: {event_type} - {content[:50]}...")

            # 收集输出行用于显示
            if event_type == "tool_use" or event_type == "text" or event_type == "status":
                output_lines.append(content)
                if event_type == "tool_use":
                    tool_count += 1

            # 更新进度卡片
            print(f"[Session] Update check: notify={notify}, card_message_id={card_message_id}, output_lines={len(output_lines)}")
            if notify and card_message_id and output_lines:
                # 获取最新的输出（最后3行）
                latest_output = "\n".join(output_lines[-3:]) if len(output_lines) > 3 else "\n".join(output_lines)
                progress_card = build_progress_card(
                    task_id, "running", latest_output, tool_count
                )

                try:
                    update_result = await feishu_client.update_interactive_card(
                        card_message_id, progress_card
                    )
                    if update_result and update_result.get("code") == 0:
                        print("[Session] Progress card updated successfully")
                    else:
                        print(f"[Session] Failed to update progress card: {update_result}")
                except Exception as e:
                    print(f"[Session] Error updating progress card: {e}")

            if event_type == "done":
                final_result = content
                output_lines.append(f"✅ 任务完成: {content[:100]}...")
            elif event_type == "error":
                error_result = content
                output_lines.append(f"❌ 任务失败: {content}")

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
                    if card_message_id:
                        # 更新现有卡片
                        result = await feishu_client.update_interactive_card(
                            card_message_id, final_card
                        )
                        print(f"[Session] Result card updated: {result}")
                    else:
                        # 发送新卡片
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
                if card_message_id:
                    # 更新现有卡片
                    result = await feishu_client.update_interactive_card(
                        card_message_id, card
                    )
                    print(f"[Session] Error card updated: {result}")
                else:
                    # 发送新卡片
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
        print(f"[Card] Session {session_id} not found, may be expired or cleaned up")
        # 会话已过期或丢失，创建新会话并继续
        # 为了确保Feishu不显示错误，我们返回成功响应
        # 同时在后台发送消息通知用户

        # 创建新会话
        new_session = await session_manager.get_or_create_session(chat_id, user_id)
        if new_session:
            # 添加一条系统消息说明会话已恢复
            await session_manager.add_message_to_session(
                new_session.session_id,
                "system",
                f"原会话 {session_id} 已过期，已创建新会话 {new_session.session_id}",
                original_session_id=session_id,
            )

            # 在后台发送通知消息
            background_tasks.add_task(
                feishu_client.send_text_message,
                chat_id,
                "⚠️ 原任务会话已过期，已创建新会话继续处理。",
            )

            # 对于确认操作，我们需要知道原始任务内容
            # 由于无法恢复原始消息，我们只能提示用户重新发送
            if action == "confirm":
                background_tasks.add_task(
                    feishu_client.send_text_message,
                    chat_id,
                    "请重新发送任务内容以继续。",
                )

        # 无论如何都返回成功响应，避免Feishu显示错误
        return {"ok": True, "action": "session_recovered", "immediate": True}

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
                chat_id,
                background_tasks,
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
                chat_id,
                background_tasks,
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

                print("[Session] Adding card send task to background")
                background_tasks.add_task(
                    feishu_client.send_interactive_card,
                    chat_id,
                    confirmation_card,
                )
                print("[Session] Card send task added")

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
                chat_id,
                background_tasks,
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
                chat_id,
                background_tasks,
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

    elif action in ["git_commit", "start_server"]:
        # 处理需要确认的自定义指令
        from .command_processor import get_command_processor

        command_processor = get_command_processor()

        # 查找对应的指令配置
        for _cmd_name, cmd_config in command_processor.commands.items():
            if cmd_config.get("action") == action:
                result = await command_processor.execute_command(
                    cmd_config, chat_id, user_id, background_tasks=background_tasks
                )

                if result.get("ok"):
                    response_msg = result.get("message", "指令已执行")
                    return {"ok": True, "action": action, "message": response_msg}
                else:
                    return {"ok": False, "error": result.get("error", "指令执行失败")}

        return {"ok": False, "error": f"Command not found for action: {action}"}

    return {"ok": False, "error": f"Unknown action: {action}", "action": "error"}
