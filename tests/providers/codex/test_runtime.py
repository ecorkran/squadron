"""Tests for the Codex runtime resolver (slice 129, D2)."""

from __future__ import annotations

import pytest

from squadron.providers.codex import runtime
from squadron.providers.codex.runtime import (
    CODEX_INSTALL_COMMAND,
    CodexRuntime,
    RuntimeSource,
    resolve_codex_runtime,
)
from squadron.providers.errors import ProviderError

_PATH_CODEX = "/usr/local/bin/codex"


def _fake_environment(
    monkeypatch: pytest.MonkeyPatch,
    *,
    modules: set[str],
    path_binary: str | None,
) -> None:
    """Pretend exactly ``modules`` are importable and ``codex`` resolves to ``path_binary``."""
    monkeypatch.setattr(runtime, "_module_available", lambda name: name in modules)
    monkeypatch.setattr(runtime.shutil, "which", lambda _name: path_binary)
    monkeypatch.setattr(runtime, "_sdk_version", lambda: "0.160.0")


class TestResolveCodexRuntime:
    def test_bundled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _fake_environment(monkeypatch, modules={"openai_codex", "codex_cli_bin"}, path_binary=None)
        assert resolve_codex_runtime() == CodexRuntime(
            source=RuntimeSource.bundled, path=None, package_version="0.160.0"
        )

    def test_path_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _fake_environment(monkeypatch, modules={"openai_codex"}, path_binary=_PATH_CODEX)
        assert resolve_codex_runtime() == CodexRuntime(
            source=RuntimeSource.path, path=_PATH_CODEX, package_version="0.160.0"
        )

    def test_bundled_preferred_when_both_exist(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _fake_environment(
            monkeypatch, modules={"openai_codex", "codex_cli_bin"}, path_binary=_PATH_CODEX
        )
        assert resolve_codex_runtime().source is RuntimeSource.bundled

    def test_no_binary_names_both_remedies(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _fake_environment(monkeypatch, modules={"openai_codex"}, path_binary=None)
        with pytest.raises(ProviderError) as exc_info:
            resolve_codex_runtime()
        message = str(exc_info.value)
        assert CODEX_INSTALL_COMMAND in message
        assert "PATH" in message

    def test_package_missing_carries_install_hint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _fake_environment(monkeypatch, modules=set(), path_binary=_PATH_CODEX)
        with pytest.raises(ProviderError) as exc_info:
            resolve_codex_runtime()
        assert CODEX_INSTALL_COMMAND in str(exc_info.value)
        assert CODEX_INSTALL_COMMAND == "uv tool install 'squadron-ai[codex]'"


class TestImportSafety:
    def test_module_has_no_sdk_import(self) -> None:
        # The resolver must load on a default install, so no top-level SDK import.
        assert "openai_codex" not in vars(runtime)
        assert "codex_cli_bin" not in vars(runtime)


def test_package_missing_is_a_distinct_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from squadron.providers.codex.runtime import CodexExtraMissingError

    _fake_environment(monkeypatch, modules=set(), path_binary=None)
    with pytest.raises(CodexExtraMissingError):
        resolve_codex_runtime()
