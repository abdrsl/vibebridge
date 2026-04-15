"""Unified session management."""

from __future__ import annotations

import json
import os
import tempfile
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
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"[SessionManager] Warning: failed to create data_dir {self.data_dir}: {e}")
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
        session: Session | None = None
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                session = Session(**data)
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                print(f"[SessionManager] Corrupted session file {path}: {e}. Recreating.")
                try:
                    backup = path.with_suffix(".json.bak")
                    path.rename(backup)
                except Exception:
                    pass

        if session is None:
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
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            session = Session(**data)
            self._cache[session_id] = session
            return session
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            print(f"[SessionManager] Corrupted session file {path}: {e}")
            return None

    def save(self, session: Session) -> None:
        session.updated_at = time.time()
        path = self._path(session.session_id)
        try:
            # Ensure parent dir exists
            path.parent.mkdir(parents=True, exist_ok=True)
            # Atomic write via temp file + rename
            fd, tmp_path = tempfile.mkstemp(
                dir=str(path.parent), prefix=f".{path.name}.tmp_"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(session.model_dump(), f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, path)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                raise
        except Exception as e:
            print(f"[SessionManager] Failed to save session {session.session_id}: {e}")

    def clear(self, session_id: str) -> bool:
        self._cache.pop(session_id, None)
        path = self._path(session_id)
        if path.exists():
            try:
                path.unlink()
                return True
            except Exception as e:
                print(f"[SessionManager] Failed to delete session {session_id}: {e}")
        return False


# Global cached instance
_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    global _manager
    if _manager is None:
        _manager = SessionManager()
    return _manager
