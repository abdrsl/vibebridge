"""Base protocol for code-agent providers."""

from __future__ import annotations

from enum import Enum
from typing import AsyncIterator, Protocol

from pydantic import BaseModel


class StreamEventType(str, Enum):
    STATUS = "status"
    TOOL_USE = "tool_use"
    TEXT = "text"
    ERROR = "error"
    DONE = "done"


class StreamEvent(BaseModel):
    type: StreamEventType
    content: str
    task_id: str | None = None
    metadata: dict = {}


class BaseProvider(Protocol):
    name: str
    display_name: str

    async def health_check(self) -> tuple[bool, str]:
        """Return (is_healthy, status_message)."""
        ...

    async def create_task(
        self,
        prompt: str,
        workdir: str,
        session_id: str,
        chat_id: str | None = None,
    ) -> str:
        """Create a task and return task_id."""
        ...

    async def stream_task(self, task_id: str) -> AsyncIterator[StreamEvent]:
        """Yield stream events until task completion or error."""
        ...

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        ...

    def default_workdir(self) -> str:
        """Return the suggested default working directory."""
        ...
