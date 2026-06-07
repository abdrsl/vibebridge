"""Legacy Feishu client stubs — re-export from legacy.feishu_client."""
from __future__ import annotations

from legacy.feishu_client import (
    FeishuClient,
    build_error_card,
    build_progress_card,
    build_result_card,
    build_start_card,
    feishu_client,
)

__all__ = [
    "FeishuClient",
    "build_error_card",
    "build_progress_card",
    "build_result_card",
    "build_start_card",
    "feishu_client",
]
