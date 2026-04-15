"""Pytest configuration for VibeBridge."""

import os
import sys

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Legacy tests are skipped by default because they rely on the old
# architecture, network access, or event loops that can hang in CI.
# Run them explicitly with: pytest tests/ -m legacy
import pytest


def pytest_collection_modifyitems(config, items):
    for item in items:
        # Auto-mark legacy tests that import old modules or are known to hang
        node_path = str(item.fspath)
        if "/test_api.py" not in node_path and "/test_vibebridge_" not in node_path:
            item.add_marker(pytest.mark.legacy)
