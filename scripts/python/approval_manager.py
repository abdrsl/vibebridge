# OpenClaw/OpenCode 统一审批管理系统
# Unified Approval Management System
#
# 架构说明:
# - OpenClaw 通过 WebSocket 连接到桥接服务器
# - OpenCode 通过 Webhook 连接到桥接服务器
# - 飞书有两个机器人:
#   * 机器人A (Webhook): 发送审批消息到飞书
#   * 机器人B (WebSocket): 与 OpenClaw 实时交互
# - 审批流程:
#   1. OpenClaw 检测到高风险操作
#   2. 通过 WebSocket 发送审批请求到桥接服务器
#   3. 桥接服务器通过 Webhook 机器人发送审批消息到飞书
#   4. 用户在飞书中点击批准/拒绝
#   5. 飞书 Webhook 回调到桥接服务器
#   6. 桥接服务器通知 OpenClaw 审批结果

import json
import time
import asyncio
import hashlib
import base64
import hmac
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
from aiohttp import web


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ApprovalRequest:
    """审批请求"""

    approval_id: str
    user_id: str
    command: str
    description: str
    risk_level: str
    status: str = "pending"
    created_at: float = 0
    expires_at: float = 0
    approved_at: Optional[float] = None
    approved_by: Optional[str] = None
    source: str = "openclaw"  # openclaw 或 opencode
    callback_url: Optional[str] = None  # 审批结果回调URL

    def __post_init__(self):
        if self.created_at == 0:
            self.created_at = time.time()
        if self.expires_at == 0:
            self.expires_at = self.created_at + 3600  # 默认1小时过期

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


