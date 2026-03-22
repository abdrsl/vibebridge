"""
飞书卡片交互处理器
处理卡片按钮点击等交互事件
"""

import json
from typing import Dict, Any
from fastapi import BackgroundTasks

from app.feishu_webhook_handler import (
    handle_card_action,
    handle_feishu_message,
)
from app.feishu_client import feishu_client


async def handle_feishu_card_interaction(
    body: Dict[str, Any],
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """
    处理飞书卡片交互

    Args:
        body: 飞书webhook请求体
        background_tasks: 后台任务

    Returns:
        处理结果
    """
    # 支持飞书事件订阅 v1 和 v2 格式
    schema = body.get("schema", "")
    event = {}
    event_type = ""

    if schema == "2.0":
        # v2 格式
        header = body.get("header", {})
        event_type = header.get("event_type", "")
        event = body.get("event", {})
    else:
        # v1 格式
        event = body.get("event", {})
        event_type = body.get("event_type", "")

    if event_type == "im.message.receive_v1":
        return await handle_im_message(event, background_tasks)

    return {
        "ok": True,
        "skipped": True,
        "reason": f"Event type {event_type} not handled",
    }


async def handle_im_message(
    event: Dict[str, Any],
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """处理IM消息（包括卡片交互）"""
    message = event.get("message", {})
    sender = event.get("sender", {})
    content_str = message.get("content", "{}")
    message_type = message.get("message_type", "text")

    try:
        content_obj = json.loads(content_str)
    except json.JSONDecodeError:
        content_obj = {}

    chat_id = message.get("chat_id", "")
    sender_id = sender.get("sender_id", {}).get("open_id", "unknown")

    # 检查是否是卡片交互消息
    if message_type == "interactive":
        # 卡片交互消息，格式为 {"value": "JSON字符串"}
        value_str = content_obj.get("value", "")
        if value_str:
            try:
                action_data = json.loads(value_str)
                if isinstance(action_data, dict) and "action" in action_data:
                    # 这是卡片动作
                    return await handle_card_action(
                        action_data,
                        chat_id,
                        sender_id,
                        background_tasks,
                    )
            except json.JSONDecodeError:
                pass

        # 卡片交互但无法解析，返回成功响应
        return {"ok": True, "action": "processed", "response": {}}

    # 普通文本消息
    text = content_obj.get("text", "").strip()

    # 检查是否是JSON格式的文本（兼容旧格式）
    if text.startswith("{") and text.endswith("}"):
        try:
            action_data = json.loads(text)
            if isinstance(action_data, dict) and "action" in action_data:
                # 这是卡片动作（旧格式）
                return await handle_card_action(
                    action_data,
                    chat_id,
                    sender_id,
                    background_tasks,
                )
        except json.JSONDecodeError:
            pass

    # 普通文本消息，使用原有的处理器
    return await handle_feishu_message(event, background_tasks)


async def send_card_action_response(
    challenge: str,
    action_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    发送卡片动作响应

    飞书卡片交互需要特定的响应格式：
    - 成功: 返回空对象 {}
    - 失败: 返回错误信息

    Args:
        challenge: 挑战码（如果有）
        action_result: 动作处理结果

    Returns:
        响应数据
    """
    if challenge:
        # URL验证请求
        return {"challenge": challenge}

    if action_result.get("ok", False):
        # 成功，返回空对象
        return {}
    else:
        # 失败，返回错误信息
        # 飞书期望的格式: {"code": 200340, "msg": "错误信息"}
        return {
            "code": 200340,
            "msg": action_result.get("error", "Unknown error"),
        }


# 兼容性函数
async def process_feishu_webhook(
    body: Dict[str, Any],
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """
    处理飞书webhook（兼容旧接口）

    Args:
        body: 飞书webhook请求体
        background_tasks: 后台任务

    Returns:
        处理结果
    """
    # 检查是否是URL验证
    challenge = body.get("challenge")
    if challenge:
        return {"challenge": challenge}

    # 处理卡片交互
    result = await handle_feishu_card_interaction(body, background_tasks)

    # 如果是卡片动作，需要特殊响应格式
    if "action" in result:
        return await send_card_action_response(None, result)

    return result
