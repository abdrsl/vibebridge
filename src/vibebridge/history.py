"""历史上下文管理器，用于存储和检索会话历史记录。"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .config import get_config


class HistoryEntry(BaseModel):
    """历史记录条目"""
    role: str  # user, assistant, system
    content: str
    timestamp: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationHistory(BaseModel):
    """会话历史"""
    session_id: str
    user_id: str
    chat_id: str
    provider: str = "opencode"
    entries: List[HistoryEntry] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    max_history_size: int = 50  # 最大历史记录条数

    def add_entry(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """添加历史记录条目"""
        entry = HistoryEntry(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.entries.append(entry)
        
        # 限制历史记录大小
        if len(self.entries) > self.max_history_size:
            self.entries = self.entries[-self.max_history_size:]
        
        self.updated_at = time.time()

    def get_recent_entries(self, limit: int = 10) -> List[HistoryEntry]:
        """获取最近的历史记录条目"""
        return self.entries[-limit:] if self.entries else []

    def get_entries_by_role(self, role: str, limit: int = 10) -> List[HistoryEntry]:
        """按角色获取历史记录条目"""
        filtered = [entry for entry in self.entries if entry.role == role]
        return filtered[-limit:] if filtered else []

    def get_context_summary(self, max_tokens: int = 2000) -> str:
        """获取上下文摘要，用于合并到LLM提示中"""
        if not self.entries:
            return ""
        
        # 从最近的记录开始构建上下文
        context_parts = []
        total_length = 0
        
        for entry in reversed(self.entries):
            entry_text = f"{entry.role}: {entry.content}"
            entry_length = len(entry_text)
            
            if total_length + entry_length > max_tokens:
                break
                
            context_parts.insert(0, entry_text)  # 插入到开头以保持时间顺序
            total_length += entry_length
        
        return "\n".join(context_parts)

    def clear(self) -> None:
        """清空历史记录"""
        self.entries.clear()
        self.updated_at = time.time()


class HistoryManager:
    """历史管理器"""
    
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or get_config().data_dir / "history"
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"[HistoryManager] Warning: failed to create data_dir {self.data_dir}: {e}")
        self._cache: Dict[str, ConversationHistory] = {}

    def _get_history_path(self, session_id: str) -> Path:
        """获取历史文件路径"""
        return self.data_dir / f"{session_id}.json"

    def get_or_create_history(
        self,
        session_id: str,
        user_id: str,
        chat_id: str,
        provider: str = "opencode"
    ) -> ConversationHistory:
        """获取或创建会话历史"""
        if session_id in self._cache:
            return self._cache[session_id]

        path = self._get_history_path(session_id)
        history: Optional[ConversationHistory] = None
        
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                history = ConversationHistory(**data)
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                print(f"[HistoryManager] Corrupted history file {path}: {e}. Recreating.")
                try:
                    backup = path.with_suffix(".json.bak")
                    path.rename(backup)
                except Exception:
                    pass

        if history is None:
            history = ConversationHistory(
                session_id=session_id,
                user_id=user_id,
                chat_id=chat_id,
                provider=provider
            )
            self.save_history(history)

        self._cache[session_id] = history
        return history

    def save_history(self, history: ConversationHistory) -> None:
        """保存会话历史"""
        history.updated_at = time.time()
        path = self._get_history_path(history.session_id)
        
        try:
            # 确保父目录存在
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # 原子写入：临时文件 + 重命名
            import tempfile
            import os
            
            fd, tmp_path = tempfile.mkstemp(
                dir=str(path.parent),
                prefix=f".{path.name}.tmp_"
            )
            
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(history.model_dump(), f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, path)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                raise
        except Exception as e:
            print(f"[HistoryManager] Failed to save history {history.session_id}: {e}")

    def add_message(
        self,
        session_id: str,
        user_id: str,
        chat_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        provider: str = "opencode"
    ) -> None:
        """添加消息到历史记录"""
        history = self.get_or_create_history(session_id, user_id, chat_id, provider)
        history.add_entry(role, content, metadata)
        self.save_history(history)

    def get_context(
        self,
        session_id: str,
        max_entries: int = 10,
        max_tokens: int = 2000
    ) -> str:
        """获取会话上下文"""
        if session_id not in self._cache:
            return ""
        
        history = self._cache[session_id]
        return history.get_context_summary(max_tokens)

    def clear_history(self, session_id: str) -> bool:
        """清空会话历史"""
        if session_id in self._cache:
            del self._cache[session_id]
        
        path = self._get_history_path(session_id)
        if path.exists():
            try:
                path.unlink()
                return True
            except Exception as e:
                print(f"[HistoryManager] Failed to delete history {session_id}: {e}")
        
        return False

    def search_history(
        self,
        session_id: str,
        query: str,
        limit: int = 5
    ) -> List[HistoryEntry]:
        """在会话历史中搜索相关内容"""
        if session_id not in self._cache:
            return []
        
        history = self._cache[session_id]
        query_lower = query.lower()
        results = []
        
        for entry in reversed(history.entries):
            if query_lower in entry.content.lower():
                results.append(entry)
                if len(results) >= limit:
                    break
        
        return results


# 全局缓存实例
_history_manager: Optional[HistoryManager] = None


def get_history_manager() -> HistoryManager:
    """获取历史管理器实例"""
    global _history_manager
    if _history_manager is None:
        _history_manager = HistoryManager()
    return _history_manager