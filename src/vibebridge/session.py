"""Unified session management."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .config import get_config


class Session(BaseModel):
    session_id: str
    user_id: str
    chat_id: str
    provider: str = "opencode"
    workdir: str = ""
    history: list[dict[str, Any]] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    def add_message(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content, "ts": time.time()})
        self.updated_at = time.time()


class SessionManager:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or get_config().data_dir / "sessions"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Session] = {}

    def _path(self, session_id: str) -> Path:
        return self.data_dir / f"{session_id}.json"

    def get_or_create(
        self,
        user_id: str,
        chat_id: str,
        provider: str = "opencode",
        workdir: str = "",
    ) -> Session:
        session_id = f"vb_{user_id}_{chat_id}"
        if session_id in self._cache:
            return self._cache[session_id]

        path = self._path(session_id)
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            session = Session(**data)
        else:
            session = Session(
                session_id=session_id,
                user_id=user_id,
                chat_id=chat_id,
                provider=provider,
                workdir=workdir or str(Path.home() / "workspace"),
            )
            self.save(session)

        self._cache[session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        if session_id in self._cache:
            return self._cache[session_id]
        path = self._path(session_id)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        session = Session(**data)
        self._cache[session_id] = session
        return session

    def save(self, session: Session) -> None:
        session.updated_at = time.time()
        path = self._path(session.session_id)
        with path.open("w", encoding="utf-8") as f:
            json.dump(session.model_dump(), f, ensure_ascii=False, indent=2)

    def clear(self, session_id: str) -> bool:
        self._cache.pop(session_id, None)
        path = self._path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False


# Global instance
_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    global _manager
    if _manager is None:
        _manager = SessionManager()
    return _manager
