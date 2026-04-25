"""Feishu IM Adapter — Multi-bot architecture.

Each MyCompany agent can have its own Feishu bot with independent
App ID + Secret. Messages are routed by ``header.app_id`` and
replies are sent via the correct bot's credentials.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from .base import BaseIMAdapter, InboundMessage

logger = logging.getLogger(__name__)


@dataclass
class FeishuBotCredentials:
    """Credentials for a single Feishu bot."""

    agent: str           # e.g. "software-agent"
    app_id: str
    app_secret: str
    encrypt_key: str = ""
    verification_token: str = ""


class FeishuBot:
    """Wrapper around legacy FeishuClient for one bot."""

    def __init__(self, creds: FeishuBotCredentials) -> None:
        self.creds = creds
        try:
            from src.legacy.feishu_client import FeishuClient
        except ModuleNotFoundError:
            from legacy.feishu_client import FeishuClient

        self._client = FeishuClient()
        self._client.app_id = creds.app_id
        self._client.app_secret = creds.app_secret
        self._client.default_chat_id = ""

    async def send_text(self, chat_id: str, text: str) -> bool:
        return await self._send_with_retry(self._client.send_text_message, chat_id, text)

    async def send_card(self, chat_id: str, card_type: str, context: dict) -> bool:
        return await self._send_with_retry(self._client.send_interactive_card, chat_id, context)

    async def upload_file(self, chat_id: str, file_path: str) -> bool:
        return await self._send_with_retry(self._client.upload_file, chat_id, file_path)

    async def _send_with_retry(self, sender, chat_id: str, payload, max_retries: int = 2) -> bool:
        last_error = None
        for attempt in range(max_retries):
            try:
                result = await sender(chat_id, payload)
                if result is not None and "error" not in result:
                    return True
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
        logger.warning("[FeishuBot:%s] send failed after %d attempts: %s", self.creds.agent, max_retries, last_error)
        return False


class FeishuMultiBotManager(BaseIMAdapter):
    """Manages multiple Feishu bots and routes messages/replies.

    Usage::

        manager = FeishuMultiBotManager([creds1, creds2, ...])
        msg = await manager.parse_incoming(payload)   # auto-detects bot from app_id
        await manager.send_text(msg.chat_id, "reply", bot_id=msg.bot_id)
    """

    name = "feishu"

    def __init__(self, bots: list[FeishuBotCredentials]) -> None:
        self._bots_by_app_id: dict[str, FeishuBot] = {}
        self._bots_by_agent: dict[str, FeishuBot] = {}
        for creds in bots:
            if not creds.app_id or not creds.app_secret:
                logger.warning("Skipping bot %s: missing app_id or app_secret", creds.agent)
                continue
            bot = FeishuBot(creds)
            self._bots_by_app_id[creds.app_id] = bot
            self._bots_by_agent[creds.agent] = bot
            logger.info("[FeishuMultiBot] Registered bot for %s (app_id=%s...)", creds.agent, creds.app_id[:8])

        if not self._bots_by_app_id:
            logger.warning("[FeishuMultiBot] No bots configured — Feishu integration disabled")

    # ------------------------------------------------------------------ #
    #  Lookup helpers
    # ------------------------------------------------------------------ #

    def _detect_app_id(self, raw_payload: dict) -> str:
        """Extract app_id from Feishu event header."""
        schema = raw_payload.get("schema", "")
        if schema == "2.0":
            return raw_payload.get("header", {}).get("app_id", "")
        # Legacy v1 schema may have app_id in event or top-level
        return raw_payload.get("app_id", "")

    def get_bot(self, app_id: str = "", agent: str = "") -> FeishuBot | None:
        """Get bot by app_id (preferred) or agent name."""
        if app_id:
            return self._bots_by_app_id.get(app_id)
        if agent:
            return self._bots_by_agent.get(agent)
        return None

    def get_default_bot(self) -> FeishuBot | None:
        """Return the first registered bot (fallback)."""
        return next(iter(self._bots_by_app_id.values()), None)

    def list_bots(self) -> list[dict[str, Any]]:
        """Return metadata for all registered bots."""
        return [
            {"agent": b.creds.agent, "app_id": b.creds.app_id, "app_id_prefix": b.creds.app_id[:8] + "..."}
            for b in self._bots_by_app_id.values()
        ]

    # ------------------------------------------------------------------ #
    #  Incoming message parsing
    # ------------------------------------------------------------------ #

    async def parse_incoming(self, raw_payload: dict) -> InboundMessage:
        app_id = self._detect_app_id(raw_payload)
        bot = self.get_bot(app_id=app_id) or self.get_default_bot()

        if bot is None:
            raise ValueError("No Feishu bot configured — cannot process webhook")

        # Crypto imports (same as before)
        try:
            from src.legacy.feishu_crypto import (
                FeishuSecurityError,
                decrypt_feishu_payload,
                verify_feishu_webhook,
            )
        except ModuleNotFoundError:
            from legacy.feishu_crypto import (
                FeishuSecurityError,
                decrypt_feishu_payload,
                verify_feishu_webhook,
            )

        # Verify signature using this bot's verification token
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

        # Deduplication
        message_id = message.get("message_id", "")
        if message_id:
            try:
                try:
                    from src.legacy.message_deduplicator import get_deduplicator
                except ModuleNotFoundError:
                    from legacy.message_deduplicator import get_deduplicator

                dedup = get_deduplicator()
                if dedup.is_duplicate(message_id):
                    raise ValueError("Duplicate message")
            except ValueError:
                raise
            except Exception as e:
                logger.debug("Deduplicator error (proceeding): %s", e)

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
        bot_mentioned = any(m.get("mentioned_type") == "bot" for m in mentions)

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
            bot_id=app_id,
        )

    # ------------------------------------------------------------------ #
    #  Outgoing messages
    # ------------------------------------------------------------------ #

    async def send_text(self, chat_id: str, text: str, bot_id: str = "") -> bool:
        bot = self.get_bot(app_id=bot_id) or self.get_default_bot()
        if not bot:
            logger.error("send_text failed: no bot available (bot_id=%s)", bot_id)
            return False
        return await bot.send_text(chat_id, text)

    async def send_card(self, chat_id: str, card_type: str, context: dict, bot_id: str = "") -> bool:
        bot = self.get_bot(app_id=bot_id) or self.get_default_bot()
        if not bot:
            logger.error("send_card failed: no bot available (bot_id=%s)", bot_id)
            return False
        return await bot.send_card(chat_id, card_type, context)

    async def upload_file(self, chat_id: str, file_path: str, bot_id: str = "") -> bool:
        bot = self.get_bot(app_id=bot_id) or self.get_default_bot()
        if not bot:
            logger.error("upload_file failed: no bot available (bot_id=%s)", bot_id)
            return False
        return await bot.upload_file(chat_id, file_path)
