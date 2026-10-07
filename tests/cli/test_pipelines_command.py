"""sq pipelines list (slice 199)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.pipeline import loader
from tests.cli.test_run_views import write_pipeline


def test_lists_project_and_user_pipelines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # HOME is a per-test temp dir (tests/conftest.py), so the user dir is hermetic.
    monkeypatch.chdir(tmp_path)
    write_pipeline(tmp_path / "project-documents/user/pipelines", "my-loop")
    write_pipeline(Path.home() / ".config/squadron/pipelines", "mine")

    result = CliRunner().invoke(app, ["pipelines", "list"])

    assert result.exit_code == 0, result.output
    assert "Built-in (" in result.output
    assert "Project (1)" in result.output
    assert "User (1)" in result.output


def test_no_pipelines_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(loader, "_BUILTIN_DIR", tmp_path / "no-builtins")

    result = CliRunner().invoke(app, ["pipelines", "list"])

    assert result.exit_code == 0, result.output
    assert "No pipelines found." in result.output


def test_bare_group_prints_help() -> None:
    result = CliRunner().invoke(app, ["pipelines"])

    assert "list" in result.output
