"""
Approval Manager - 审核机器人C核心模块
处理审批请求的创建、发送、回调和状态管理
"""

import asyncio
import time
from enum import Enum
from typing import Callable, Dict, Optional


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalRequest:
    """审批请求类"""

    def __init__(
        self,
        approval_id: str,
        user_id: str,
        command: str,
        description: str,
        risk_level: str,
        source: str,
        status: ApprovalStatus,
        created_at: float,
        expires_at: float,
        resolved_at: Optional[float] = None,
        resolved_by: Optional[str] = None,
        reason: Optional[str] = None,
        callback_url: Optional[str] = None
    ):
        self.approval_id = approval_id
        self.user_id = user_id
        self.command = command
        self.description = description
        self.risk_level = risk_level
        self.source = source
        self.status = status
        self.created_at = created_at
        self.expires_at = expires_at
        self.resolved_at = resolved_at
        self.resolved_by = resolved_by
        self.reason = reason
        self.callback_url = callback_url


class ApprovalManager:
    """审核管理器 - 机器人C的核心"""

    def __init__(self, feishu_client=None, websocket_manager=None):
        self.requests: Dict[str, ApprovalRequest] = {}
        self.feishu_client = feishu_client
        self.websocket_manager = websocket_manager
        self.callbacks: Dict[str, Callable] = {}

    def create_approval(
        self,
        user_id: str,
        command: str,
        description: str = "",
        risk_level: str = "medium",
        source: str = "opencode",
        callback_url: Optional[str] = None,
        expires_in: int = 3600
    ) -> ApprovalRequest:
        """创建新的审批请求"""
        approval_id = f"APR-{int(time.time())}-{hash(command) % 10000:04d}"

        request = ApprovalRequest(
            approval_id=approval_id,
            user_id=user_id,
            command=command,
            description=description,
            risk_level=risk_level,
            source=source,
            status=ApprovalStatus.PENDING,
            created_at=time.time(),
            expires_at=time.time() + expires_in,
            callback_url=callback_url
        )

        self.requests[approval_id] = request
        print(f"[ApprovalManager] Created: {approval_id} for user {user_id}")

        return request

    def get_approval(self, approval_id: str) -> Optional[ApprovalRequest]:
        """获取审批请求"""
        return self.requests.get(approval_id)

    def list_pending(self) -> list:
        """列出所有待审批请求"""
        return [
            req for req in self.requests.values()
            if req.status == ApprovalStatus.PENDING and req.expires_at > time.time()
        ]

    def approve(
        self,
        approval_id: str,
        resolved_by: str,
        reason: Optional[str] = None
    ) -> Optional[ApprovalRequest]:
        """批准请求"""
        request = self.requests.get(approval_id)
        if not request:
            return None

        if request.status != ApprovalStatus.PENDING:
            print(f"[ApprovalManager] Cannot approve {approval_id}: status is {request.status}")
            return None

        request.status = ApprovalStatus.APPROVED
        request.resolved_at = time.time()
        request.resolved_by = resolved_by
        request.reason = reason

        print(f"[ApprovalManager] Approved: {approval_id} by {resolved_by}")

        # 触发回调
        self._trigger_callback(request)

        return request

    def reject(
        self,
        approval_id: str,
        resolved_by: str,
        reason: Optional[str] = None
    ) -> Optional[ApprovalRequest]:
        """拒绝请求"""
        request = self.requests.get(approval_id)
        if not request:
            return None

        if request.status != ApprovalStatus.PENDING:
            print(f"[ApprovalManager] Cannot reject {approval_id}: status is {request.status}")
            return None

        request.status = ApprovalStatus.REJECTED
        request.resolved_at = time.time()
        request.resolved_by = resolved_by
        request.reason = reason

        print(f"[ApprovalManager] Rejected: {approval_id} by {resolved_by}")

        # 触发回调
        self._trigger_callback(request)

        return request

    def register_callback(self, approval_id: str, callback: Callable):
        """注册审批结果回调"""
        self.callbacks[approval_id] = callback

    def _trigger_callback(self, request: ApprovalRequest):
        """触发回调通知"""
        # 1. WebSocket 回调
        if request.approval_id in self.callbacks:
            try:
                callback = self.callbacks[request.approval_id]
                asyncio.create_task(callback(request))
            except Exception as e:
                print(f"[ApprovalManager] Callback error: {e}")

        # 2. HTTP 回调
        if request.callback_url:
            # TODO: 实现HTTP回调
            print(f"[ApprovalManager] HTTP callback to {request.callback_url}")

    def to_dict(self, request: ApprovalRequest) -> dict:
        """转换为字典"""
        return {
            "approval_id": request.approval_id,
            "user_id": request.user_id,
            "command": request.command,
            "description": request.description,
            "risk_level": request.risk_level,
            "source": request.source,
            "status": request.status.value if hasattr(request.status, 'value') else str(request.status),
            "created_at": request.created_at,
            "expires_at": request.expires_at,
            "resolved_at": request.resolved_at,
            "resolved_by": request.resolved_by,
            "reason": request.reason,
        }


class FeishuApprovalCardBuilder:
    """飞书审批卡片构建器"""

    @staticmethod
    def build_approval_card(request: ApprovalRequest) -> dict:
        """构建审批请求卡片"""
        risk_colors = {
            "low": "green",
            "medium": "orange",
            "high": "red",
            "critical": "red"
        }
        risk_color = risk_colors.get(request.risk_level, "blue")

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "🔔 新的审批请求"
                },
                "template": risk_color
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**风险等级:** {request.risk_level.upper()}\n**来源:** {request.source}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**命令:**\n```\n{request.command}\n```"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**描述:** {request.description or '无'}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**审批ID:** `{request.approval_id}`"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "✅ 批准"
                            },
                            "type": "primary",
                            "value": {
                                "action": "approve",
                                "approval_id": request.approval_id
                            }
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "❌ 拒绝"
                            },
                            "type": "danger",
                            "value": {
                                "action": "reject",
                                "approval_id": request.approval_id
                            }
                        }
                    ]
                }
            ]
        }

    @staticmethod
    def build_result_card(request: ApprovalRequest) -> dict:
        """构建审批结果卡片"""
        status_icons = {
            ApprovalStatus.APPROVED: "✅",
            ApprovalStatus.REJECTED: "❌",
            ApprovalStatus.EXPIRED: "⏰",
            ApprovalStatus.CANCELLED: "🚫"
        }
        icon = status_icons.get(request.status, "❓")

        status_text = {
            ApprovalStatus.APPROVED: "已批准",
            ApprovalStatus.REJECTED: "已拒绝",
            ApprovalStatus.EXPIRED: "已过期",
            ApprovalStatus.CANCELLED: "已取消"
        }

        template = "green" if request.status == ApprovalStatus.APPROVED else "red"

        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**命令:** `{request.command}`"
                }
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**审批人:** {request.resolved_by or '未知'}"
                }
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**审批ID:** `{request.approval_id}`"
                }
            }
        ]

        if request.reason:
            elements.insert(2, {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**理由:** {request.reason}"
                }
            })

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"{icon} 审批{status_text.get(request.status, '未知状态')}"
                },
                "template": template
            },
            "elements": elements
        }


# 全局审批管理器实例
approval_manager = ApprovalManager()
