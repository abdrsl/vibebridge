"""
消息去重器
防止重复处理相同的消息
"""

import time
from typing import Set, Dict
from collections import deque


class MessageDeduplicator:
    """消息去重器"""

    def __init__(self, max_size: int = 1000, expiry_seconds: int = 3600):
        """
        初始化去重器

        Args:
            max_size: 最大存储消息数
            expiry_seconds: 消息过期时间（秒）
        """
        self.max_size = max_size
        self.expiry_seconds = expiry_seconds
        # 存储 (message_id, timestamp)
        self.messages: deque = deque(maxlen=max_size)
        self.message_ids: Set[str] = set()

    def is_duplicate(self, message_id: str) -> bool:
        """
        检查消息是否重复

        Args:
            message_id: 消息ID

        Returns:
            True如果是重复消息，False如果不是
        """
        self._cleanup_expired()

        if message_id in self.message_ids:
            return True

        # 添加到记录
        self.messages.append((message_id, time.time()))
        self.message_ids.add(message_id)
        return False

    def _cleanup_expired(self):
        """清理过期消息"""
        current_time = time.time()

        while self.messages:
            msg_id, timestamp = self.messages[0]
            if current_time - timestamp > self.expiry_seconds:
                self.messages.popleft()
                self.message_ids.discard(msg_id)
            else:
                break

    def get_stats(self) -> Dict:
        """获取统计信息"""
        self._cleanup_expired()
        return {
            "total_messages": len(self.messages),
            "unique_messages": len(self.message_ids),
        }


# 全局实例
_deduplicator = None


def get_deduplicator() -> MessageDeduplicator:
    """获取去重器实例"""
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = MessageDeduplicator()
    return _deduplicator
