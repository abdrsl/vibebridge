"""
飞书Webhook处理器 - 支持session管理的消息处理
"""

import asyncio
import json
import os
import re
from datetime import datetime
from typing import Any, Dict

from fastapi import BackgroundTasks

from .feishu_client import (
    build_confirmation_card,
    build_dynamic_progress_card,
    build_help_card,
    build_session_continue_card,
    build_session_status_card,
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

    # 清理飞书@mention标签格式（如<at user_id="user_1">@_user_1</at>）
    import re

    # 移除<at>标签及其内容
    text = re.sub(r"<at[^>]*>.*?</at>", "", text)
    # 移除消息开头的@用户名（如@_user_1）
    text = re.sub(r"^\s*@[^\s]+\s*", "", text)
    text = text.strip()

    # 检查群组消息是否@机器人
    chat_type = message.get("chat_type", "")
    mentions = message.get("mentions", [])

    # 如果是群组消息
    if chat_type == "group":
        # 检查是否有机器人提及
        bot_mentioned = False
        for mention in mentions:
            if mention.get("mentioned_type") == "bot":
                bot_mentioned = True
                print(f"[Webhook] 机器人被提及: {mention.get('name', 'unknown')}")
                break

        if not bot_mentioned:
            print(
                f"[Webhook] 群组消息未@机器人，跳过处理。chat_id: {chat_id}, text: {text[:50]}..."
            )
            return {
                "ok": True,
                "skipped": True,
                "reason": "Group message without bot mention",
            }

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
        background_tasks.add_task(feishu_client.send_interactive_card, chat_id, help_card)
        return {"ok": True, "handled": True, "action": "help"}

    # 检查是否是session操作
    if text.lower() in ["status", "状态", "/status"]:
        return await handle_session_status(chat_id, sender_id, background_tasks)

    if text.lower() in ["cancel", "取消", "/cancel"]:
        return await handle_session_cancel(chat_id, sender_id, background_tasks)

    # 检查是否是进度查询（中文）
    progress_keywords = [
        "进度",
        "进展",
        "怎么样了",
        "完成了吗",
        "怎么没反馈",
        "反馈进度",
    ]
    if any(keyword in text for keyword in progress_keywords):
        # 检查是否有正在进行的session
        session_manager = get_session_manager()
        session = await session_manager.get_user_session(chat_id, sender_id)

        if session and session.status == SessionStatus.RUNNING:
            # 有正在运行的任务，返回当前状态
            return await handle_session_status(chat_id, sender_id, background_tasks)
        elif session and session.status in [
            SessionStatus.COMPLETED,
            SessionStatus.FAILED,
        ]:
            # 任务已完成或失败
            status_text = "已完成" if session.status == SessionStatus.COMPLETED else "已失败"
            background_tasks.add_task(
                feishu_client.send_text_message,
                chat_id,
                f"📋 上一个任务{status_text}。请发送新任务或使用 /status 查看详情。",
            )
            return {
                "ok": True,
                "handled": True,
                "action": "progress_query",
                "status": session.status,
            }
        else:
            # 没有正在进行的任务
            background_tasks.add_task(
                feishu_client.send_text_message,
                chat_id,
                "📭 当前没有正在执行的任务。请发送你的开发任务，我会立即开始处理！",
            )
            return {
                "ok": True,
                "handled": True,
                "action": "progress_query",
                "status": "no_task",
            }

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
                    response_msg = result.get("message") or cmd_config.get("response", "指令已执行")
                    print(f"[Command] Sending response message: {response_msg[:50]}...")

                    # 直接使用asyncio.create_task发送消息，避免background_tasks问题
                    async def send_message_task():
                        try:
                            print("[Command] Starting to send message via feishu_client...")
                            result = await feishu_client.send_text_message(chat_id, response_msg)
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
            background_tasks.add_task(feishu_client.send_text_message, chat_id, f"❌ {error_msg}")
            return {"ok": False, "error": error_msg}

    # 获取或创建session
    session_manager = get_session_manager()
    session = await session_manager.get_or_create_session(chat_id, sender_id)

    # 检查是否WebSocket模式
    from .config_manager import get_config_manager

    config_manager = get_config_manager()
    feishu_mode = config_manager.get_feishu_mode()
    is_websocket_mode = feishu_mode == "websocket"
    print(
        f"[Session] WebSocket mode check: feishu_mode={feishu_mode}, is_websocket_mode={is_websocket_mode}"
    )

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
        # 检查是否WebSocket模式，如果是则自动确认并开始执行
        if is_websocket_mode:
            # WebSocket模式：自动确认并开始执行
            print(f"[Session] WebSocket模式，自动确认session {session.session_id}")

            # 更新session状态为已确认
            await session_manager.update_session(
                session.session_id,
                status=SessionStatus.CONFIRMED,
            )

            # 开始执行任务
            return await start_opencode_task(session, text, chat_id, background_tasks)
        else:
            # Webhook模式：发送确认卡片
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
        # 任务正在执行中
        # 无论WebSocket还是Webhook模式，都取消旧任务并开始新任务
        # 这样避免了CLI任务和飞书任务的冲突
        print(f"[Session] Session {session.session_id} 状态为 RUNNING，取消旧任务并开始新任务")
        # 尝试取消旧任务
        if session.current_task_id:
            try:
                cancelled = await opencode_manager.cancel_task(session.current_task_id)
                print(f"[Session] 取消旧任务 {session.current_task_id}: {cancelled}")
            except Exception as e:
                print(f"[Session] 取消任务失败: {e}")
        # 更新session状态为已确认
        await session_manager.update_session(
            session.session_id,
            status=SessionStatus.CONFIRMED,
        )
        # 开始执行新任务
        return await start_opencode_task(session, text, chat_id, background_tasks)

    elif session.status in [
        SessionStatus.COMPLETED,
        SessionStatus.FAILED,
        SessionStatus.CANCELLED,
    ]:
        # 之前的任务已完成/失败/取消
        if is_websocket_mode:
            # WebSocket模式：自动开始新任务
            print(
                f"[Session] WebSocket模式，session {session.session_id} 状态为 {session.status}，自动开始新任务"
            )
            # 更新session状态为已确认
            await session_manager.update_session(
                session.session_id,
                status=SessionStatus.CONFIRMED,
            )
            # 开始执行任务
            return await start_opencode_task(session, text, chat_id, background_tasks)
        else:
            # Webhook模式：询问是否继续
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
        if is_websocket_mode:
            # WebSocket模式：自动开始新任务
            print(f"[Session] WebSocket模式，session {session.session_id} 状态未知，自动开始新任务")
            # 更新session状态为已确认
            await session_manager.update_session(
                session.session_id,
                status=SessionStatus.CONFIRMED,
            )
            # 开始执行任务
            return await start_opencode_task(session, text, chat_id, background_tasks)
        else:
            # Webhook模式：重置session并发送确认卡片
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
    # 创建OpenCode任务 - 支持口令授权最高权限
    # 检查环境变量 FEISHU_PERMIT_ALL，默认为 True（向后兼容）
    feishu_permit_all = os.getenv("FEISHU_PERMIT_ALL", "true").lower() in ("true", "1", "yes", "y")
    # 获取授权口令
    permit_password = os.getenv("FEISHU_PERMIT_PASSWORD", "").strip()

    # 初始化变量
    original_message = user_message
    cleaned_message = user_message
    skip_constitution = feishu_permit_all  # 如果 FEISHU_PERMIT_ALL=true，跳过检查

    # 检查是否包含授权口令
    if permit_password and permit_password in user_message:
        skip_constitution = True
        # 从消息中移除口令（避免OpenCode看到）
        cleaned_message = user_message.replace(permit_password, "")
        # 去除首尾空格，合并多个连续空格
        cleaned_message = re.sub(r"\s+", " ", cleaned_message.strip())
        # 如果消息为空，使用默认消息
        if not cleaned_message:
            cleaned_message = "执行授权任务"
        print(f"[Security] Permit password detected, skipping constitution check")
        # 记录时隐藏口令
        print(
            f"[Security] Original message length: {len(user_message)}, cleaned length: {len(cleaned_message)}"
        )
    elif feishu_permit_all:
        print(f"[Security] Feishu permit all enabled, skipping constitution check")
    else:
        print(f"[Security] No permit password or FEISHU_PERMIT_ALL, constitution check enabled")

    check_constitution = not skip_constitution

    task_id = await opencode_manager.create_task(
        user_message=cleaned_message,
        feishu_chat_id=chat_id,
        check_constitution=check_constitution,  # 根据环境变量和口令控制宪法检查
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
    """使用session运行OpenCode任务 - 实时文本滚轮显示版本"""
    print(f"[Session] Starting task {task_id} for session {session_id}")

    # 检查是否WebSocket模式
    from .config_manager import get_config_manager

    config_manager = get_config_manager()
    is_websocket_mode = config_manager.get_feishu_mode() == "websocket"
    print(
        f"[Session] WebSocket mode detection: is_websocket_mode={is_websocket_mode}, notify={notify}, feishu_mode={config_manager.get_feishu_mode()}"
    )

    # WebSocket模式下保持通知开启（用户需要实时进度卡片）
    if is_websocket_mode:
        notify = True
        print("[Session] WebSocket mode: notify forced to True (user wants progress cards)")

    session_manager = get_session_manager()

    # 获取session以获取用户消息
    session = await session_manager.get_session(session_id)
    user_message = ""
    if session and session.messages:
        # 查找最后一个用户消息（最新的）
        for msg in reversed(session.messages):
            if msg.role == "user":
                user_message = msg.content
                break
        # 如果找不到最新的，使用第一个
        if not user_message:
            for msg in session.messages:
                if msg.role == "user":
                    user_message = msg.content
                    break

    card_message_id = None
    text_message_id = None  # 后备：文本消息ID
    output_lines = []
    tool_count = 0
    last_update_time = 0
    update_count = 0
    current_phase = "analyzing"
    completed_phases = []
    # thought_summaries = []  # Unused variable
    send_failures = 0  # 消息发送失败计数器
    max_failures = 5  # 最大失败次数，超过则禁用更新

    # 阶段和进度追踪
    def estimate_phase_and_progress():
        """根据事件估算当前阶段和进度"""
        nonlocal current_phase, completed_phases

        # 简单启发式：基于工具使用和输出计数
        total_events = len(output_lines)

        if total_events == 0:
            return "analyzing", 5

        # 事件计数映射到阶段
        if total_events < 3:
            phase = "analyzing"
            progress = min(20, total_events * 7)
        elif total_events < 6:
            if "planning" not in completed_phases:
                completed_phases.append("planning")
            phase = "planning"
            progress = min(40, 20 + (total_events - 3) * 7)
        elif total_events < 10:
            if "reading" not in completed_phases:
                completed_phases.append("reading")
            phase = "reading"
            progress = min(60, 40 + (total_events - 6) * 5)
        elif total_events < 15:
            if "coding" not in completed_phases:
                completed_phases.append("coding")
            phase = "coding"
            progress = min(80, 60 + (total_events - 10) * 4)
        elif total_events < 20:
            if "testing" not in completed_phases:
                completed_phases.append("testing")
            phase = "testing"
            progress = min(95, 80 + (total_events - 15) * 3)
        else:
            phase = "summarizing"
            progress = 95

        # 如果有工具调用，可能是coding或fixing阶段
        if tool_count > 0 and "coding" not in completed_phases:
            phase = "coding"

        current_phase = phase
        return phase, progress

    # 思考摘要提取
    def extract_thought_summary():
        """从text事件中提取思考摘要"""
        if not output_lines:
            return ""

        # 查找最近的text事件（不是tool_use或status）
        for line in reversed(output_lines):
            if line and len(line) > 10 and not line.startswith("🛠️") and not line.startswith("正在"):
                # 提取简短摘要
                summary = line[:100] + "..." if len(line) > 100 else line
                return summary

        return ""

    # 动态显示更新函数 - 优先使用卡片，后备使用文本
    async def update_display_message():
        """更新显示消息 - 优先使用交互卡片更新，失败时使用文本消息"""
        nonlocal card_message_id, text_message_id, output_lines, update_count, current_phase, completed_phases, send_failures, max_failures

        # WebSocket模式下也发送更新消息（用户需要实时进度卡片）

        if not output_lines:
            return

        # 如果发送失败次数过多，跳过更新以避免重复失败
        if send_failures >= max_failures:
            print(
                f"[Session] Too many send failures ({send_failures}/{max_failures}), skipping update"
            )
            return

        # 估算阶段和进度
        phase, progress = estimate_phase_and_progress()
        thought_summary = extract_thought_summary()

        # 最近输出（最近30行）
        recent_output_lines = output_lines[-30:] if len(output_lines) >= 30 else output_lines
        recent_output = "\n".join(recent_output_lines)

        # 尝试使用卡片更新（首选）
        if card_message_id or not text_message_id:  # 优先使用卡片
            try:
                # 构建动态进度卡片
                card = build_dynamic_progress_card(
                    task_id=task_id,
                    user_message=user_message,
                    phase=phase,
                    progress=progress,
                    thought_summary=thought_summary,
                    recent_output=recent_output,
                    tool_count=tool_count,
                    output_count=len(output_lines),
                    status="running",
                    timeline=completed_phases,
                )

                if card_message_id:
                    # 尝试更新现有卡片
                    update_result = await feishu_client.update_interactive_card(
                        card_message_id, card
                    )
                    if update_result and update_result.get("code") == 0:
                        # 卡片更新成功
                        update_count += 1
                        send_failures = 0  # 重置失败计数器
                        print(f"[Session] Card updated successfully, ID: {card_message_id}")
                        return
                    else:
                        # 卡片更新失败，尝试发送新卡片
                        print(f"[Session] Failed to update card: {update_result}")
                        send_failures += 1  # 递增失败计数器
                        # 清除旧message_id，尝试发送新卡片
                        card_message_id = None
                else:
                    # 发送新卡片
                    result = await feishu_client.send_interactive_card(chat_id, card)
                    if result and result.get("code") == 0:
                        new_message_id = result.get("data", {}).get("message_id")
                        if new_message_id:
                            card_message_id = new_message_id
                            update_count += 1
                            print(f"[Session] New card sent successfully, ID: {card_message_id}")
                            send_failures = 0  # 重置失败计数器
                            return
                        else:
                            print("[Session] No message ID in card result")
                            send_failures += 1  # 递增失败计数器
                    else:
                        print(f"[Session] Failed to send new card: {result}")
                        send_failures += 1  # 递增失败计数器
            except Exception as e:
                print(f"[Session] Error with card update: {e}")
                send_failures += 1  # 递增失败计数器

        # 卡片更新失败，回退到文本消息更新
        # 构建文本消息内容
        display_lines = output_lines[-30:] if len(output_lines) > 30 else output_lines
        message_content = "## 🔨 OpenCode 任务执行中\n\n"
        message_content += f"**任务ID:** `{task_id}`\n"
        message_content += f"**当前阶段:** {phase} ({progress}%)\n\n"
        message_content += "**最近输出:**\n```\n"
        message_content += "\n".join(display_lines) if display_lines else "无输出"
        message_content += "\n```\n\n"

        if thought_summary:
            message_content += f"**💭 思考摘要:** {thought_summary}\n\n"

        if tool_count > 0:
            message_content += f"🛠️ 已执行 {tool_count} 个操作\n"

        message_content += f"⏰ 更新次数: {update_count}\n"
        message_content = message_content.strip()

        # 尝试更新文本消息
        if text_message_id:
            try:
                update_result = await feishu_client.update_text_message(
                    text_message_id, message_content
                )
                if update_result and update_result.get("code") == 0:
                    # 文本更新成功
                    update_count += 1
                    print(f"[Session] Text message updated successfully, ID: {text_message_id}")
                    send_failures = 0  # 重置失败计数器
                    return
                else:
                    # 文本更新失败
                    print(f"[Session] Failed to update text message: {update_result}")
                    send_failures += 1  # 递增失败计数器
                    # 尝试删除旧消息（如果还存在）
                    try:
                        await feishu_client.delete_message(text_message_id)
                    except:
                        pass
                    text_message_id = None
            except Exception as e:
                print(f"[Session] Error updating text message: {e}")
                send_failures += 1  # 递增失败计数器

        # 发送新文本消息
        try:
            result = await feishu_client.send_text_message(chat_id, message_content)
            print(f"[Session] New text message result: {result}")
            if result and result.get("code") == 0:
                new_message_id = result.get("data", {}).get("message_id")
                if new_message_id:
                    text_message_id = new_message_id
                    update_count += 1
                    print(f"[Session] New text message sent successfully, ID: {text_message_id}")
                    send_failures = 0  # 重置失败计数器
                else:
                    print("[Session] No message ID in text result")
                    send_failures += 1  # 递增失败计数器
            else:
                print(f"[Session] Failed to send new text message: {result}")
                send_failures += 1  # 递增失败计数器
        except Exception as e:
            print(f"[Session] Failed to send new text message: {e}")
            send_failures += 1  # 递增失败计数器

    try:
        print(f"[Session] Debug: notify={notify}, is_websocket_mode={is_websocket_mode}")
        if notify:
            # 发送初始消息（WebSocket和Webhook模式都发送）
            print(f"[Session] Sending initial message to {chat_id} (WebSocket={is_websocket_mode})")

            # 尝试发送初始卡片
            try:
                initial_card = build_dynamic_progress_card(
                    task_id=task_id,
                    user_message=user_message,
                    phase="analyzing",
                    progress=5,
                    thought_summary="正在解析任务需求...",
                    recent_output="",
                    tool_count=0,
                    output_count=0,
                    status="running",
                    timeline=[],
                )

                result = await feishu_client.send_interactive_card(chat_id, initial_card)
                print(f"[Session] Initial card result: {result}")

                if result and result.get("code") == 0:
                    card_message_id = result.get("data", {}).get("message_id")
                    print(f"[Session] Card message ID: {card_message_id}")
                else:
                    print(f"[Session] Failed to send initial card, result: {result}")
                    send_failures += 1  # 递增失败计数器
                    # 卡片发送失败，尝试发送文本消息
                    initial_message = f"## 🚀 OpenCode 任务已启动\n\n**任务ID:** `{task_id}`\n\n**开始执行...**\n\n⏳ 正在初始化，请稍候～"
                    result = await feishu_client.send_text_message(chat_id, initial_message)
                    print(f"[Session] Initial text message result: {result}")

                    if result and result.get("code") == 0:
                        text_message_id = result.get("data", {}).get("message_id")
                        send_failures = 0  # 重置失败计数器（文本发送成功）
                        print(f"[Session] Text message ID: {text_message_id}")
                    else:
                        print(f"[Session] Failed to send initial text message, result: {result}")
                        send_failures += 1  # 递增失败计数器（文本发送也失败）
            except Exception as e:
                print(f"[Session] Error sending initial message: {e}")
                send_failures += 1  # 递增失败计数器
                # 即使发送失败，仍然继续执行任务（不在飞书中显示实时更新）

        # 实时处理事件并更新显示
        final_result = None
        error_result = None
        import time

        async for event in opencode_manager.run_opencode(task_id):
            event_type = event.get("type", "")
            content = event.get("content", "")
            print(f"[Session] Event: {event_type} - {content[:50]}...")

            # 收集输出行用于显示
            if event_type == "tool_use" or event_type == "text" or event_type == "status":
                output_lines.append(content)
                if event_type == "tool_use":
                    tool_count += 1

                # 控制更新频率：每2个事件或每2秒更新一次
                current_time = time.time()
                should_update = False

                # 总是更新前几次，让用户看到进度
                if len(output_lines) <= 3:
                    should_update = True
                # 每收集到2个新事件更新一次
                elif len(output_lines) % 2 == 0:
                    should_update = True
                # 如果超过2秒没更新，也更新一次
                elif current_time - last_update_time > 2.0:
                    should_update = True

                if should_update and notify:
                    await update_display_message()
                    last_update_time = current_time

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
                f"任务完成: {final_result[:500]}{'...' if len(final_result) > 500 else ''}",
                task_id=task_id,
                result_type="completed",
            )

            # WebSocket模式下发送优化的最终汇总总结
            if is_websocket_mode:
                print(
                    f"[Session] WebSocket mode: sending optimized final summary for session {session_id}"
                )
                try:
                    # 尝试发送卡片（更美观，支持表格）
                    # 构建完成卡片
                    completed_phases.append("summarizing")

                    # 准备结果内容 - 如果是表格，直接显示；否则放在代码块中
                    result_display = ""
                    if final_result:
                        # 检查是否包含表格（包含管道符和横线）
                        if "|" in final_result and "-" in final_result:
                            # 可能是markdown表格，直接作为markdown内容
                            if len(final_result) > 4000:
                                result_display = f"{final_result[:3500]}...\n\n*表格过长已截断，完整结果共 {len(final_result)} 字符*"
                            else:
                                result_display = final_result
                        else:
                            # 普通文本，放在代码块中
                            if len(final_result) > 1200:
                                result_display = f"```\n{final_result[:1000]}...\n```\n*完整结果共 {len(final_result)} 字符*"
                            else:
                                result_display = f"```\n{final_result}\n```"
                    else:
                        result_display = "无输出"

                    # 构建统计信息
                    stats_content = f"**📊 执行统计:**\n"
                    stats_content += f"• 工具使用: {tool_count} 次\n"
                    stats_content += f"• 输出事件: {len(output_lines)} 个\n"
                    stats_content += "• 状态: ✅ 成功"

                    print(
                        f"[Session] WebSocket completion - building card, final_result length: {len(final_result) if final_result else 0}, has_table: {'|' in final_result and '-' in final_result if final_result else False}"
                    )

                    completion_card = {
                        "config": {"wide_screen_mode": True},
                        "elements": [
                            {
                                "tag": "markdown",
                                "content": f"## ✅ **任务完成**\n\n"
                                f"**任务:** {user_message[:300]}{'...' if len(user_message) > 300 else ''}\n"
                                f"**ID:** `{task_id}`",
                            },
                            {"tag": "hr"},
                            {"tag": "markdown", "content": f"**📋 完整结果:**\n\n{result_display}"},
                            {"tag": "hr"},
                            {"tag": "markdown", "content": stats_content},
                            {
                                "tag": "note",
                                "elements": [
                                    {"tag": "plain_text", "content": "任务执行完毕，可发送新任务"}
                                ],
                            },
                        ],
                        "header": {
                            "title": {"tag": "plain_text", "content": "✅ 任务完成"},
                            "template": "green",
                        },
                    }

                    print(
                        f"[Session] Attempting to send completion card, card size: {len(str(completion_card))}"
                    )
                    result = await feishu_client.send_interactive_card(chat_id, completion_card)
                    print(f"[Session] Card send result: {result}")
                    if result and result.get("code") == 0:
                        print(f"[Session] WebSocket completion card sent successfully")
                    else:
                        # 卡片发送失败，回退到文本消息
                        raise Exception(f"Card send failed: {result}")

                except Exception as e:
                    print(f"[Session] Error sending WebSocket completion card: {e}")
                    # 回退到文本消息
                    try:
                        # 优化后的最终总结格式 - 更简洁
                        completion_message = "## ✅ 任务完成\n\n"
                        completion_message += f"**任务:** {user_message[:150]}{'...' if len(user_message) > 150 else ''}\n"
                        completion_message += f"**ID:** `{task_id}`\n\n"

                        # 结果摘要（更完整）
                        if final_result:
                            if len(final_result) > 2000:
                                # 对于超长结果，提供更长的摘要
                                completion_message += "**📋 结果摘要:**\n"
                                completion_message += f"```\n{final_result[:1500]}...\n```\n"
                                completion_message += f"*完整结果共 {len(final_result)} 字符*\n\n"
                            else:
                                completion_message += "**📋 完整结果:**\n"
                                completion_message += f"```\n{final_result}\n```\n\n"
                        else:
                            completion_message += "**📋 结果:** 无输出\n\n"

                        completion_message += "**📊 执行统计:**\n"
                        completion_message += f"• 工具使用: {tool_count} 次\n"
                        completion_message += f"• 输出事件: {len(output_lines)} 个\n"
                        completion_message += "• 状态: ✅ 成功\n\n"
                        completion_message += "---\n*任务执行完毕*"

                        await feishu_client.send_text_message(chat_id, completion_message)
                    except Exception as e2:
                        print(
                            f"[Session] Error sending WebSocket completion message (fallback): {e2}"
                        )
            elif notify:
                # Webhook模式：更新现有卡片为完成状态
                print(f"[Session] Sending final completion message for session {session_id}")

                try:
                    # 尝试更新现有卡片为完成状态
                    if card_message_id:
                        # 构建完成卡片
                        completed_phases.append("summarizing")
                        completion_card = build_dynamic_progress_card(
                            task_id=task_id,
                            user_message=user_message,
                            phase="summarizing",
                            progress=100,
                            thought_summary="任务执行完成",
                            recent_output=f"✅ 完成: {final_result[:500]}{'...' if final_result and len(final_result) > 500 else ''}"
                            if final_result
                            else "任务完成",
                            tool_count=tool_count,
                            output_count=len(output_lines),
                            status="completed",
                            timeline=completed_phases,
                        )

                        update_result = await feishu_client.update_interactive_card(
                            card_message_id, completion_card
                        )
                        if update_result and update_result.get("code") == 0:
                            print(
                                f"[Session] Card updated to completed status, ID: {card_message_id}"
                            )
                        else:
                            # 卡片更新失败，发送新卡片
                            print(f"[Session] Failed to update card to completed: {update_result}")
                            result = await feishu_client.send_interactive_card(
                                chat_id, completion_card
                            )
                            print(f"[Session] New completion card sent: {result}")
                    elif text_message_id:
                        # 只有文本消息，更新文本消息
                        completion_message = "## 🎉 OpenCode 任务完成\n\n"
                        completion_message += f"**任务ID:** `{task_id}`\n\n"
                        completion_message += f"**最终结果:**\n{final_result[:1000]}{'...' if len(final_result) > 1000 else ''}\n\n"
                        completion_message += "**执行统计:**\n"
                        completion_message += f"• 📊 总输出行数: {len(output_lines)}\n"
                        completion_message += f"• 🛠️ 工具使用次数: {tool_count}\n"
                        completion_message += "• ✅ 状态: 成功完成\n\n"
                        completion_message += "🎯 任务已成功执行完毕！"

                        update_result = await feishu_client.update_text_message(
                            text_message_id, completion_message
                        )
                        if update_result and update_result.get("code") == 0:
                            print(
                                f"[Session] Text message updated to completed, ID: {text_message_id}"
                            )
                        else:
                            # 文本更新失败，发送新消息
                            print(f"[Session] Failed to update text message: {update_result}")
                            result = await feishu_client.send_text_message(
                                chat_id, completion_message
                            )
                            print(f"[Session] New completion message sent: {result}")
                    else:
                        # 没有现有消息，发送新卡片
                        completion_card = build_dynamic_progress_card(
                            task_id=task_id,
                            user_message=user_message,
                            phase="summarizing",
                            progress=100,
                            thought_summary="任务执行完成",
                            recent_output=f"✅ 完成: {final_result[:500]}{'...' if final_result and len(final_result) > 500 else ''}"
                            if final_result
                            else "任务完成",
                            tool_count=tool_count,
                            output_count=len(output_lines),
                            status="completed",
                            timeline=completed_phases,
                        )
                        result = await feishu_client.send_interactive_card(chat_id, completion_card)
                        print(f"[Session] New completion card sent: {result}")
                except Exception as e:
                    print(f"[Session] Error sending completion message: {e}")
                    # 后备：发送简单文本消息
                    try:
                        completion_message = (
                            f"## 🎉 OpenCode 任务完成\n\n**任务ID:** `{task_id}`\n\n✅ 任务已完成"
                        )
                        await feishu_client.send_text_message(chat_id, completion_message)
                    except:
                        pass

        elif error_result:
            await session_manager.update_session(
                session_id,
                status=SessionStatus.FAILED,
            )

            # 添加失败消息
            await session_manager.add_message_to_session(
                session_id,
                "assistant",
                f"任务失败: {error_result[:500]}",
                task_id=task_id,
                result_type="failed",
            )

            if notify:
                # 发送错误消息 - 优先更新现有卡片
                print(f"[Session] Sending error message for session {session_id}")

                try:
                    # 尝试更新现有卡片为失败状态
                    if card_message_id:
                        error_card = build_dynamic_progress_card(
                            task_id=task_id,
                            user_message=user_message,
                            phase="fixing",
                            progress=100,
                            thought_summary="任务执行失败",
                            recent_output=f"❌ 错误: {error_result[:500]}...",
                            tool_count=tool_count,
                            output_count=len(output_lines),
                            status="failed",
                            timeline=completed_phases,
                        )

                        update_result = await feishu_client.update_interactive_card(
                            card_message_id, error_card
                        )
                        if update_result and update_result.get("code") == 0:
                            print(f"[Session] Card updated to failed status, ID: {card_message_id}")
                        else:
                            # 卡片更新失败，发送新卡片
                            print(f"[Session] Failed to update card to failed: {update_result}")
                            result = await feishu_client.send_interactive_card(chat_id, error_card)
                            print(f"[Session] New error card sent: {result}")
                    elif text_message_id:
                        # 只有文本消息，更新文本消息
                        error_message = "## ❌ OpenCode 任务失败\n\n"
                        error_message += f"**任务ID:** `{task_id}`\n\n"
                        error_message += f"**错误信息:**\n{error_result[:500]}{'...' if len(error_result) > 500 else ''}\n\n"
                        error_message += "**执行统计:**\n"
                        error_message += f"• 📊 总输出行数: {len(output_lines)}\n"
                        error_message += f"• 🛠️ 工具使用次数: {tool_count}\n"
                        error_message += "• ❌ 状态: 执行失败\n\n"
                        error_message += "🔧 请检查任务描述或重试。"

                        update_result = await feishu_client.update_text_message(
                            text_message_id, error_message
                        )
                        if update_result and update_result.get("code") == 0:
                            print(
                                f"[Session] Text message updated to failed, ID: {text_message_id}"
                            )
                        else:
                            # 文本更新失败，发送新消息
                            print(f"[Session] Failed to update text message: {update_result}")
                            result = await feishu_client.send_text_message(chat_id, error_message)
                            print(f"[Session] New error message sent: {result}")
                    else:
                        # 没有现有消息，发送新卡片
                        error_card = build_dynamic_progress_card(
                            task_id=task_id,
                            user_message=user_message,
                            phase="fixing",
                            progress=100,
                            thought_summary="任务执行失败",
                            recent_output=f"❌ 错误: {error_result[:500]}...",
                            tool_count=tool_count,
                            output_count=len(output_lines),
                            status="failed",
                            timeline=completed_phases,
                        )
                        result = await feishu_client.send_interactive_card(chat_id, error_card)
                        print(f"[Session] New error card sent: {result}")
                except Exception as e:
                    print(f"[Session] Error sending error message: {e}")
                    # 后备：发送简单文本消息
                    try:
                        error_message = f"## ❌ OpenCode 任务失败\n\n**任务ID:** `{task_id}`\n\n❌ 任务失败: {error_result[:500]}"
                        await feishu_client.send_text_message(chat_id, error_message)
                    except:
                        pass
            elif is_websocket_mode:
                # WebSocket模式：发送错误汇总总结（使用卡片）
                print(f"[Session] WebSocket mode: sending error summary for session {session_id}")
                try:
                    # 构建错误卡片
                    error_card = {
                        "config": {"wide_screen_mode": True},
                        "elements": [
                            {
                                "tag": "markdown",
                                "content": f"## ❌ **任务失败**\n\n"
                                f"**任务:** {user_message[:300]}{'...' if len(user_message) > 300 else ''}\n"
                                f"**ID:** `{task_id}`",
                            },
                            {"tag": "hr"},
                            {
                                "tag": "markdown",
                                "content": f"**错误信息:**\n\n```\n{error_result[:800]}{'...' if len(error_result) > 800 else ''}\n```",
                            },
                            {"tag": "hr"},
                            {
                                "tag": "markdown",
                                "content": f"**📊 执行统计:**\n\n"
                                f"• 工具使用: {tool_count} 次\n"
                                f"• 输出事件: {len(output_lines)} 个\n"
                                f"• 状态: ❌ 失败",
                            },
                            {
                                "tag": "note",
                                "elements": [
                                    {"tag": "plain_text", "content": "🔧 请检查任务描述或重试"}
                                ],
                            },
                        ],
                        "header": {
                            "title": {"tag": "plain_text", "content": "❌ 任务失败"},
                            "template": "red",
                        },
                    }

                    result = await feishu_client.send_interactive_card(chat_id, error_card)
                    if result and result.get("code") == 0:
                        print(f"[Session] WebSocket error card sent successfully")
                    else:
                        # 卡片发送失败，回退到文本消息
                        raise Exception(f"Card send failed: {result}")

                except Exception as e:
                    print(f"[Session] Error sending WebSocket error card: {e}")
                    # 回退到文本消息
                    try:
                        error_message = "## ❌ 任务失败\n\n"
                        error_message += f"**任务:** {user_message[:150]}{'...' if len(user_message) > 150 else ''}\n"
                        error_message += f"**ID:** `{task_id}`\n\n"
                        error_message += "**错误信息:**\n"
                        error_message += f"```\n{error_result[:500]}{'...' if len(error_result) > 500 else ''}\n```\n\n"
                        error_message += "**执行统计:**\n"
                        error_message += f"• 工具使用: {tool_count} 次\n"
                        error_message += f"• 输出事件: {len(output_lines)} 个\n"
                        error_message += "• 状态: ❌ 失败\n\n"
                        error_message += "🔧 请检查任务描述或重试。"

                        await feishu_client.send_text_message(chat_id, error_message)
                    except Exception as e2:
                        print(f"[Session] Error sending WebSocket error message (fallback): {e2}")

    except Exception as e:
        print(f"[Session] Error: {e}")
        import traceback

        traceback.print_exc()

        # 更新session状态为失败
        await session_manager.update_session(
            session_id,
            status=SessionStatus.FAILED,
        )

        # 发送异常错误消息
        if notify:
            error_message = "## ⚠️ OpenCode 任务异常\n\n"
            error_message += f"**任务ID:** `{task_id}`\n\n"
            error_message += (
                f"**异常信息:**\n{str(e)[:200]}{'...' if len(str(e)) > 200 else ''}\n\n"
            )
            error_message += "**执行统计:**\n"
            error_message += f"• 📊 总输出行数: {len(output_lines)}\n"
            error_message += f"• 🛠️ 工具使用次数: {tool_count}\n"
            error_message += "• ⚠️ 状态: 执行异常\n\n"
            error_message += "🔧 系统内部错误，请稍后重试或联系开发者。"

            # 先删除之前的进度消息
            if text_message_id:
                try:
                    await feishu_client.delete_message(text_message_id)
                    print("[Session] Deleted progress message before sending exception message")
                except Exception as delete_error:
                    print(f"[Session] Error deleting progress message: {delete_error}")

            # 发送异常消息
            try:
                result = await feishu_client.send_text_message(chat_id, error_message)
                print(f"[Session] Exception message sent: {result}")
            except Exception as send_error:
                print(f"[Session] Failed to send exception message: {send_error}")
        elif is_websocket_mode:
            # WebSocket模式：发送异常汇总总结
            print(f"[Session] WebSocket mode: sending exception summary for session {session_id}")
            try:
                error_message = "## ⚠️ OpenCode 任务异常\n\n"
                error_message += f"**任务ID:** `{task_id}`\n\n"
                error_message += "**异常信息:**\n"
                error_message += (
                    f"```\n{str(e)[:1000]}{'...' if len(str(e)) > 1000 else ''}\n```\n\n"
                )
                error_message += "**执行统计:**\n"
                error_message += f"• 📊 总输出行数: {len(output_lines)}\n"
                error_message += f"• 🛠️ 工具使用次数: {tool_count}\n"
                error_message += "• ⚠️ 状态: 执行异常\n\n"
                error_message += "🔧 系统内部错误，请稍后重试或联系开发者。"

                await feishu_client.send_text_message(chat_id, error_message)
            except Exception as send_error:
                print(f"[Session] Failed to send WebSocket exception message: {send_error}")


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
            task_description=session_info.get("metadata", {}).get("last_task", "未知任务"),
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
