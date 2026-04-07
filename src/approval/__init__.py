"""
Approval System - 审核机器人C
"""

from src.approval.feishu_handler import FeishuApprovalHandler, feishu_approval_handler
from src.approval.manager import (
    ApprovalManager,
    ApprovalRequest,
    ApprovalStatus,
    FeishuApprovalCardBuilder,
    approval_manager,
)
from src.approval.routes import (
    api_approve,
    api_create_approval,
    api_feishu_callback,
    api_get_approval,
    api_list_pending,
    api_reject,
    register_approval_routes,
)

__all__ = [
    'ApprovalManager',
    'ApprovalRequest',
    'ApprovalStatus',
    'FeishuApprovalCardBuilder',
    'approval_manager',
    'FeishuApprovalHandler',
    'feishu_approval_handler',
    'register_approval_routes',
    'api_create_approval',
    'api_get_approval',
    'api_list_pending',
    'api_approve',
    'api_reject',
    'api_feishu_callback',
]
