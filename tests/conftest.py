"""Pytest configuration for VibeBridge."""

import os
import sys

# Ensure src is on path
src_path = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, src_path)

# Enable pytest-asyncio auto mode
import pytest

pytest_plugins = ("pytest_asyncio",)


def pytest_collection_modifyitems(config, items):
    for item in items:
        # Auto-mark legacy tests that import old modules or are known to hang
        node_path = str(item.fspath)
        if "/test_api.py" not in node_path and "/test_vibebridge_" not in node_path:
            item.add_marker(pytest.mark.legacy)
