"""Tests for ``sq squash`` (slice 948)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from tests.conftest import run_test_git
from tests.pipeline.commit_fixtures import cf_client
from tests.pipeline.squash_helpers import assert_history_unchanged, history, planning_run

runner = CliRunner()


@pytest.fixture
def in_repo(temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.chdir(temp_git_repo)
    with patch("squadron.cli.commands.squash_run.ContextForgeClient", return_value=cf_client()):
        yield temp_git_repo


def _log(repo: Path) -> list[str]:
    return run_test_git(repo, "log", "--format=%s").splitlines()


def test_squash_collapses_the_run_and_names_the_tag(in_repo: Path) -> None:
    planning_run(in_repo, 3)

    result = runner.invoke(app, ["squash", "design", "--slice", "105"])

    assert result.exit_code == 0, result.output
    assert "squashed 3 commits into" in result.output
    tag = run_test_git(in_repo, "tag", "-l", "squash-backup/*").strip()
    assert f"backup tag: {tag}" in result.output
    assert f"git tag -d {tag}" in result.output
    assert _log(in_repo) == ["docs: planning round 1", "init"]


def test_dry_run_prints_the_run_and_rewrites_nothing(in_repo: Path) -> None:
    shas = planning_run(in_repo, 3)
    before = history(in_repo)

    result = runner.invoke(app, ["squash", "design", "--slice", "105", "--dry-run"])

    assert result.exit_code == 0, result.output
    for sha in shas:
        assert sha[:8] in result.output
    assert "surviving message: docs: planning round 1" in result.output
    assert f"squash-backup/design-105-{shas[-1][:8]}" in result.output
    assert "dry run: nothing rewritten" in result.output
    assert_history_unchanged(in_repo, before)


def test_run_of_one_is_nothing_to_squash(in_repo: Path) -> None:
    planning_run(in_repo, 1)

    result = runner.invoke(app, ["squash", "design", "--slice", "105", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == "nothing to squash"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["squash", "code", "--slice", "1"], "must be one of"),
        (["squash", "design", "--plan", "100"], "takes --slice N"),
    ],
)
def test_bad_scope_exits_one(in_repo: Path, args: list[str], message: str) -> None:
    result = runner.invoke(app, args)

    assert result.exit_code == 1
    assert message in result.output


def test_refusal_exits_one(in_repo: Path) -> None:
    planning_run(in_repo, 2)
    (in_repo / "README.md").write_text("dirty\n")

    result = runner.invoke(app, ["squash", "design", "--slice", "105"])

    assert result.exit_code == 1
    assert "not clean" in result.output
