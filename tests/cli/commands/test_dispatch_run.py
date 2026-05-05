"""Tests for the sq _dispatch-run hidden subcommand."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from squadron.cli.app import app

_runner = CliRunner()

_MODULE = "squadron.cli.commands.dispatch_run"


def _invoke(*args: str) -> object:
    return _runner.invoke(app, ["_dispatch-run", *args])


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_dispatch_run_with_prompt_file(tmp_path: Path) -> None:
    """Reads prompt file, calls one_shot_dispatch, prints result, exits 0."""
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Write a haiku.", encoding="utf-8")

    with patch(
        f"{_MODULE}.one_shot_dispatch",
        new=AsyncMock(return_value="response text"),
    ):
        result = _runner.invoke(
            app,
            [
                "_dispatch-run",
                "--prompt-file",
                str(prompt_file),
                "--model",
                "minimax-text-01",
                "--profile",
                "openrouter",
            ],
        )

    assert result.exit_code == 0
    assert "response text" in (result.output or "")


def test_dispatch_run_resolves_profile_from_alias(tmp_path: Path) -> None:
    """Without --profile, resolves model/profile via ModelResolver."""
    prompt_file = tmp_path / "p.txt"
    prompt_file.write_text("hello", encoding="utf-8")

    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = ("minimax-text-01", "openrouter")

    with (
        patch(
            f"{_MODULE}.one_shot_dispatch",
            new=AsyncMock(return_value="ok"),
        ) as mock_dispatch,
        patch("squadron.pipeline.resolver.ModelResolver", return_value=mock_resolver),
    ):
        result = _runner.invoke(
            app,
            [
                "_dispatch-run",
                "--prompt-file",
                str(prompt_file),
                "--model",
                "minimax",
            ],
        )

    assert result.exit_code == 0
    call_kwargs = mock_dispatch.call_args.kwargs
    assert call_kwargs["profile_name"] == "openrouter"
    assert call_kwargs["model_id"] == "minimax-text-01"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_dispatch_run_errors_when_prompt_file_missing() -> None:
    """Non-existent prompt file: exit code != 0 and stderr contains 'not found'."""
    result = _runner.invoke(
        app,
        [
            "_dispatch-run",
            "--prompt-file",
            "/tmp/does-not-exist-xyz.txt",
            "--model",
            "minimax-text-01",
            "--profile",
            "openrouter",
        ],
    )

    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
    assert "not found" in combined.lower() or "not found" in combined


def test_dispatch_run_bad_param_format(tmp_path: Path) -> None:
    """--param without '=' produces exit 1 and mentions the bad value."""
    prompt_file = tmp_path / "p.txt"
    prompt_file.write_text("hi", encoding="utf-8")

    result = _runner.invoke(
        app,
        [
            "_dispatch-run",
            "--prompt-file",
            str(prompt_file),
            "--model",
            "minimax-text-01",
            "--profile",
            "openrouter",
            "--param",
            "noequals",
        ],
    )

    assert result.exit_code == 1
    assert "noequals" in (result.output or "")


def test_dispatch_run_provider_failure_exits_1(tmp_path: Path) -> None:
    """Provider exception caught and reported as exit 1."""
    prompt_file = tmp_path / "p.txt"
    prompt_file.write_text("hi", encoding="utf-8")

    with patch(
        f"{_MODULE}.one_shot_dispatch",
        new=AsyncMock(side_effect=RuntimeError("network failed")),
    ):
        result = _runner.invoke(
            app,
            [
                "_dispatch-run",
                "--prompt-file",
                str(prompt_file),
                "--model",
                "minimax-text-01",
                "--profile",
                "openrouter",
            ],
        )

    assert result.exit_code == 1
    assert "network failed" in (result.output or "")


# ---------------------------------------------------------------------------
# Hidden from help
# ---------------------------------------------------------------------------


def test_dispatch_run_hidden_from_help() -> None:
    """sq --help output does not list _dispatch-run."""
    result = _runner.invoke(app, ["--help"])
    assert "_dispatch-run" not in (result.output or "")
