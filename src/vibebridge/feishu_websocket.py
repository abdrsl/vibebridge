"""Feishu WebSocket client."""
from __future__ import annotations

from typing import Any

# Re-export the canonical implementation from src/feishu_websocket.py
from feishu_websocket import OpenCodeEventProcessor


class ProgressCardForwarder:
    def __init__(self, bot_manager: Any = None) -> None:
        self._bot_manager = bot_manager
        self._progress_card_meta: dict[str, Any] = {}


class FeishuWebSocketClient:
    def __init__(self, app_id: str = "", app_secret: str = "", bot_manager: Any = None) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self._bot_manager = bot_manager
        self._cancel_event = False
        self._interrupt_active_task = False

    def _send_interrupt_message(self, chat_id: str) -> None:
        if self._bot_manager is not None:
            try:
                self._bot_manager.send_text(chat_id, "任务已中断")
            except Exception:
                pass
