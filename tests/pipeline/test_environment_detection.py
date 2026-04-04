"""Tests for execution mode detection in the run command."""

from __future__ import annotations

import pytest
import typer

from squadron.cli.commands.run import _resolve_execution_mode


def test_prompt_only_flag_returns_prompt_only() -> None:
    result = _resolve_execution_mode(prompt_only=True)
    assert result == "prompt-only"


def test_normal_environment_returns_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDECODE", raising=False)
    result = _resolve_execution_mode(prompt_only=False)
    assert result == "sdk"


def test_claudecode_env_raises_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDECODE", "1")
    with pytest.raises(typer.Exit):
        _resolve_execution_mode(prompt_only=False)


def test_prompt_only_takes_precedence_over_claudecode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--prompt-only returns prompt-only even if CLAUDECODE is set."""
    monkeypatch.setenv("CLAUDECODE", "1")
    result = _resolve_execution_mode(prompt_only=True)
    assert result == "prompt-only"
