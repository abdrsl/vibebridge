"""Feishu WebSocket long-connection client for VibeBridge.

Wraps the lark-oapi SDK to maintain a persistent WebSocket connection
to Feishu's event subscription service. Incoming messages are forwarded
to the local webhook endpoint for processing.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FeishuWebSocketClient:
    """Feishu WebSocket long-connection client.

    Starts a background thread that maintains a WebSocket connection.
    When events arrive, they are forwarded to the local webhook endpoint.
    """

    def __init__(self, app_id: str, app_secret: str, webhook_url: str = "http://127.0.0.1:8000/feishu/webhook"):
        self.app_id = app_id
        self.app_secret = app_secret
        self.webhook_url = webhook_url
        self.running = False
        self._client_thread: Optional[threading.Thread] = None
        self._client_loop: Optional[asyncio.AbstractEventLoop] = None

    async def start(self) -> None:
        """Start the WebSocket client in a background thread."""
        if self.running:
            logger.warning("WebSocket client already running")
            return

        logger.info(f"Starting Feishu WebSocket client for app {self.app_id[:10]}...")
        self.running = True

        def _run_client() -> None:
            _run_ws_client(
                app_id=self.app_id,
                app_secret=self.app_secret,
                webhook_url=self.webhook_url,
                running_ref=self,
            )

        self._client_thread = threading.Thread(target=_run_client, daemon=True)
        self._client_thread.start()
        logger.info("WebSocket client thread started")

    async def stop(self) -> None:
        """Stop the WebSocket client."""
        if not self.running:
            return
        logger.info("Stopping WebSocket client...")
        self.running = False
        # The thread will exit on next reconnection cycle


def _run_ws_client(
    app_id: str,
    app_secret: str,
    webhook_url: str,
    running_ref: Any,
) -> None:
    """Run the WebSocket client in a dedicated thread."""
    import json as _json
    import urllib.request

    # Set env vars for lark-oapi SDK
    os.environ["FEISHU_APP_ID"] = app_id
    os.environ["FEISHU_APP_SECRET"] = app_secret

    # Create event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    running_ref._client_loop = loop

    # Patch lark_oapi's global loop
    try:
        from lark_oapi import ws
        ws.client.loop = loop
    except Exception:
        pass

    from lark_oapi.core.enum import LogLevel
    from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
    from lark_oapi.ws import Client

    # Create event handler that forwards to webhook
    class BridgeEventHandler(EventDispatcherHandler):
        def __init__(self):
            super().__init__()
            from lark_oapi.event.dispatcher_handler import ICallBackProcessor

            class ForwardProcessor:
                def type(self):
                    return dict

                def do(self, data: dict):
                    try:
                        payload = _json.dumps(data).encode("utf-8")
                        req = urllib.request.Request(
                            webhook_url,
                            data=payload,
                            headers={"Content-Type": "application/json"},
                            method="POST",
                        )
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            result = _json.loads(resp.read())
                            return result
                    except Exception as e:
                        logger.debug(f"Webhook forward error: {e}")
                        return {"code": 0, "msg": "ok"}

            # Register for IM messages, card actions, and chat events
            processor = ForwardProcessor()
            self._callback_processor_map = {
                "p2.im.message.receive_v1": processor,
                "p2.card.action.trigger": processor,
                "im.chat.access_event.bot_p2p_chat_entered_v1": processor,
            }

        def on_open(self, *args, **kwargs):
            logger.info("[WS] Feishu WebSocket connected!")

        def on_close(self, *args, **kwargs):
            logger.info("[WS] Feishu WebSocket closed")

        def on_error(self, *args, **kwargs):
            logger.error(f"[WS] Feishu WebSocket error: args={args}, kwargs={kwargs}")

    handler = BridgeEventHandler()

    retry_count = 0
    while getattr(running_ref, "running", False):
        try:
            client = Client(
                app_id=app_id,
                app_secret=app_secret,
                event_handler=handler,
                auto_reconnect=True,
                log_level=LogLevel.INFO,
            )
            logger.info(f"[WS] Starting WebSocket client (attempt {retry_count + 1})")
            client.start()
            retry_count = 0
        except Exception as e:
            retry_count += 1
            logger.error(f"[WS] Client error (retry {retry_count}): {e}")

        if getattr(running_ref, "running", False):
            delay = min(5 * (2 ** min(retry_count, 8)), 300)
            jitter = random.uniform(0.8, 1.2)
            time.sleep(delay * jitter)
