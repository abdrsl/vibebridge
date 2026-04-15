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
        except Exception as e:
            raise ValueError(f"Webhook verification error: {e}") from e

        # Decrypt if needed
        try:
            body = decrypt_feishu_payload(raw_payload)
        except Exception as e:
            raise ValueError(f"Payload decryption failed: {e}") from e

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

        message = event.get("message", {}) if isinstance(event.get("message"), dict) else {}
        sender = event.get("sender", {}) if isinstance(event.get("sender"), dict) else {}
        content_str = message.get("content", "{}") if isinstance(message.get("content"), str) else "{}"

        # Deduplication (swallow deduplicator errors so one bad message doesn't crash the service)
        message_id = message.get("message_id", "")
        if message_id:
            try:
                from src.legacy.message_deduplicator import get_deduplicator

                dedup = get_deduplicator()
                if dedup.is_duplicate(message_id):
                    raise ValueError("Duplicate message")
            except ValueError:
                raise
            except Exception as e:
                print(f"[FeishuAdapter] Deduplicator error (proceeding anyway): {e}")

        try:
            content_obj = json.loads(content_str)
        except json.JSONDecodeError:
            content_obj = {}

        text = content_obj.get("text", "").strip() if isinstance(content_obj, dict) else ""

        # Clean @mentions
        text = re.sub(r"<at[^>]*>.*?</at>", "", text)
        text = re.sub(r"^\s*@[^\s]+\s*", "", text)
        text = text.strip()

        chat_type = message.get("chat_type", "")
        mentions = message.get("mentions", [])
        if not isinstance(mentions, list):
            mentions = []
        bot_mentioned = any(
            m.get("mentioned_type") == "bot" for m in mentions
        )

        sender_id = "unknown"
        try:
            sender_id = sender.get("sender_id", {}).get("open_id", "unknown")
        except Exception:
            pass

        chat_id = ""
        try:
            chat_id = message.get("chat_id", "")
        except Exception:
            pass

        return InboundMessage(
            message_id=message_id,
            chat_id=chat_id,
            sender_id=sender_id,
            text=text,
            chat_type=chat_type,
            is_bot_mentioned=bot_mentioned,
            raw_payload=body,
        )

    async def send_text(self, chat_id: str, text: str) -> bool:
        return await self._send_with_retry(
            self._client.send_text_message, chat_id, text
        )

    async def send_card(self, chat_id: str, card_type: str, context: dict) -> bool:
        return await self._send_with_retry(
            self._client.send_interactive_card, chat_id, context
        )

    async def upload_file(self, chat_id: str, file_path: str) -> bool:
        return await self._send_with_retry(
            self._client.upload_file, chat_id, file_path
        )

    async def _send_with_retry(self, sender, chat_id: str, payload, max_retries: int = 2) -> bool:
        """Send with token-clear retry on auth failures."""
        last_error = None
        for attempt in range(max_retries):
            try:
                result = await sender(chat_id, payload)
                if result is not None and "error" not in result:
                    return True
                # If result indicates token failure, clear cache and retry
                if isinstance(result, dict) and result.get("code") in (99991663, 99991664, 99991665, 10003):
                    self._client.clear_token_cache()
                    last_error = f"Token error {result.get('code')}"
                    continue
                last_error = result
            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                if "token" in err_str or "auth" in err_str or "unauthorized" in err_str:
                    self._client.clear_token_cache()
        print(f"[FeishuAdapter] send failed after {max_retries} attempts: {last_error}")
        return False
