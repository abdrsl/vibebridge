"""
飞书卡片交互处理器
处理卡片按钮点击等交互事件
"""

import json
from typing import Dict, Any
from fastapi import BackgroundTasks

from .feishu_webhook_handler import (
    handle_card_action,
    handle_feishu_message,
)
from .feishu_client import feishu_client


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
    # 记录完整的请求体用于调试
    print(
        f"[Card] Received webhook body: {json.dumps(body, ensure_ascii=False)[:500]}..."
    )

    # 支持飞书事件订阅 v1 和 v2 格式
    schema = body.get("schema", "")
    event = {}
    event_type = ""

    if schema == "2.0":
        # v2 格式
        header = body.get("header", {})
        event_type = header.get("event_type", "")
        event = body.get("event", {})
        print(f"[Card] v2 format - event_type: {event_type}, header: {header}")
    else:
        # v1 格式
        event = body.get("event", {})
        event_type = body.get("event_type", "")
        print(f"[Card] v1 format - event_type: {event_type}")

    if event_type == "im.message.receive_v1":
        print(f"[Card] Handling IM message receive event")
        return await handle_im_message(event, background_tasks)

    elif event_type == "card.action.trigger":
        print(f"[Card] Handling card action trigger event")
        return await handle_card_action_trigger(event, background_tasks)

    print(f"[Card] Unhandled event type: {event_type}")
    return {
        "ok": True,
        "skipped": True,
        "reason": f"Event type {event_type} not handled",
    }


