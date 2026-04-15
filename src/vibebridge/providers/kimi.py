"""Kimi Code CLI provider implementation (ACP/MCP-based)."""

from __future__ import annotations

from typing import AsyncIterator

import httpx

from .base import BaseProvider, StreamEvent, StreamEventType


class KimiProvider(BaseProvider):
    name = "kimi"
    display_name = "Kimi Code"

    def __init__(self, acp_url: str = "http://127.0.0.1:9876"):
        self.acp_url = acp_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def health_check(self) -> tuple[bool, str]:
        try:
            resp = await self._client.get(f"{self.acp_url}/health")
            if resp.status_code == 200:
                return True, "Kimi ACP ready"
            return False, f"Kimi ACP returned {resp.status_code}"
        except Exception as e:
            return False, str(e)

    async def create_task(
        self,
        prompt: str,
        workdir: str,
        session_id: str,
        chat_id: str | None = None,
    ) -> str:
        task_id = f"kimi_{session_id}"
        return task_id

    async def stream_task(self, task_id: str) -> AsyncIterator[StreamEvent]:
        yield StreamEvent(
            type=StreamEventType.STATUS,
            content="Kimi provider is a placeholder. ACP/MCP integration pending.",
            task_id=task_id,
        )
        yield StreamEvent(
            type=StreamEventType.ERROR,
            content="Kimi execution via bridge is not yet fully implemented. Start `kimi acp` first.",
            task_id=task_id,
        )

    async def cancel_task(self, task_id: str) -> bool:
        return True

    def default_workdir(self) -> str:
        from pathlib import Path

        return str(Path.home() / "workspace")
