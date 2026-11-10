"""Tests for the shared provider loader module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from squadron.providers.loader import PROVIDER_MODULES, ensure_provider_loaded


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

    def test_unknown_provider_module_is_ignored(self) -> None:
        missing = ModuleNotFoundError("no module", name="squadron.providers.nonexistent")
        with patch("squadron.providers.loader.importlib.import_module", side_effect=missing):
            ensure_provider_loaded("nonexistent")  # get_provider reports it later

    def test_missing_dependency_of_known_provider_propagates(self) -> None:
        missing = ModuleNotFoundError("no module", name="openai")
        with (
            patch("squadron.providers.loader.importlib.import_module", side_effect=missing),
            pytest.raises(ModuleNotFoundError),
        ):
            ensure_provider_loaded("openai")

    def test_real_unknown_provider_does_not_raise(self) -> None:
        ensure_provider_loaded("definitely-not-a-provider")


class TestProviderModulesMapping:
    """Tests for the PROVIDER_MODULES constant."""

    def test_contains_openai(self) -> None:
        assert "openai" in PROVIDER_MODULES

    def test_contains_sdk(self) -> None:
        assert "sdk" in PROVIDER_MODULES

    def test_contains_openai_oauth(self) -> None:
        assert "openai-oauth" in PROVIDER_MODULES

    def test_openai_oauth_maps_to_codex(self) -> None:
        assert PROVIDER_MODULES["openai-oauth"] == "codex"
