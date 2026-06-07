"""Minimal vibebridge gateway — routes messages and manages task mappings.

Uses VibeBridge's own SessionManager and HistoryManager instead of external
conversation stores.
"""
from __future__ import annotations

import threading
import time
from typing import Any

from vibebridge.session import get_session_manager
from vibebridge.history import get_history_manager

# In-memory task mappings (sufficient for embedded vibebridge)
_task_mappings: dict[str, dict[str, Any]] = {}
_task_lock = threading.Lock()

# Gateway keywords (loaded lazily)
NOTICE_KEYWORDS: set[str] = set()
TASK_KEYWORDS: set[str] = set()


def _load_gateway_keywords() -> None:
    global NOTICE_KEYWORDS, TASK_KEYWORDS
    if NOTICE_KEYWORDS and TASK_KEYWORDS:
        return
    NOTICE_KEYWORDS = {
        "收到", "明白", "好的", "ok", "了解了", "知道了",
        "谢谢", "感谢", "received", "ack", "roger",
    }
    TASK_KEYWORDS = {
        "请", "帮我", "需要", "实现", "修复", "优化",
        "添加", "删除", "更新", "创建", "生成", "写",
        "deploy", "fix", "implement", "create", "add",
    }


def is_actual_task(text: str) -> bool:
    """Return True if text looks like a task request (not just ack/nice)."""
    _load_gateway_keywords()
    text_lower = text.lower()
    if any(kw in text_lower for kw in NOTICE_KEYWORDS):
        return False
    return any(kw in text_lower for kw in TASK_KEYWORDS)


def route_feishu_p2p(
    agent_name: str,
    message: str,
    chat_id: str,
    user_id: str,
    task_id: str,
) -> dict[str, Any]:
    """Route a Feishu P2P message to the agent's main session."""
    session_mgr = get_session_manager()
    history_mgr = get_history_manager()

    session = session_mgr.get_or_create(
        user_id=user_id,
        chat_id=chat_id,
        provider=agent_name,
    )
    session.add_message(role="user", content=message)
    session_mgr.save(session)

    history_mgr.add_message(
        session_id=session.session_id,
        user_id=user_id,
        chat_id=chat_id,
        role="user",
        content=message,
        metadata={"source": "feishu_p2p", "user_id": user_id},
        provider=agent_name,
    )

    register_task_mapping(
        task_id, session.session_id, chat_id, "feishu_p2p", agent_name, source="feishu_p2p"
    )
    return {"session_id": session.session_id, "task_id": task_id}


def route_feishu_group(
    agent_name: str,
    message: str,
    chat_id: str,
    user_id: str,
    task_id: str,
    is_actual: bool,
) -> dict[str, Any]:
    """Route a Feishu group message."""
    session_mgr = get_session_manager()
    history_mgr = get_history_manager()

    session = session_mgr.get_or_create(
        user_id=user_id,
        chat_id=chat_id,
        provider=agent_name,
    )
    if is_actual:
        session.add_message(role="user", content=message)
        session_mgr.save(session)

        history_mgr.add_message(
            session_id=session.session_id,
            user_id=user_id,
            chat_id=chat_id,
            role="user",
            content=message,
            metadata={"source": "feishu_group", "user_id": user_id},
            provider=agent_name,
        )

    register_task_mapping(
        task_id, session.session_id, chat_id, "feishu_group", agent_name, source="feishu_group"
    )
    return {"session_id": session.session_id, "task_id": task_id}


def route_webui(
    agent_name: str,
    message: str,
    session_id: str | None = None,
    model: str | None = None,
    chat_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Route a WebUI message."""
    session_mgr = get_session_manager()
    history_mgr = get_history_manager()

    if session_id:
        session = session_mgr.get(session_id)
        if session is None:
            session = session_mgr.get_or_create(
                user_id=user_id or "webui",
                chat_id=chat_id or "webui",
                provider=agent_name,
            )
    else:
        session = session_mgr.get_or_create(
            user_id=user_id or "webui",
            chat_id=chat_id or "webui",
            provider=agent_name,
        )

    session.add_message(role="user", content=message)
    session_mgr.save(session)

    history_mgr.add_message(
        session_id=session.session_id,
        user_id=session.user_id,
        chat_id=session.chat_id,
        role="user",
        content=message,
        metadata={"source": "webui", "user_id": user_id},
        provider=agent_name,
    )

    return {"task": {"session_id": session.session_id, "agent": agent_name, "model": model}}


def register_task_mapping(
    task_id: str,
    session_id: str,
    chat_id: str,
    channel: str,
    agent_name: str,
    source: str | None = None,
) -> None:
    with _task_lock:
        _task_mappings[task_id] = {
            "task_id": task_id,
            "session_id": session_id,
            "chat_id": chat_id,
            "channel": channel,
            "agent_name": agent_name,
            "source": source,
            "created_at": time.time(),
        }


def _get_task_mapping(task_id: str) -> dict[str, Any] | None:
    with _task_lock:
        return _task_mappings.get(task_id)


def pop_task_mapping(task_id: str) -> dict[str, Any] | None:
    with _task_lock:
        return _task_mappings.pop(task_id, None)


def get_session_by_chat_id(chat_id: str) -> dict[str, Any] | None:
    """Get session info by chat_id (stub)."""
    return None


def get_webui_base_url() -> str:
    import os

    host = os.environ.get("VIBEBRIDGE_DASHBOARD_HOST", "127.0.0.1")
    port = os.environ.get("VIBEBRIDGE_DASHBOARD_PORT", "8000")
    return f"http://{host}:{port}"


class Gateway:
    """Unified message gateway."""

    def route_feishu_p2p(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return route_feishu_p2p(*args, **kwargs)

    def route_feishu_group(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return route_feishu_group(*args, **kwargs)

    def register_task_mapping(self, task_id: str, session_id: str, source: str | None = None) -> None:
        register_task_mapping(task_id, session_id, "", "webui", "", source=source)

    def get_task_mapping(self, task_id: str) -> dict[str, Any] | None:
        return _get_task_mapping(task_id)
