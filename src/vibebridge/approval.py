"""审批系统 - 将审批请求发送到飞书并处理审批结果"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .im.base import BaseIMAdapter


class ApprovalStatus(Enum):
    """审批状态"""
    PENDING = "pending"  # 等待审批
    APPROVED = "approved"  # 已批准
    REJECTED = "rejected"  # 已拒绝
    EXPIRED = "expired"  # 已过期


class ApprovalAction(Enum):
    """审批动作"""
    ALLOW_ONCE = "allow-once"  # 允许一次
    ALLOW_ALWAYS = "allow-always"  # 永久允许
    DENY = "deny"  # 拒绝


@dataclass
class ApprovalRequest:
    """审批请求"""
    request_id: str
    task_id: str
    provider: str
    prompt: str
    risk_level: str
    chat_id: str
    sender_id: str
    created_at: float = field(default_factory=time.time)
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: Optional[str] = None
    approved_at: Optional[float] = None
    action: Optional[ApprovalAction] = None
    message_id: Optional[str] = None  # 飞书消息ID


class ApprovalManager:
    """审批管理器"""
    
    def __init__(self, im_adapter: BaseIMAdapter, approval_chat_id: Optional[str] = None):
        self.im = im_adapter
        self.approval_chat_id = approval_chat_id or self._get_default_approval_chat_id()
        self.requests: Dict[str, ApprovalRequest] = {}
        self._lock = asyncio.Lock()
        self._data_file = Path.home() / ".local" / "share" / "vibebridge" / "approvals.json"
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 加载历史数据
        self._load_requests()
    
    def _get_default_approval_chat_id(self) -> str:
        """获取默认审批群聊ID"""
        # 可以从环境变量或配置中获取
        import os
        return os.getenv("FEISHU_APPROVAL_CHAT_ID", "")
    
    async def create_approval_request(
        self,
        task_id: str,
        provider: str,
        prompt: str,
        risk_level: str,
        chat_id: str,
        sender_id: str,
    ) -> Tuple[str, bool]:
        """创建审批请求并发送到飞书
        
        Returns:
            Tuple[request_id, success]
        """
        request_id = str(uuid.uuid4())[:8]
        
        request = ApprovalRequest(
            request_id=request_id,
            task_id=task_id,
            provider=provider,
            prompt=prompt,
            risk_level=risk_level,
            chat_id=chat_id,
            sender_id=sender_id,
        )
        
        async with self._lock:
            self.requests[request_id] = request
        
        # 发送审批请求到飞书
        success = await self._send_approval_card(request)
        
        if success:
            self._save_requests()
        
        return request_id, success
    
    async def _send_approval_card(self, request: ApprovalRequest) -> bool:
        """发送审批卡片到飞书"""
        if not self.approval_chat_id:
            print(f"[Approval] 未配置审批群聊ID，无法发送审批请求")
            return False
        
        card = self._build_approval_card(request)
        
        try:
            # 发送卡片并获取消息ID
            result = await self.im.send_card(self.approval_chat_id, "interactive", card)
            if result:
                request.message_id = f"msg_{id(card)}"  # 简化处理，实际应该从飞书API获取消息ID
                return True
            return False
        except Exception as e:
            print(f"[Approval] 发送审批卡片失败: {e}")
            return False
    
    def _build_approval_card(self, request: ApprovalRequest) -> dict:
        """构建审批卡片"""
        # 格式化时间
        created_time = datetime.fromtimestamp(request.created_at).strftime("%Y-%m-%d %H:%M:%S")
        
        # 截取提示文本
        prompt_preview = request.prompt[:200] + ("..." if len(request.prompt) > 200 else "")
        
        card = {
            "config": {
                "wide_screen_mode": True,
                "enable_forward": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🔐 审批请求 - {request.risk_level.upper()} 风险"
                },
                "template": "red" if request.risk_level == "critical" else "orange"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**请求ID:** `{request.request_id}`\n"
                                  f"**任务ID:** `{request.task_id}`\n"
                                  f"**提供者:** `{request.provider}`\n"
                                  f"**风险等级:** `{request.risk_level}`\n"
                                  f"**请求时间:** {created_time}\n"
                                  f"**请求者:** `{request.sender_id}`\n"
                                  f"**来源群聊:** `{request.chat_id}`"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**命令内容:**\n```\n{prompt_preview}\n```"
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
                                "content": "✅ 允许一次"
                            },
                            "type": "primary",
                            "value": json.dumps({
                                "action": "approve",
                                "request_id": request.request_id,
                                "type": "allow-once"
                            })
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "✅ 永久允许"
                            },
                            "type": "primary",
                            "value": json.dumps({
                                "action": "approve",
                                "request_id": request.request_id,
                                "type": "allow-always"
                            })
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "❌ 拒绝"
                            },
                            "type": "danger",
                            "value": json.dumps({
                                "action": "reject",
                                "request_id": request.request_id,
                                "type": "deny"
                            })
                        }
                    ]
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": "请在飞书中点击按钮进行审批，或使用命令：\n"
                                      f"/approve {request.request_id} allow-once\n"
                                      f"/approve {request.request_id} allow-always\n"
                                      f"/approve {request.request_id} deny"
                        }
                    ]
                }
            ]
        }
        
        return card
    
    async def process_approval_action(
        self,
        request_id: str,
        action: ApprovalAction,
        approved_by: str,
    ) -> Tuple[bool, Optional[ApprovalRequest]]:
        """处理审批动作
        
        Returns:
            Tuple[success, updated_request]
        """
        async with self._lock:
            if request_id not in self.requests:
                return False, None
            
            request = self.requests[request_id]
            
            if request.status != ApprovalStatus.PENDING:
                return False, request
            
            # 更新状态
            request.status = ApprovalStatus.APPROVED if action != ApprovalAction.DENY else ApprovalStatus.REJECTED
            request.approved_by = approved_by
            request.approved_at = time.time()
            request.action = action
            
            # 保存更新
            self._save_requests()
            
            # 发送审批结果通知
            await self._send_approval_result(request)
            
            return True, request
    
    async def _send_approval_result(self, request: ApprovalRequest) -> bool:
        """发送审批结果通知到原始群聊"""
        if not request.chat_id:
            return False
        
        action_text = {
            ApprovalAction.ALLOW_ONCE: "✅ 已批准（仅本次）",
            ApprovalAction.ALLOW_ALWAYS: "✅ 已批准（永久）",
            ApprovalAction.DENY: "❌ 已拒绝"
        }.get(request.action, "未知")
        
        approved_time = datetime.fromtimestamp(request.approved_at).strftime("%Y-%m-%d %H:%M:%S")
        
        message = (
            f"**审批结果通知**\n\n"
            f"**请求ID:** `{request.request_id}`\n"
            f"**任务ID:** `{request.task_id}`\n"
            f"**审批结果:** {action_text}\n"
            f"**审批人:** `{request.approved_by}`\n"
            f"**审批时间:** {approved_time}\n\n"
            f"命令已{'可以继续执行' if request.action != ApprovalAction.DENY else '被拒绝执行'}。"
        )
        
        try:
            return await self.im.send_text(request.chat_id, message)
        except Exception as e:
            print(f"[Approval] 发送审批结果通知失败: {e}")
            return False
    
    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """获取审批请求"""
        return self.requests.get(request_id)
    
    def get_pending_requests(self) -> List[ApprovalRequest]:
        """获取所有待审批的请求"""
        return [req for req in self.requests.values() if req.status == ApprovalStatus.PENDING]
    
    def _load_requests(self):
        """从文件加载审批请求"""
        if not self._data_file.exists():
            return
        
        try:
            with open(self._data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for req_data in data.get('requests', []):
                try:
                    request = ApprovalRequest(
                        request_id=req_data['request_id'],
                        task_id=req_data['task_id'],
                        provider=req_data['provider'],
                        prompt=req_data['prompt'],
                        risk_level=req_data['risk_level'],
                        chat_id=req_data['chat_id'],
                        sender_id=req_data['sender_id'],
                        created_at=req_data['created_at'],
                        status=ApprovalStatus(req_data['status']),
                        approved_by=req_data.get('approved_by'),
                        approved_at=req_data.get('approved_at'),
                        action=ApprovalAction(req_data['action']) if req_data.get('action') else None,
                        message_id=req_data.get('message_id'),
                    )
                    self.requests[request.request_id] = request
                except Exception as e:
                    print(f"[Approval] 加载审批请求失败: {e}")
        except Exception as e:
            print(f"[Approval] 加载审批数据失败: {e}")
    
    def _save_requests(self):
        """保存审批请求到文件"""
        try:
            data = {
                'requests': [],
                'updated_at': time.time()
            }
            
            for request in self.requests.values():
                req_data = {
                    'request_id': request.request_id,
                    'task_id': request.task_id,
                    'provider': request.provider,
                    'prompt': request.prompt,
                    'risk_level': request.risk_level,
                    'chat_id': request.chat_id,
                    'sender_id': request.sender_id,
                    'created_at': request.created_at,
                    'status': request.status.value,
                    'approved_by': request.approved_by,
                    'approved_at': request.approved_at,
                    'action': request.action.value if request.action else None,
                    'message_id': request.message_id,
                }
                data['requests'].append(req_data)
            
            with open(self._data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Approval] 保存审批数据失败: {e}")
    
    def cleanup_expired(self, expiry_hours: int = 24):
        """清理过期的审批请求"""
        expiry_time = time.time() - (expiry_hours * 3600)
        
        expired_ids = []
        for request_id, request in self.requests.items():
            if (request.status == ApprovalStatus.PENDING and 
                request.created_at < expiry_time):
                request.status = ApprovalStatus.EXPIRED
                expired_ids.append(request_id)
        
        if expired_ids:
            self._save_requests()
            print(f"[Approval] 清理了 {len(expired_ids)} 个过期的审批请求")
    
    async def handle_approval_command(self, text: str, sender_id: str, chat_id: str) -> str:
        """处理审批命令
        
        命令格式: /approve <request_id> <action>
        示例: /approve 73d95f6a allow-once
        """
        parts = text.strip().split()
        if len(parts) != 3:
            return "❌ 命令格式错误。正确格式: /approve <请求ID> <动作>\n动作: allow-once, allow-always, deny"
        
        _, request_id, action_str = parts
        
        try:
            action = ApprovalAction(action_str)
        except ValueError:
            return f"❌ 无效的动作: {action_str}\n可用动作: allow-once, allow-always, deny"
        
        success, request = await self.process_approval_action(request_id, action, sender_id)
        
        if not success:
            if request:
                return f"❌ 请求 `{request_id}` 当前状态为 `{request.status.value}`，无法审批"
            else:
                return f"❌ 未找到请求ID: `{request_id}`"
        
        action_text = {
            ApprovalAction.ALLOW_ONCE: "✅ 已批准（仅本次）",
            ApprovalAction.ALLOW_ALWAYS: "✅ 已批准（永久）",
            ApprovalAction.DENY: "❌ 已拒绝"
        }.get(action, "未知")
        
        return f"{action_text} 请求 `{request_id}`"