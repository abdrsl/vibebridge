"""Base protocol for IM adapters."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class InboundMessage(BaseModel):
    message_id: str
    chat_id: str
    sender_id: str
    text: str
    chat_type: str  # "group" | "p2p"
    is_bot_mentioned: bool
    raw_payload: dict


class BaseIMAdapter(Protocol):
    name: str

    async def parse_incoming(self, raw_payload: dict) -> InboundMessage:
        """Parse raw webhook/websocket payload into unified message."""
        ...

    async def send_text(self, chat_id: str, text: str) -> bool:
        """Send plain text message."""
        ...

    async def send_card(self, chat_id: str, card_type: str, context: dict) -> bool:
        """Send an interactive card message."""
        ...

    async def upload_file(self, chat_id: str, file_path: str) -> bool:
        """Upload and send a file."""
        ...