async def handle_card_action_trigger(
    event: Dict[str, Any],
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """
    处理卡片动作触发事件 (card.action.trigger)
    这是飞书新的卡片交互事件类型
    """
    print(
        f"[Card] Processing card action trigger: {json.dumps(event, ensure_ascii=False)[:300]}..."
    )

    # 获取动作信息
    action = event.get("action", {})
    action_value = action.get("value", "{}")
    operator = event.get("operator", {})
    context = event.get("context", {})

    # 解析动作数据（处理多重转义JSON）
    action_data = None
    value_str = action_value if isinstance(action_value, str) else str(action_value)

    print(f"[Card] Action value string: {value_str[:200]}...")

    # 尝试多次解析，处理多重转义
    max_attempts = 5
    current_str = value_str

    for attempt in range(max_attempts):
        try:
            parsed = json.loads(current_str)
            print(f"[Card] JSON parsed successfully on attempt {attempt + 1}")

            # 如果解析结果还是字符串，继续解析
            if isinstance(parsed, str):
                current_str = parsed
                print(f"[Card] Parsed result is still string, continuing...")
                continue
            else:
                # 得到了最终的字典对象
                action_data = parsed
                break

        except json.JSONDecodeError:
            # 尝试清理字符串后再解析
            try:
                cleaned = current_str.strip()
                # 移除外层引号
                if cleaned.startswith('"') and cleaned.endswith('"'):
                    cleaned = cleaned[1:-1]
                    # 处理转义字符
                    cleaned = cleaned.replace('\\"', '"')
                    current_str = cleaned
                    print(
                        f"[Card] Cleaned string for next attempt: {current_str[:100]}..."
                    )
                    continue
            except Exception as e:
                print(f"[Card] Cleaning failed: {e}")
                break

    if not action_data:
        print(f"[Card] Failed to parse action value after {max_attempts} attempts")
        print(f"[Card] Final raw value: {value_str[:200]}...")
        # 返回成功响应避免飞书显示错误
        return {"ok": True, "action": "processed", "response": {}}

    if not action_data:
        print(f"[Card] No action data parsed")
        return {"ok": True, "action": "processed", "response": {}}

    print(
        f"[Card] Parsed action data from trigger: {json.dumps(action_data, ensure_ascii=False)}"
    )

    # 获取操作者信息（优先使用open_id，其次user_id）
    # open_id是飞书用户的唯一标识，session中存储的就是open_id
    user_id = operator.get("open_id", "")
    if not user_id:
        user_id = operator.get("user_id", "unknown")

    # 获取聊天上下文
    chat_id = context.get("open_chat_id", "")
    if not chat_id:
        # 尝试其他可能的字段
        chat_id = context.get("chat_id", "")

    # 如果还是没有chat_id，尝试从host推断
    if not chat_id:
        host = event.get("host", "")
        if host == "im_message":
            # 对于im_message，可能需要从其他字段获取
            # 暂时留空，handle_card_action会处理
            pass

    # 详细日志
    print(f"[Card] Operator details: {json.dumps(operator, ensure_ascii=False)}")
    print(f"[Card] Context details: {json.dumps(context, ensure_ascii=False)}")
    print(
        f"[Card] Extracted - open_id: {operator.get('open_id')}, user_id: {operator.get('user_id')}, effective_user_id: {user_id}"
    )
    print(
        f"[Card] Card trigger - action: {action_data.get('action')}, user: {user_id}, chat: {chat_id}"
    )

    # 调用原有的卡片动作处理
    if isinstance(action_data, dict) and "action" in action_data:
        return await handle_card_action(
            action_data,
            chat_id,
            user_id,
            background_tasks,
        )

    print(f"[Card] Invalid action data format: {action_data}")
    return {"ok": True, "action": "processed", "response": {}}


async def handle_im_message(
    event: Dict[str, Any],
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """处理IM消息（包括卡片交互）"""
    message = event.get("message", {})
    sender = event.get("sender", {})
    content_str = message.get("content", "{}")
    message_type = message.get("message_type", "text")

    print(
        f"[Card] Message details - type: {message_type}, content length: {len(content_str)}"
    )
    print(f"[Card] Sender: {sender}")

    try:
        content_obj = json.loads(content_str)
    except json.JSONDecodeError as e:
        print(f"[Card] JSON decode error for content: {e}")
        content_obj = {}

    chat_id = message.get("chat_id", "")
    sender_id = sender.get("sender_id", {}).get("open_id", "unknown")

    print(f"[Card] Chat ID: {chat_id}, Sender ID: {sender_id}")

    # 检查是否是卡片交互消息
    if message_type == "interactive":
        print(f"[Card] Received interactive message: {content_str[:500]}...")
        # 卡片交互消息，格式为 {"value": "JSON字符串"}
        value_str = content_obj.get("value", "")
        print(f"[Card] Value string length: {len(value_str)}")
        if value_str:
            try:
                action_data = json.loads(value_str)
                print(
                    f"[Card] Parsed action data: {json.dumps(action_data, ensure_ascii=False)}"
                )
                if isinstance(action_data, dict) and "action" in action_data:
                    # 这是卡片动作
                    print(
                        f"[Card] Handling card action: {action_data.get('action')}, "
                        f"session: {action_data.get('session_id')}, "
                        f"chat: {chat_id}, user: {sender_id}"
                    )
                    return await handle_card_action(
                        action_data,
                        chat_id,
                        sender_id,
                        background_tasks,
                    )
                else:
                    print(f"[Card] Action data missing 'action' key: {action_data}")
            except json.JSONDecodeError as e:
                print(f"[Card] JSON decode error for value string: {e}")
                print(f"[Card] Value string that failed: {value_str[:200]}...")
                pass
        else:
            print(f"[Card] No value string in content object")

        # 卡片交互但无法解析，返回成功响应
        print(f"[Card] Unparseable card interaction, returning success")
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
    challenge: str | None,
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
        print(f"[Card] URL verification challenge: {challenge}")
        return {"challenge": challenge}

    print(f"[Card] Preparing response for action result: {action_result}")

    if action_result.get("ok", False):
        # 成功，返回空对象或成功结构
        # 飞书可能接受空对象 {} 或 {"success": true} 或 {"code": 0}
        # 先尝试返回空对象，如果不行再尝试其他格式
        response = {}
        print(f"[Card] Returning success response: {response}")
        return response
    else:
        # 失败，返回错误信息
        # 飞书期望的格式: {"code": 200340, "msg": "错误信息"}
        error_msg = action_result.get("error", "Unknown error")
        response = {
            "code": 200340,
            "msg": error_msg,
        }
        print(f"[Card] Returning error response: {response}")
        return response


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
        print(f"[Card] Action result: {result}")
        response = await send_card_action_response("", result)
        print(f"[Card] Sending response to Feishu: {response}")
        return response

    return result
