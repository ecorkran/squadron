"""Tests for ``sq squash`` (slice 948)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from tests.conftest import run_test_git
from tests.pipeline.commit_fixtures import ARCH_FILE, PLAN_FILE, cf_client
from tests.pipeline.squash_helpers import (
    FOREIGN_FILE,
    assert_history_unchanged,
    commit_files,
    history,
    planning_run,
)

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

    result = runner.invoke(app, ["squash", "slice", "105"])

    assert result.exit_code == 0, result.output
    assert "squashed 3 commits into" in result.output
    tag = run_test_git(in_repo, "tag", "-l", "squash-backup/*").strip()
    assert f"backup tag: {tag}" in result.output
    assert f"git tag -d {tag}" in result.output
    assert _log(in_repo) == ["docs: planning round 1", "init"]


def test_dry_run_prints_the_run_and_rewrites_nothing(in_repo: Path) -> None:
    shas = planning_run(in_repo, 3)
    before = history(in_repo)

    result = runner.invoke(app, ["squash", "slice", "105", "--dry-run"])

    assert result.exit_code == 0, result.output
    for sha in shas:
        assert sha[:8] in result.output
    assert "surviving message: docs: planning round 1" in result.output
    assert f"squash-backup/slice-105-{shas[-1][:8]}" in result.output
    assert "dry run: nothing rewritten" in result.output
    assert_history_unchanged(in_repo, before)


def test_buried_run_reports_the_recreated_later_commits(in_repo: Path) -> None:
    planning_run(in_repo, 3)
    commit_files(in_repo, "feat: code", FOREIGN_FILE)

    dry = runner.invoke(app, ["squash", "slice", "105", "--dry-run"])
    result = runner.invoke(app, ["squash", "slice", "105"])

    assert "later commits recreated on top (content unchanged): 1" in dry.output
    assert result.exit_code == 0, result.output
    assert "recreated 1 later commits on top (content unchanged)" in result.output
    assert _log(in_repo) == ["feat: code", "docs: planning round 1", "init"]


def test_run_of_one_is_nothing_to_squash(in_repo: Path) -> None:
    planning_run(in_repo, 1)

    result = runner.invoke(app, ["squash", "slice", "105", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == "nothing to squash"


def test_arch_is_accepted_and_architecture_is_not(in_repo: Path) -> None:
    planning_run(in_repo, 3, artifact=ARCH_FILE)

    accepted = runner.invoke(app, ["squash", "arch", "100", "--dry-run"])
    rejected = runner.invoke(app, ["squash", "architecture", "100"])

    assert accepted.exit_code == 0, accepted.output
    assert "run of 3 commits" in accepted.output
    assert rejected.exit_code == 2


def test_plan_squashes_the_slice_plan(in_repo: Path) -> None:
    planning_run(in_repo, 2, artifact=PLAN_FILE)

    result = runner.invoke(app, ["squash", "plan", "100"])

    assert result.exit_code == 0, result.output
    assert "squashed 2 commits" in result.output
    assert "squash-backup/plan-100-" in result.output


def test_unknown_kind_exits_two(in_repo: Path) -> None:
    result = runner.invoke(app, ["squash", "code", "105"])
    assert result.exit_code == 2


def test_missing_slice_plan_exits_one(in_repo: Path) -> None:
    result = runner.invoke(app, ["squash", "plan", "999"])
    assert result.exit_code == 1
    assert "999-slices" in result.output


def test_refusal_exits_one(in_repo: Path) -> None:
    planning_run(in_repo, 2)
    (in_repo / "README.md").write_text("dirty\n")

    result = runner.invoke(app, ["squash", "slice", "105"])

    assert result.exit_code == 1
    assert "not clean" in result.output


def test_pipeline_dry_run_lists_squash_and_runs_no_git(in_repo: Path) -> None:
    planning_run(in_repo, 3)
    before = history(in_repo)

    result = runner.invoke(app, ["run", "P4", "105", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "(squash)" in result.output
    assert_history_unchanged(in_repo, before)
