"""
Session管理器 - 管理飞书对话的session状态
"""

import json
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
import asyncio


class SessionStatus(str, Enum):
    """Session状态"""

    PENDING = "pending"  # 等待用户确认
    CONFIRMED = "confirmed"  # 用户已确认，准备执行
    RUNNING = "running"  # 任务执行中
    COMPLETED = "completed"  # 任务完成
    FAILED = "failed"  # 任务失败
    CANCELLED = "cancelled"  # 用户取消
    EXPIRED = "expired"  # Session过期


@dataclass
class SessionMessage:
    """Session中的消息"""

    role: str  # user, assistant, system
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeishuSession:
    """飞书对话Session"""

    session_id: str
    chat_id: str
    user_id: str
    status: SessionStatus = SessionStatus.PENDING
    current_task_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 3600)  # 1小时过期
    messages: List[SessionMessage] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str, **metadata) -> None:
        """添加消息到session"""
        self.messages.append(
            SessionMessage(role=role, content=content, metadata=metadata)
        )
        self.updated_at = time.time()

    def get_conversation_history(self, max_messages: int = 10) -> List[Dict[str, Any]]:
        """获取对话历史"""
        recent_messages = self.messages[-max_messages:] if self.messages else []
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp,
                "metadata": msg.metadata,
            }
            for msg in recent_messages
        ]

    def is_expired(self) -> bool:
        """检查session是否过期"""
        return time.time() > self.expires_at

    def renew(self, duration: int = 3600) -> None:
        """续期session"""
        self.expires_at = time.time() + duration
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "chat_id": self.chat_id,
            "user_id": self.user_id,
            "status": self.status.value,
            "current_task_id": self.current_task_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "message_count": len(self.messages),
            "metadata": self.metadata,
        }


