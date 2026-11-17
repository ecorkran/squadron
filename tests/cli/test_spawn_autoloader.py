"""Tests for provider auto-loader (now in engine, not spawn command).

The _load_provider function moved from spawn.py to engine.py as part
of the daemon refactor. These tests verify it still works correctly.
"""

from __future__ import annotations

from unittest.mock import patch

from squadron.server.engine import _load_provider


class TestLoadProvider:
    def test_calls_import_module(self) -> None:
        target = "squadron.providers.loader.importlib.import_module"
        with patch(target) as mock_import:
            _load_provider("openai")
        mock_import.assert_called_once_with("squadron.providers.openai")

    def test_silences_import_error(self) -> None:
        target = "squadron.providers.loader.importlib.import_module"
        missing = ModuleNotFoundError("no module", name="squadron.providers.nonexistent-provider")
        with patch(target, side_effect=missing):
            # Must not raise
            _load_provider("nonexistent-provider")
