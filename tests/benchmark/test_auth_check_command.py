"""``sq benchmark auth-check`` with run_auth_check patched."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from squadron.benchmark.auth_check import (
    AuthAnswer,
    AuthCheckResult,
    UnresolvedProfileError,
)
from squadron.cli.app import app
from squadron.providers.base import ProfileName

runner = CliRunner()


def row(answer: AuthAnswer, stderr: str = "", detail: str = "") -> AuthCheckResult:
    return AuthCheckResult(ProfileName.SDK, "opus", answer, 0, stderr, detail)


@pytest.fixture(autouse=True)
def fake_sq(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: "/abs/bin/sq")


def patch_check(monkeypatch: pytest.MonkeyPatch, result: object) -> None:
    def fake(*_args: object, **_kwargs: object) -> list[AuthCheckResult]:
        if isinstance(result, Exception):
            raise result
        return result  # type: ignore[return-value]

    monkeypatch.setattr("squadron.cli.commands.benchmark.run_auth_check", fake)


def test_all_yes_exits_zero_and_prints_probed_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_check(monkeypatch, [row(AuthAnswer.YES)])
    result = runner.invoke(app, ["benchmark", "auth-check", "--model", "opus"])
    assert result.exit_code == 0
    assert "/abs/bin/sq" in result.stdout
    assert "opus" in result.stdout


def test_no_exits_one_with_error_shown(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_check(monkeypatch, [row(AuthAnswer.NO, stderr="401 unauthorized\nmore")])
    result = runner.invoke(app, ["benchmark", "auth-check", "--model", "opus"])
    assert result.exit_code == 1
    assert "401 unauthorized" in result.stdout
    assert "more" not in result.stdout


def test_carryover_replaced_exits_one_with_explanation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_check(monkeypatch, [row(AuthAnswer.YES_CARRYOVER_REPLACED, detail="replaced X")])
    result = runner.invoke(app, ["benchmark", "auth-check", "--model", "opus"])
    assert result.exit_code == 1
    assert "replaced X" in result.stdout


def test_unknown_alias_exits_one_naming_it(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_check(monkeypatch, UnresolvedProfileError("zzz", "is unknown"))
    result = runner.invoke(app, ["benchmark", "auth-check", "--model", "zzz"])
    assert result.exit_code == 1
    assert "zzz" in result.stderr


def test_no_model_is_usage_error() -> None:
    result = runner.invoke(app, ["benchmark", "auth-check"])
    assert result.exit_code == 2
