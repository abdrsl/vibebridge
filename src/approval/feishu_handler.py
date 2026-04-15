"""
Feishu Approval Handler - 飞书审批交互处理
处理审批卡片的发送和回调
"""

import json
import os
from typing import Optional

from .manager import (
    ApprovalStatus,
    FeishuApprovalCardBuilder,
    approval_manager,
)

# 导入Feishu客户端
from src.legacy.feishu_client import feishu_client


class FeishuApprovalHandler:
    """飞书审批处理器 - 机器人C的交互实现"""

    def __init__(self):
        self.webhook_url = os.getenv("FEISHU_APPROVAL_WEBHOOK_URL")
        self.app_id = os.getenv("FEISHU_APP_ID")
        self.app_secret = os.getenv("FEISHU_APP_SECRET")
        self.feishu_client = feishu_client
        self.default_chat_id = os.getenv(
            "FEISHU_DEFAULT_CHAT_ID", "oc_REDACTED_CHAT_ID"
        )

    async def send_approval_request(
        self, user_id: str, approval_id: str, chat_id: Optional[str] = None
    ) -> bool:
        """
        发送审批请求到飞书

        Args:
            user_id: 飞书用户ID (ou_xxx)
            approval_id: 审批请求ID
            chat_id: 可选的群聊ID，如果不提供则发送给个人
        """
        request = approval_manager.get_approval(approval_id)
        if not request:
            print(f"[FeishuApproval] Approval not found: {approval_id}")
            return False

        # 构建卡片
        card = FeishuApprovalCardBuilder.build_approval_card(request)

        # 发送方式1: 通过Webhook (机器人A)
        if self.webhook_url:
            success = await self._send_via_webhook(card)
            if success:
                print(f"[FeishuApproval] Sent via webhook: {approval_id}")
                return True

        # 发送方式2: 通过Bot API (机器人C)
        # 如果没有提供chat_id，使用默认chat_id（避免open_id跨应用问题）
        target_chat_id = chat_id if chat_id else self.default_chat_id
        if target_chat_id:
            success = await self._send_to_chat(target_chat_id, card)
            if success:
                print(f"[FeishuApproval] Sent to chat {target_chat_id}: {approval_id}")
                return success

        # 如果既没有chat_id也没有default_chat_id，尝试发送给用户（可能失败）
        print(
            f"[FeishuApproval] No chat_id provided, attempting to send to user (may fail due to open_id cross app)"
        )
        success = await self._send_to_user(user_id, card)
        if success:
            print(f"[FeishuApproval] Sent to user {user_id}: {approval_id}")

        return success

    async def _send_via_webhook(self, card: dict) -> bool:
        """通过Webhook发送卡片"""
        import aiohttp

        if not self.webhook_url:
            return False

        payload = {"msg_type": "interactive", "card": card}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("code") == 0
                    return False
        except Exception as e:
            print(f"[FeishuApproval] Webhook send error: {e}")
            return False

    async def _send_to_user(self, user_id: str, card: dict) -> bool:
        """通过Bot API发送给用户"""
        try:
            print(f"[FeishuApproval] Sending card to user {user_id}")

            # 确定receive_id类型
            receive_id_type = self._get_receive_id_type(user_id)
            print(
                f"[FeishuApproval] Using receive_id_type: {receive_id_type} for {user_id}"
            )

            # 首先尝试发送交互式卡片
            result = await self.feishu_client.send_interactive_card(
                user_id, card, receive_id_type=receive_id_type
            )

            if result and "error" not in result:
                print(f"[FeishuApproval] Card sent successfully to user {user_id}")
                return True
            else:
                # 如果卡片发送失败，尝试发送文本消息作为备用
                print(f"[FeishuApproval] Card send failed, trying text message")

                # 从卡片中提取文本内容
                card_text = self._extract_text_from_card(card)
                if card_text:
                    text_result = await self.feishu_client.send_text_message(
                        user_id, card_text, receive_id_type=receive_id_type
                    )
                    if text_result and "error" not in text_result:
                        print(f"[FeishuApproval] Text message sent as fallback")
                        return True

                print(f"[FeishuApproval] Failed to send to user {user_id}: {result}")
                return False

        except Exception as e:
            print(f"[FeishuApproval] Error sending to user {user_id}: {e}")
            return False

    async def _send_to_chat(self, chat_id: str, card: dict) -> bool:
        """通过Bot API发送到群聊"""
        try:
            print(f"[FeishuApproval] Sending card to chat {chat_id}")

            # 确定receive_id类型
            receive_id_type = self._get_receive_id_type(chat_id)
            print(
                f"[FeishuApproval] Using receive_id_type: {receive_id_type} for {chat_id}"
            )

            result = await self.feishu_client.send_interactive_card(
                chat_id, card, receive_id_type=receive_id_type
            )

            if result and "error" not in result:
                print(f"[FeishuApproval] Card sent successfully to chat {chat_id}")
                return True
            else:
                print(f"[FeishuApproval] Failed to send to chat {chat_id}: {result}")
                return False

        except Exception as e:
            print(f"[FeishuApproval] Error sending to chat {chat_id}: {e}")
            return False

    def _extract_text_from_card(self, card: dict) -> str:
        """从卡片中提取文本内容，用于备用文本消息"""
        try:
            elements = card.get("elements", [])
            text_parts = []

            for element in elements:
                if element.get("tag") == "div" and "text" in element:
                    text_content = element["text"].get("content", "")
                    if text_content:
                        # 清理markdown格式
                        text_content = text_content.replace("**", "").replace("`", "")
                        text_parts.append(text_content)
                elif element.get("tag") == "markdown":
                    text_content = element.get("content", "")
                    if text_content:
                        text_parts.append(text_content)

            if text_parts:
                return "\n".join(text_parts[:3])  # 限制为前3个部分

            # 如果有标题，使用标题
            header = card.get("header", {})
            title = header.get("title", {})
            if isinstance(title, dict):
                title_text = title.get("content", "")
                if title_text:
                    return title_text

            return "审批请求通知（请查看卡片详情）"

        except Exception as e:
            print(f"[FeishuApproval] Error extracting text from card: {e}")
            return "新的审批请求等待处理"

    def _get_receive_id_type(self, receive_id: str) -> str:
        """根据receive_id判断其类型"""
        if receive_id.startswith("ou_"):
            return "open_id"
        elif receive_id.startswith("oc_"):
            return "chat_id"
        elif receive_id.startswith("on_"):
            return "union_id"
        else:
            # 默认假设是chat_id，因为历史代码使用chat_id
            return "chat_id"

    async def update_approval_card(self, message_id: str, approval_id: str) -> bool:
        """更新审批卡片为结果状态"""
        request = approval_manager.get_approval(approval_id)
        if not request:
            return False

        # 构建结果卡片但不使用（TODO: 实现卡片更新API）
        FeishuApprovalCardBuilder.build_result_card(request)

        # TODO: 实现卡片更新API
        print(f"[FeishuApproval] Update card {message_id} for {approval_id}")
        return True

    async def handle_feishu_callback(self, data: dict) -> dict:
        """
        处理飞书回调

        支持两种回调类型:
        1. 卡片按钮点击事件
        2. 消息事件
        """
        print(f"[FeishuApproval] Received callback: {json.dumps(data, indent=2)}")

        # 处理URL验证
        if "challenge" in data:
            return {"challenge": data["challenge"]}

        # 获取事件类型
        event_type = data.get("header", {}).get("event_type", "")

        # 处理卡片按钮点击
        if event_type == "interactive_card_action":
            return await self._handle_card_action(data)

        # 处理消息事件
        if event_type == "im.message.receive_v1":
            return await self._handle_message(data)

        return {"success": True, "message": "Event ignored"}

    async def _handle_card_action(self, data: dict) -> dict:
        """处理卡片按钮点击"""
        event = data.get("event", {})
        action_value = event.get("action_value", {})
        user = event.get("user", {})

        action = action_value.get("action")
        approval_id = action_value.get("approval_id")
        user_id = user.get("user_id")

        if not action or not approval_id:
            return {"success": False, "error": "Missing action or approval_id"}

        print(f"[FeishuApproval] Card action: {action} for {approval_id} by {user_id}")

        if action == "approve":
            request = approval_manager.approve(approval_id, user_id, "通过飞书卡片批准")
        elif action == "reject":
            request = approval_manager.reject(approval_id, user_id, "通过飞书卡片拒绝")
        else:
            return {"success": False, "error": f"Unknown action: {action}"}

        if not request:
            return {"success": False, "error": "Approval not found or already resolved"}

        # 更新飞书卡片显示结果
        # TODO: 实现卡片更新

        return {
            "success": True,
            "approval_id": approval_id,
            "status": request.status.value,
            "message": f"已{('批准' if request.status == ApprovalStatus.APPROVED else '拒绝')}",
        }

    async def _handle_message(self, data: dict) -> dict:
        """处理消息事件（文字审批）"""
        event = data.get("event", {})
        message = event.get("message", {})
        sender = event.get("sender", {})

        content = json.loads(message.get("content", "{}"))
        text = content.get("text", "").strip()
        user_id = sender.get("sender_id", {}).get("user_id")

        print(f"[FeishuApproval] Message from {user_id}: {text}")

        # 解析审批命令
        # 格式: "批准 APR-xxx" 或 "拒绝 APR-xxx [理由]"
        # 也支持带引号或回复前缀的格式，如: 回复"批准 APR-xxx

        # 清理文本：移除常见的回复前缀
        clean_text = text
        reply_prefixes = ['回复"', "回复：", "回复:", "回复 "]
        for prefix in reply_prefixes:
            if clean_text.startswith(prefix):
                clean_text = clean_text[len(prefix) :]
                break

        # 检查批准命令
        if clean_text.startswith("批准 ") or clean_text.startswith("通过 "):
            parts = clean_text.split()
            if len(parts) >= 2:
                approval_id = parts[1]
                request = approval_manager.approve(
                    approval_id, user_id, "通过文字消息批准"
                )
                if request:
                    return {"success": True, "message": f"✅ 已批准: {approval_id}"}
                return {"success": False, "error": "审批请求不存在或已处理"}

        # 检查拒绝命令
        elif clean_text.startswith("拒绝 ") or clean_text.startswith("驳回 "):
            parts = clean_text.split(maxsplit=2)
            if len(parts) >= 2:
                approval_id = parts[1]
                reason = parts[2] if len(parts) > 2 else "通过文字消息拒绝"
                request = approval_manager.reject(approval_id, user_id, reason)
                if request:
                    return {"success": True, "message": f"❌ 已拒绝: {approval_id}"}
                return {"success": False, "error": "审批请求不存在或已处理"}

        return {"success": True, "message": "Message processed"}


# 全局处理器实例
feishu_approval_handler = FeishuApprovalHandler()