class ApprovalManager:
    """审批管理器 - 统一管理 OpenClaw 和 OpenCode 的审批请求"""

    def __init__(self, feishu_webhook_url: str, feishu_secret: Optional[str] = None):
        self.feishu_webhook_url = feishu_webhook_url
        self.feishu_secret = feishu_secret
        self.approvals: Dict[str, ApprovalRequest] = {}
        self.pending_callbacks: Dict[str, asyncio.Future] = {}
        self.ws_clients: List[web.WebSocketResponse] = []
        self.logger = None  # 需要外部设置

    def set_logger(self, logger):
        self.logger = logger

    def log(self, message: str):
        if self.logger:
            self.logger.info(f"[ApprovalManager] {message}")
        else:
            print(f"[ApprovalManager] {message}")

    async def create_approval(
        self,
        user_id: str,
        command: str,
        description: str,
        risk_level: str,
        source: str = "openclaw",
        callback_url: Optional[str] = None,
    ) -> ApprovalRequest:
        """创建审批请求"""

        # 生成审批ID
        timestamp = int(time.time())
        random_str = hashlib.md5(f"{user_id}{command}{timestamp}".encode()).hexdigest()[
            :8
        ]
        approval_id = f"APR-{timestamp}-{random_str}"

        # 创建请求
        request = ApprovalRequest(
            approval_id=approval_id,
            user_id=user_id,
            command=command,
            description=description,
            risk_level=risk_level,
            source=source,
            callback_url=callback_url,
        )

        # 保存
        self.approvals[approval_id] = request
        self.log(f"创建审批请求: {approval_id} [{risk_level}] from {source}")

        # 发送到飞书
        await self._send_to_feishu(request)

        # 创建等待Future
        future = asyncio.get_event_loop().create_future()
        self.pending_callbacks[approval_id] = future

        # 设置超时
        asyncio.create_task(self._check_timeout(approval_id))

        return request

    async def _send_to_feishu(self, request: ApprovalRequest):
        """发送审批消息到飞书 (通过 Webhook 机器人)"""

        # 构建飞书消息卡片
        risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴", "critical": "🚨"}
        emoji = risk_emoji.get(request.risk_level, "⚪")

        timestamp = datetime.fromtimestamp(request.created_at).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        card = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": f"{emoji} 需要您的审批"},
                    "template": "red"
                    if request.risk_level in ["high", "critical"]
                    else "yellow",
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**来源:** {request.source.upper()}\n"
                            f"**操作:** `{request.command}`\n"
                            f"**风险等级:** {emoji} {request.risk_level.upper()}\n"
                            f"**说明:** {request.description}\n"
                            f"**时间:** {timestamp}\n"
                            f"**审批ID:** `{request.approval_id}`",
                        },
                    },
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {"tag": "plain_text", "content": "✅ 批准"},
                                "type": "primary",
                                "value": {
                                    "action": "approve",
                                    "approval_id": request.approval_id,
                                },
                            },
                            {
                                "tag": "button",
                                "text": {"tag": "plain_text", "content": "❌ 拒绝"},
                                "type": "danger",
                                "value": {
                                    "action": "reject",
                                    "approval_id": request.approval_id,
                                },
                            },
                        ],
                    },
                ],
            },
        }

        # 发送请求
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Content-Type": "application/json"}

                # 如果有secret，添加签名
                if self.feishu_secret:
                    timestamp = str(int(time.time()))
                    string_to_sign = f"{timestamp}\n{self.feishu_secret}"
                    sign = base64.b64encode(
                        hmac.new(
                            self.feishu_secret.encode(),
                            string_to_sign.encode(),
                            digestmod=hashlib.sha256,
                        ).digest()
                    ).decode()
                    card["timestamp"] = timestamp
                    card["sign"] = sign

                async with session.post(
                    self.feishu_webhook_url, headers=headers, json=card
                ) as resp:
                    if resp.status == 200:
                        self.log(f"✅ 审批消息已发送到飞书: {request.approval_id}")
                    else:
                        self.log(f"❌ 发送失败: {resp.status}")

        except Exception as e:
            self.log(f"❌ 发送异常: {e}")

    async def handle_feishu_callback(self, data: dict) -> dict:
        """处理飞书 Webhook 回调"""

        # 解析回调数据
        action = data.get("action", "")
        approval_id = data.get("approval_id", "")
        user_id = data.get("user_id", "unknown")

        self.log(f"📥 收到飞书回调: {approval_id}, 动作: {action}")

        if approval_id not in self.approvals:
            return {"success": False, "error": "审批请求不存在或已过期"}

        request = self.approvals[approval_id]

        if request.status != "pending":
            return {"success": False, "error": f"审批请求已{request.status}"}

        # 更新状态
        if action == "approve":
            request.status = "approved"
            request.approved_by = user_id
            request.approved_at = time.time()
            self.log(f"✅ 审批通过: {approval_id} by {user_id}")
        elif action == "reject":
            request.status = "rejected"
            request.approved_by = user_id
            request.approved_at = time.time()
            self.log(f"❌ 审批拒绝: {approval_id} by {user_id}")
        else:
            return {"success": False, "error": "未知的操作类型"}

        # 通知等待的future
        if approval_id in self.pending_callbacks:
            future = self.pending_callbacks[approval_id]
            if not future.done():
                future.set_result(request)

        # 通知源系统
        await self._notify_source(request)

        return {"success": True, "approval_id": approval_id, "status": request.status}

    async def _notify_source(self, request: ApprovalRequest):
        """通知源系统审批结果"""

        if request.source == "openclaw":
            # 通过 WebSocket 通知 OpenClaw
            await self._notify_openclaw(request)
        elif request.source == "opencode":
            # 通过 Webhook 回调通知 OpenCode
            await self._notify_opencode(request)

    async def _notify_openclaw(self, request: ApprovalRequest):
        """通过 WebSocket 通知 OpenClaw"""

        message = {
            "type": "approval_result",
            "approval_id": request.approval_id,
            "status": request.status,
            "approved_by": request.approved_by,
            "approved_at": request.approved_at,
        }

        # 广播给所有 WebSocket 客户端
        disconnected = []
        for ws in self.ws_clients:
            try:
                await ws.send_json(message)
                self.log(f"📤 已通知 OpenClaw: {request.approval_id}")
            except:
                disconnected.append(ws)

        # 清理断开的连接
        for ws in disconnected:
            self.ws_clients.remove(ws)

    async def _notify_opencode(self, request: ApprovalRequest):
        """通过 Webhook 回调通知 OpenCode"""

        if not request.callback_url:
            self.log(f"⚠️  OpenCode 回调URL未设置: {request.approval_id}")
            return

        payload = {
            "approval_id": request.approval_id,
            "status": request.status,
            "approved_by": request.approved_by,
            "approved_at": request.approved_at,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(request.callback_url, json=payload) as resp:
                    if resp.status == 200:
                        self.log(f"✅ 已回调 OpenCode: {request.approval_id}")
                    else:
                        self.log(f"⚠️  OpenCode 回调失败: {resp.status}")
        except Exception as e:
            self.log(f"❌ OpenCode 回调异常: {e}")

    async def _check_timeout(self, approval_id: str):
        """检查审批超时"""

        await asyncio.sleep(3600)  # 1小时超时

        if approval_id in self.approvals:
            request = self.approvals[approval_id]
            if request.status == "pending":
                request.status = "expired"
                self.log(f"⏰ 审批超时: {approval_id}")

                # 通知等待的future
                if approval_id in self.pending_callbacks:
                    future = self.pending_callbacks[approval_id]
                    if not future.done():
                        future.set_result(request)

                # 通知源系统
                await self._notify_source(request)

    async def wait_for_approval(
        self, approval_id: str, timeout: float = 3600
    ) -> Optional[ApprovalRequest]:
        """等待审批结果"""

        if approval_id not in self.pending_callbacks:
            return None

        future = self.pending_callbacks[approval_id]

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            return None

    def get_approval(self, approval_id: str) -> Optional[ApprovalRequest]:
        """获取审批请求"""
        return self.approvals.get(approval_id)

    def list_pending(self) -> List[ApprovalRequest]:
        """列出待审批请求"""
        return [req for req in self.approvals.values() if req.status == "pending"]

    def register_ws_client(self, ws: web.WebSocketResponse):
        """注册 WebSocket 客户端"""
        self.ws_clients.append(ws)
        self.log(f"🟢 WebSocket 客户端已注册，当前连接数: {len(self.ws_clients)}")

    def unregister_ws_client(self, ws: web.WebSocketResponse):
        """注销 WebSocket 客户端"""
        if ws in self.ws_clients:
            self.ws_clients.remove(ws)
            self.log(f"🔴 WebSocket 客户端已断开，当前连接数: {len(self.ws_clients)}")


# Web 路由处理器
class ApprovalWebHandler:
    """Web 路由处理器"""

    def __init__(self, approval_manager: ApprovalManager):
        self.manager = approval_manager

    async def handle_create_approval(self, request: web.Request) -> web.Response:
        """处理创建审批请求"""

        try:
            data = await request.json()

            user_id = data.get("user_id")
            command = data.get("command")
            description = data.get("description", "")
            risk_level = data.get("risk_level", "medium")
            source = data.get("source", "opencode")
            callback_url = data.get("callback_url")

            if not user_id or not command:
                return web.json_response(
                    {"success": False, "error": "缺少必要参数"}, status=400
                )

            approval = await self.manager.create_approval(
                user_id=user_id,
                command=command,
                description=description,
                risk_level=risk_level,
                source=source,
                callback_url=callback_url,
            )

            return web.json_response(
                {
                    "success": True,
                    "approval_id": approval.approval_id,
                    "status": approval.status,
                    "expires_at": approval.expires_at,
                }
            )

        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def handle_feishu_webhook(self, request: web.Request) -> web.Response:
        """处理飞书 Webhook 回调"""

        try:
            data = await request.json()

            # 解析飞书卡片回调
            # 飞书按钮点击会发送 challenge 或 action 数据

            # 处理飞书验证
            if "challenge" in data:
                return web.json_response({"challenge": data["challenge"]})

            # 处理按钮点击
            action_data = data.get("action", {})
            value = action_data.get("value", {})

            result = await self.manager.handle_feishu_callback(
                {
                    "action": value.get("action"),
                    "approval_id": value.get("approval_id"),
                    "user_id": data.get("user_id", "unknown"),
                }
            )

            return web.json_response(result)

        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def handle_get_approval(self, request: web.Request) -> web.Response:
        """获取审批状态"""

        approval_id = request.match_info.get("approval_id")
        approval = self.manager.get_approval(approval_id)

        if not approval:
            return web.json_response(
                {"success": False, "error": "审批请求不存在"}, status=404
            )

        return web.json_response({"success": True, "approval": approval.to_dict()})

    async def handle_list_pending(self, request: web.Request) -> web.Response:
        """列出待审批请求"""

        pending = self.manager.list_pending()

        return web.json_response(
            {
                "success": True,
                "count": len(pending),
                "approvals": [a.to_dict() for a in pending],
            }
        )


# WebSocket 处理器
class ApprovalWebSocketHandler:
    """WebSocket 处理器 - 处理 OpenClaw 连接"""

    def __init__(self, approval_manager: ApprovalManager):
        self.manager = approval_manager

    async def handle(self, request: web.Request) -> web.WebSocketResponse:
        """处理 WebSocket 连接"""

        ws = web.WebSocketResponse()
        await ws.prepare(request)

        # 注册客户端
        self.manager.register_ws_client(ws)

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_message(ws, msg.data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    self.manager.log(f"WebSocket 错误: {ws.exception()}")
        finally:
            self.manager.unregister_ws_client(ws)

        return ws

    async def _handle_message(self, ws: web.WebSocketResponse, data: str):
        """处理 WebSocket 消息"""

        try:
            message = json.loads(data)
            msg_type = message.get("type")

            if msg_type == "create_approval":
                # OpenClaw 请求创建审批
                approval = await self.manager.create_approval(
                    user_id=message.get("user_id"),
                    command=message.get("command"),
                    description=message.get("description", ""),
                    risk_level=message.get("risk_level", "medium"),
                    source="openclaw",
                )

                # 返回审批ID
                await ws.send_json(
                    {
                        "type": "approval_created",
                        "approval_id": approval.approval_id,
                        "status": approval.status,
                    }
                )

            elif msg_type == "get_approval":
                # 查询审批状态
                approval_id = message.get("approval_id")
                approval = self.manager.get_approval(approval_id)

                if approval:
                    await ws.send_json(
                        {"type": "approval_status", "approval": approval.to_dict()}
                    )
                else:
                    await ws.send_json({"type": "error", "error": "审批请求不存在"})

            elif msg_type == "ping":
                await ws.send_json({"type": "pong"})

        except json.JSONDecodeError:
            await ws.send_json({"type": "error", "error": "无效的 JSON 格式"})
        except Exception as e:
            await ws.send_json({"type": "error", "error": str(e)})


# 使用示例
async def main():
    """示例：启动审批服务器"""

    # 配置
    FEISHU_WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
    FEISHU_SECRET = "your-secret-here"

    # 创建审批管理器
    manager = ApprovalManager(FEISHU_WEBHOOK_URL, FEISHU_SECRET)

    # 创建处理器
    web_handler = ApprovalWebHandler(manager)
    ws_handler = ApprovalWebSocketHandler(manager)

    # 设置路由
    app = web.Application()
    app.router.add_post("/api/approval/create", web_handler.handle_create_approval)
    app.router.add_get("/api/approval/{approval_id}", web_handler.handle_get_approval)
    app.router.add_get("/api/approval/pending", web_handler.handle_list_pending)
    app.router.add_post("/webhook/feishu", web_handler.handle_feishu_webhook)
    app.router.add_get("/ws/approval", ws_handler.handle)

    # 启动服务器
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8000)

    print("🚀 审批服务器已启动: http://localhost:8000")
    print("📡 WebSocket 端点: ws://localhost:8000/ws/approval")

    await site.start()

    # 保持运行
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
