"""VibeBridge Admin Panel — Web UI for configuration and monitoring."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/admin", tags=["admin"])

templates = Jinja2Templates(directory=str(__file__).replace("__init__.py", "templates"))
