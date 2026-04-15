"""OpenClaw provider implementation (HTTP Gateway)."""

from __future__ import annotations

from typing import AsyncIterator

import httpx

from .base import BaseProvider, StreamEvent, StreamEventType


class OpenClawProvider(BaseProvider):
    name = "openclaw"
    display_name = "OpenClaw"

    def __init__(self, gateway_url: str = "http://127.0.0.1:18789"):
        self.gateway_url = gateway_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def health_check(self) -> tuple[bool, str]:
        try:
            resp = await self._client.get(f"{self.gateway_url}/health")
            if resp.status_code == 200:
                return True, f"Gateway OK ({resp.status_code})"
            return False, f"Gateway returned {resp.status_code}"
        except Exception as e:
            return False, str(e)

    async def create_task(
        self,
        prompt: str,
        workdir: str,
        session_id: str,
        chat_id: str | None = None,
    ) -> str:
        # TODO: Integrate with OpenClaw Gateway MCP loopback or internal API
        task_id = f"ocw_{session_id}"
        return task_id

    async def stream_task(self, task_id: str) -> AsyncIterator[StreamEvent]:
        yield StreamEvent(
            type=StreamEventType.STATUS,
            content="OpenClaw provider is a placeholder. Please use OpenCode or configure OpenClaw MCP.",
            task_id=task_id,
        )
        yield StreamEvent(
            type=StreamEventType.ERROR,
            content="OpenClaw execution via bridge is not yet fully implemented.",
            task_id=task_id,
        )

    async def cancel_task(self, task_id: str) -> bool:
        return True

    def default_workdir(self) -> str:
        from pathlib import Path

        return str(Path.home() / "workspace")
