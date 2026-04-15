"""Feishu IM Adapter."""

from __future__ import annotations

import json
import re

from .base import BaseIMAdapter, InboundMessage


class FeishuAdapter(BaseIMAdapter):
    name = "feishu"

    def __init__(self, config):
        from ..config import FeishuConfig

        assert isinstance(config, FeishuConfig)
        self.config = config

        # Reuse legacy FeishuClient but override credentials
        from src.legacy.feishu_client import FeishuClient

        self._client = FeishuClient()
        self._client.app_id = config.app_id
        self._client.app_secret = config.app_secret
        self._client.default_chat_id = ""

    async def parse_incoming(self, raw_payload: dict) -> InboundMessage:
        from src.legacy.feishu_crypto import (
            FeishuSecurityError,
            decrypt_feishu_payload,
            verify_feishu_webhook,
        )

        # Verify signature
        try:
            verify_feishu_webhook(raw_payload)
        except FeishuSecurityError as e:
            raise ValueError(f"Webhook verification failed: {e}") from e

        # Decrypt if needed
        body = decrypt_feishu_payload(raw_payload)

        # Parse schema v2 / v1
        schema = body.get("schema", "")
        event = {}
        event_type = ""

        if schema == "2.0":
            header = body.get("header", {})
            event_type = header.get("event_type", "")
            event = body.get("event", {})
        else:
            event = body.get("event", {})
            event_type = body.get("event_type", "")

        if event_type != "im.message.receive_v1":
            raise ValueError(f"Unhandled event type: {event_type}")

        message = event.get("message", {})
        sender = event.get("sender", {})
        content_str = message.get("content", "{}")

        # Deduplication
        message_id = message.get("message_id", "")
        if message_id:
            from src.legacy.message_deduplicator import get_deduplicator

            dedup = get_deduplicator()
            if dedup.is_duplicate(message_id):
                raise ValueError("Duplicate message")

        try:
            content_obj = json.loads(content_str)
        except json.JSONDecodeError:
            content_obj = {}

        text = content_obj.get("text", "").strip()

        # Clean @mentions
        text = re.sub(r"<at[^>]*>.*?</at>", "", text)
        text = re.sub(r"^\s*@[^\s]+\s*", "", text)
        text = text.strip()

        chat_type = message.get("chat_type", "")
        mentions = message.get("mentions", [])
        bot_mentioned = any(
            m.get("mentioned_type") == "bot" for m in mentions
        )

        return InboundMessage(
            message_id=message_id,
            chat_id=message.get("chat_id", ""),
            sender_id=sender.get("sender_id", {}).get("open_id", "unknown"),
            text=text,
            chat_type=chat_type,
            is_bot_mentioned=bot_mentioned,
            raw_payload=body,
        )

    async def send_text(self, chat_id: str, text: str) -> bool:
        result = await self._client.send_text_message(chat_id, text)
        return result is not None and "error" not in result

    async def send_card(self, chat_id: str, card_type: str, context: dict) -> bool:
        result = await self._client.send_interactive_card(chat_id, context)
        return result is not None and "error" not in result

    async def upload_file(self, chat_id: str, file_path: str) -> bool:
        result = await self._client.upload_file(chat_id, file_path)
        return result is not None and "error" not in result