class SessionManager:
    """Session管理器"""

    def __init__(self, storage_path: Optional[Path] = None):
        self.sessions: Dict[str, FeishuSession] = {}
        self.storage_path = storage_path or Path("data/sessions")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._load_sessions()

    def _load_sessions(self) -> None:
        """从存储加载sessions"""
        try:
            for session_file in self.storage_path.glob("*.json"):
                try:
                    with open(session_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # 检查是否过期
                    if time.time() > data.get("expires_at", 0):
                        session_file.unlink()
                        continue

                    session = FeishuSession(
                        session_id=data["session_id"],
                        chat_id=data["chat_id"],
                        user_id=data["user_id"],
                        status=SessionStatus(data["status"]),
                        current_task_id=data.get("current_task_id"),
                        created_at=data["created_at"],
                        updated_at=data["updated_at"],
                        expires_at=data["expires_at"],
                        metadata=data.get("metadata", {}),
                    )

                    # 加载消息（如果有）
                    messages_data = data.get("messages", [])
                    for msg_data in messages_data:
                        session.messages.append(
                            SessionMessage(
                                role=msg_data["role"],
                                content=msg_data["content"],
                                timestamp=msg_data.get("timestamp", time.time()),
                                metadata=msg_data.get("metadata", {}),
                            )
                        )

                    self.sessions[session.session_id] = session

                except Exception as e:
                    print(f"Error loading session {session_file}: {e}")
                    continue

            print(f"Loaded {len(self.sessions)} sessions from storage")

        except Exception as e:
            print(f"Error loading sessions: {e}")

    def _save_session(self, session: FeishuSession) -> None:
        """保存session到存储"""
        try:
            session_file = self.storage_path / f"{session.session_id}.json"
            data = session.to_dict()

            # 添加消息数据
            data["messages"] = [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp,
                    "metadata": msg.metadata,
                }
                for msg in session.messages
            ]

            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"Error saving session {session.session_id}: {e}")

    async def get_or_create_session(
        self, chat_id: str, user_id: str, create_if_not_exists: bool = True
    ) -> Optional[FeishuSession]:
        """
        获取或创建session

        Args:
            chat_id: 飞书群聊ID
            user_id: 用户ID
            create_if_not_exists: 如果不存在是否创建

        Returns:
            Session对象或None
        """
        async with self._lock:
            # 首先查找活跃的session
            for session in self.sessions.values():
                if (
                    session.chat_id == chat_id
                    and session.user_id == user_id
                    and not session.is_expired()
                    and session.status not in [SessionStatus.CANCELLED]
                ):
                    session.renew()
                    self._save_session(session)
                    return session

            # 如果没有找到活跃session且允许创建
            if create_if_not_exists:
                session_id = f"fs_{int(time.time())}_{uuid.uuid4().hex[:8]}"
                session = FeishuSession(
                    session_id=session_id,
                    chat_id=chat_id,
                    user_id=user_id,
                    status=SessionStatus.PENDING,
                )

                self.sessions[session_id] = session
                self._save_session(session)
                return session

            return None

    async def get_session(self, session_id: str) -> Optional[FeishuSession]:
        """根据session_id获取session"""
        async with self._lock:
            session = self.sessions.get(session_id)
            if session and session.is_expired():
                # 清理过期session
                await self.close_session(session_id, SessionStatus.EXPIRED)
                return None
            return session

    async def update_session(
        self,
        session_id: str,
        status: Optional[SessionStatus] = None,
        task_id: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """更新session"""
        async with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return False

            if status:
                session.status = status

            if task_id:
                session.current_task_id = task_id

            # 更新其他字段
            for key, value in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, value)

            session.updated_at = time.time()
            session.renew()
            self._save_session(session)
            return True

    async def add_message_to_session(
        self, session_id: str, role: str, content: str, **metadata
    ) -> bool:
        """添加消息到session"""
        async with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return False

            session.add_message(role, content, **metadata)
            self._save_session(session)
            return True

    async def close_session(
        self, session_id: str, status: SessionStatus = SessionStatus.COMPLETED
    ) -> bool:
        """关闭session"""
        async with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return False

            session.status = status
            session.updated_at = time.time()

            # 从内存中移除，但保留在存储中
            del self.sessions[session_id]

            # 更新存储中的状态
            self._save_session(session)
            return True

    async def cleanup_expired_sessions(self) -> int:
        """清理过期session"""
        async with self._lock:
            expired_ids = []
            for session_id, session in self.sessions.items():
                if session.is_expired():
                    expired_ids.append(session_id)

            for session_id in expired_ids:
                session = self.sessions[session_id]
                session.status = SessionStatus.EXPIRED
                self._save_session(session)
                del self.sessions[session_id]

            # 清理存储中的过期文件
            for session_file in self.storage_path.glob("*.json"):
                try:
                    with open(session_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    if time.time() > data.get("expires_at", 0):
                        session_file.unlink()

                except Exception:
                    continue

            return len(expired_ids)

    async def list_sessions(
        self,
        chat_id: Optional[str] = None,
        user_id: Optional[str] = None,
        status: Optional[SessionStatus] = None,
    ) -> List[Dict[str, Any]]:
        """列出sessions"""
        async with self._lock:
            sessions = []
            for session in self.sessions.values():
                # 过滤条件
                if chat_id and session.chat_id != chat_id:
                    continue
                if user_id and session.user_id != user_id:
                    continue
                if status and session.status != status:
                    continue

                sessions.append(session.to_dict())

            return sessions


# 全局实例
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """获取session管理器实例"""
    global _session_manager

    if _session_manager is None:
        _session_manager = SessionManager()

    return _session_manager


if __name__ == "__main__":
    # 测试session管理器
    import asyncio

    async def test():
        manager = get_session_manager()

        print("Session Manager Test")
        print("=" * 60)

        # 创建session
        session = await manager.get_or_create_session(
            chat_id="test_chat_123", user_id="test_user_456"
        )

        print(f"Created session: {session.session_id}")
        print(f"Status: {session.status}")

        # 添加消息
        await manager.add_message_to_session(
            session.session_id, "user", "请帮我创建一个HTML页面"
        )

        await manager.add_message_to_session(
            session.session_id,
            "assistant",
            "好的，我会帮你创建一个漂亮的HTML页面。请确认是否开始执行？",
        )

        # 更新状态
        await manager.update_session(
            session.session_id, status=SessionStatus.CONFIRMED, task_id="task_123"
        )

        # 获取session
        retrieved = await manager.get_session(session.session_id)
        print(f"\nRetrieved session: {retrieved.session_id if retrieved else 'None'}")
        print(f"Message count: {len(retrieved.messages) if retrieved else 0}")

        # 列出sessions
        sessions = await manager.list_sessions(chat_id="test_chat_123")
        print(f"\nSessions for chat: {len(sessions)}")

        # 清理
        cleaned = await manager.cleanup_expired_sessions()
        print(f"Cleaned expired sessions: {cleaned}")

        print("\n" + "=" * 60)
        print("Test completed")

    asyncio.run(test())
