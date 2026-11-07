"""The hidden ``sq benchmark _auth-probe`` command."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app

runner = CliRunner()


@pytest.fixture
def known_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "squadron.benchmark.auth_check.resolve_model_alias",
        lambda alias: ("model-x", "openai") if alias == "known" else (alias, None),
    )


def _probe(*args: str):
    return runner.invoke(app, ["benchmark", "_auth-probe", *args])


def test_non_empty_response_exits_zero(known_alias: None, monkeypatch: pytest.MonkeyPatch) -> None:
    dispatch = AsyncMock(return_value="ok")
    monkeypatch.setattr("squadron.cli.commands.benchmark.one_shot_dispatch", dispatch)
    result = _probe("--model", "known")
    assert result.exit_code == 0
    assert "ok" in result.stdout
    assert dispatch.call_args.kwargs["profile_name"] == "openai"


def test_empty_response_exits_one(known_alias: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "squadron.cli.commands.benchmark.one_shot_dispatch",
        AsyncMock(return_value="  "),
    )
    result = _probe("--model", "known")
    assert result.exit_code == 1
    assert "empty response" in result.stderr


def test_raised_error_exits_one_with_message(
    known_alias: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "squadron.cli.commands.benchmark.one_shot_dispatch",
        AsyncMock(side_effect=RuntimeError("401 unauthorized")),
    )
    result = _probe("--model", "known")
    assert result.exit_code == 1
    assert "401 unauthorized" in result.stderr


def test_alias_with_no_profile_never_dispatches(
    known_alias: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    dispatch = AsyncMock(return_value="ok")
    monkeypatch.setattr("squadron.cli.commands.benchmark.one_shot_dispatch", dispatch)
    result = _probe("--model", "mystery")
    assert result.exit_code == 1
    assert "mystery" in result.stderr
    dispatch.assert_not_called()


def test_probe_is_hidden_from_help() -> None:
    result = runner.invoke(app, ["benchmark", "--help"])
    assert result.exit_code == 0
    assert "_auth-probe" not in result.stdout
