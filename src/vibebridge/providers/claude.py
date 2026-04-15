"""Claude Code provider implementation."""

from __future__ import annotations

from typing import AsyncIterator

from .base import BaseProvider, StreamEvent, StreamEventType


class ClaudeProvider(BaseProvider):
    name = "claude"
    display_name = "Claude Code"

    def __init__(self, binary: str | None = None):
        self.binary = binary or "claude"

    async def health_check(self) -> tuple[bool, str]:
        import shutil

        if shutil.which(self.binary):
            return True, f"Claude Code found ({self.binary})"
        return False, "Claude Code not found in PATH"

    async def create_task(
        self,
        prompt: str,
        workdir: str,
        session_id: str,
        chat_id: str | None = None,
    ) -> str:
        task_id = f"claude_{session_id}"
        return task_id

    async def stream_task(self, task_id: str) -> AsyncIterator[StreamEvent]:
        yield StreamEvent(
            type=StreamEventType.STATUS,
            content="Claude provider is a placeholder.",
            task_id=task_id,
        )
        yield StreamEvent(
            type=StreamEventType.ERROR,
            content="Claude execution via bridge is not yet fully implemented.",
            task_id=task_id,
        )

    async def cancel_task(self, task_id: str) -> bool:
        return True

    def default_workdir(self) -> str:
        from pathlib import Path

        return str(Path.home() / "workspace")
