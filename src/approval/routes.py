"""
Approval API Routes - 审批系统API端点
"""

from typing import Optional

from fastapi import Request
from pydantic import BaseModel

from .feishu_handler import feishu_approval_handler
from .manager import approval_manager


# 请求模型
class CreateApprovalRequest(BaseModel):
    user_id: str
    command: str
    description: Optional[str] = ""
    risk_level: Optional[str] = "medium"
    source: Optional[str] = "opencode"
    callback_url: Optional[str] = None
    expires_in: Optional[int] = 3600


class ApprovalResponse(BaseModel):
    success: bool
    approval_id: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None


# API 处理函数
async def api_create_approval(request: Request):
    """创建审批请求"""
    try:
        data = await request.json()

        user_id = data.get("user_id")
        command = data.get("command")

        if not user_id or not command:
            return {"success": False, "error": "缺少必需参数: user_id 和 command"}

        # 创建审批请求
        approval = approval_manager.create_approval(
            user_id=user_id,
            command=command,
            description=data.get("description", ""),
            risk_level=data.get("risk_level", "medium"),
            source=data.get("source", "opencode"),
            callback_url=data.get("callback_url"),
            expires_in=data.get("expires_in", 3600),
        )

        # 发送到飞书
        chat_id = data.get("chat_id")
        await feishu_approval_handler.send_approval_request(
            user_id=user_id, approval_id=approval.approval_id, chat_id=chat_id
        )

        return {
            "success": True,
            "approval_id": approval.approval_id,
            "status": approval.status.value,
            "expires_at": approval.expires_at,
        }

    except Exception as e:
        print(f"[ApprovalAPI] Create error: {e}")
        return {"success": False, "error": str(e)}


async def api_get_approval(request: Request):
    """获取审批请求状态"""
    approval_id = request.path_params.get("approval_id")

    approval = approval_manager.get_approval(approval_id)
    if not approval:
        return {"success": False, "error": "审批请求不存在"}

    return {"success": True, "approval": approval_manager.to_dict(approval)}


async def api_list_pending(request: Request):
    """列出待审批请求"""
    pending = approval_manager.list_pending()

    return {
        "success": True,
        "count": len(pending),
        "approvals": [approval_manager.to_dict(req) for req in pending],
    }


async def api_approve(request: Request):
    """批准审批请求（API方式）"""
    try:
        data = await request.json()
        approval_id = data.get("approval_id")
        user_id = data.get("user_id")
        reason = data.get("reason", "通过API批准")

        if not approval_id or not user_id:
            return {"success": False, "error": "缺少 approval_id 或 user_id"}

        approval = approval_manager.approve(approval_id, user_id, reason)
        if not approval:
            return {"success": False, "error": "审批请求不存在或已处理"}

        return {
            "success": True,
            "approval_id": approval_id,
            "status": approval.status.value,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


async def api_reject(request: Request):
    """拒绝审批请求（API方式）"""
    try:
        data = await request.json()
        approval_id = data.get("approval_id")
        user_id = data.get("user_id")
        reason = data.get("reason", "通过API拒绝")

        if not approval_id or not user_id:
            return {"success": False, "error": "缺少 approval_id 或 user_id"}

        approval = approval_manager.reject(approval_id, user_id, reason)
        if not approval:
            return {"success": False, "error": "审批请求不存在或已处理"}

        return {
            "success": True,
            "approval_id": approval_id,
            "status": approval.status.value,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


async def api_feishu_callback(request: Request):
    """飞书回调处理"""
    try:
        data = await request.json()
        result = await feishu_approval_handler.handle_feishu_callback(data)
        return result
    except Exception as e:
        print(f"[ApprovalAPI] Feishu callback error: {e}")
        return {"success": False, "error": str(e)}


# 注册路由函数
def register_approval_routes(app):
    """注册审批系统路由到FastAPI应用"""

    # 审批API
    app.post("/api/approval/create")(api_create_approval)
    app.get("/api/approval/{approval_id}")(api_get_approval)
    app.get("/api/approval/pending/list")(api_list_pending)
    app.post("/api/approval/approve")(api_approve)
    app.post("/api/approval/reject")(api_reject)

    # 飞书回调
    app.post("/webhook/feishu/approval")(api_feishu_callback)

    print("✅ Approval API routes registered")
