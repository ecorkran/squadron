"""Tests for the shared provider loader module."""

from __future__ import annotations

from unittest.mock import patch

from squadron.providers.loader import _PROVIDER_MODULES, ensure_provider_loaded


class TestEnsureProviderLoaded:
    """Tests for ensure_provider_loaded()."""

    def test_known_provider_imports_mapped_module(self) -> None:
        with patch("squadron.providers.loader.importlib.import_module") as mock_import:
            ensure_provider_loaded("openai")
            mock_import.assert_called_once_with("squadron.providers.openai")

    def test_sdk_provider_imports_sdk_module(self) -> None:
        with patch("squadron.providers.loader.importlib.import_module") as mock_import:
            ensure_provider_loaded("sdk")
            mock_import.assert_called_once_with("squadron.providers.sdk")

    def test_openai_oauth_imports_codex_module(self) -> None:
        with patch("squadron.providers.loader.importlib.import_module") as mock_import:
            ensure_provider_loaded("openai-oauth")
            mock_import.assert_called_once_with("squadron.providers.codex")

    def test_unknown_provider_falls_back_to_type_as_module(self) -> None:
        with patch("squadron.providers.loader.importlib.import_module") as mock_import:
            ensure_provider_loaded("custom-provider")
            mock_import.assert_called_once_with("squadron.providers.custom-provider")

    def test_import_error_swallowed_silently(self) -> None:
        with patch(
            "squadron.providers.loader.importlib.import_module",
            side_effect=ImportError("no such module"),
        ):
            # Should not raise
            ensure_provider_loaded("nonexistent")


class TestProviderModulesMapping:
    """Tests for the _PROVIDER_MODULES constant."""

    def test_contains_openai(self) -> None:
        assert "openai" in _PROVIDER_MODULES

    def test_contains_sdk(self) -> None:
        assert "sdk" in _PROVIDER_MODULES

    def test_contains_openai_oauth(self) -> None:
        assert "openai-oauth" in _PROVIDER_MODULES

    def test_openai_oauth_maps_to_codex(self) -> None:
        assert _PROVIDER_MODULES["openai-oauth"] == "codex"
