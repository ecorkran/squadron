"""Tests for squashing a run buried under later commits, on real repositories (#271)."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest

from squadron.pipeline.squash import (
    SquashKind,
    SquashPlan,
    SquashRefusedError,
    apply_squash,
    plan_squash,
)
from tests.conftest import run_test_git
from tests.pipeline.commit_fixtures import TASKS_FILE, cf_client
from tests.pipeline.squash_helpers import FOREIGN_FILE, commit_files, head, planning_run, squash_target


def _plan(repo: Path, kind: SquashKind = SquashKind.SLICE) -> SquashPlan | None:
    return plan_squash(squash_target(kind), "main", repo, cf_client())


def _squash(repo: Path, kind: SquashKind = SquashKind.SLICE) -> str:
    plan = _plan(repo, kind)
    assert plan is not None
    return apply_squash(plan, repo)


def _tree(repo: Path, rev: str = "HEAD") -> str:
    return run_test_git(repo, "rev-parse", f"{rev}^{{tree}}").strip()


def _first_parent_subjects(repo: Path) -> list[str]:
    return run_test_git(repo, "log", "--first-parent", "--format=%s").splitlines()


def _identity(repo: Path, rev: str) -> str:
    """Everything about a commit except its parents: tree, author, committer, message."""
    return run_test_git(repo, "show", "-s", "--format=%T%n%an%ae%ad%n%cn%ce%cd%n%B", rev)


def test_run_under_foreign_commits_is_squashed_and_later_commits_kept(temp_git_repo: Path) -> None:
    parent = head(temp_git_repo)
    shas = planning_run(temp_git_repo, 3)
    first = commit_files(temp_git_repo, "feat: code one", FOREIGN_FILE)
    second = commit_files(temp_git_repo, "feat: code two", FOREIGN_FILE)
    before_tree = _tree(temp_git_repo)
    plan = _plan(temp_git_repo)
    assert plan is not None and plan.later == 2

    squashed = apply_squash(plan, temp_git_repo)

    assert _first_parent_subjects(temp_git_repo) == [
        "feat: code two",
        "feat: code one",
        "docs: planning round 1",
        "init",
    ]
    assert run_test_git(temp_git_repo, "rev-parse", f"{squashed}^").strip() == parent
    assert _tree(temp_git_repo, squashed) == _tree(temp_git_repo, shas[-1])
    assert _tree(temp_git_repo) == before_tree
    assert _identity(temp_git_repo, "HEAD") == _identity(temp_git_repo, second)
    assert _identity(temp_git_repo, "HEAD^") == _identity(temp_git_repo, first)
    assert run_test_git(temp_git_repo, "status", "--porcelain") == ""


def test_run_under_a_merged_branch_keeps_the_merge(temp_git_repo: Path) -> None:
    planning_run(temp_git_repo, 3)
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "slice")
    commit_files(temp_git_repo, "feat: slice one", FOREIGN_FILE)
    side_tip = commit_files(temp_git_repo, "feat: slice two", FOREIGN_FILE)
    run_test_git(temp_git_repo, "checkout", "-q", "main")
    run_test_git(temp_git_repo, "merge", "-q", "--no-ff", "-m", "merge slice", "slice")
    old_merge = head(temp_git_repo)

    squashed = _squash(temp_git_repo)

    assert _first_parent_subjects(temp_git_repo) == ["merge slice", "docs: planning round 1", "init"]
    assert run_test_git(temp_git_repo, "rev-list", "--count", "HEAD").strip() == "5"
    assert _identity(temp_git_repo, "HEAD") == _identity(temp_git_repo, old_merge)
    assert _identity(temp_git_repo, "HEAD^2") == _identity(temp_git_repo, side_tip)
    assert run_test_git(temp_git_repo, "rev-parse", "HEAD^2~1^").strip() == squashed


def test_slice_and_tasks_runs_both_squash_after_a_merge(temp_git_repo: Path) -> None:
    planning_run(temp_git_repo, 3)
    planning_run(temp_git_repo, 2, artifact=TASKS_FILE)
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "slice")
    commit_files(temp_git_repo, "feat: slice code", FOREIGN_FILE)
    run_test_git(temp_git_repo, "checkout", "-q", "main")
    run_test_git(temp_git_repo, "merge", "-q", "--no-ff", "-m", "merge slice", "slice")
    before_tree = _tree(temp_git_repo)

    _squash(temp_git_repo, SquashKind.TASKS)
    _squash(temp_git_repo, SquashKind.SLICE)

    assert _first_parent_subjects(temp_git_repo) == [
        "merge slice",
        "docs: planning round 1",
        "docs: planning round 1",
        "init",
    ]
    assert _tree(temp_git_repo) == before_tree
    assert _plan(temp_git_repo, SquashKind.TASKS) is None
    assert _plan(temp_git_repo, SquashKind.SLICE) is None


def test_branch_forked_before_the_run_keeps_its_commits(temp_git_repo: Path) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "early")
    early = commit_files(temp_git_repo, "feat: early work", FOREIGN_FILE)
    run_test_git(temp_git_repo, "checkout", "-q", "main")
    planning_run(temp_git_repo, 3)
    run_test_git(temp_git_repo, "merge", "-q", "--no-ff", "-m", "merge early", "early")

    _squash(temp_git_repo)

    assert run_test_git(temp_git_repo, "rev-parse", "HEAD^2").strip() == early


def test_branch_forked_inside_the_run_refuses(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    shas = planning_run(temp_git_repo, 3)
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "mid", shas[1])
    commit_files(temp_git_repo, "feat: forked mid-run", FOREIGN_FILE)
    run_test_git(temp_git_repo, "checkout", "-q", "main")
    run_test_git(temp_git_repo, "merge", "-q", "--no-ff", "-m", "merge mid", "mid")
    before = head(temp_git_repo)

    with caplog.at_level(logging.WARNING, logger="squadron.pipeline.squash"):
        with pytest.raises(SquashRefusedError, match="forked from inside the run"):
            _plan(temp_git_repo)

    assert head(temp_git_repo) == before


def test_message_bytes_that_are_not_utf8_survive_the_rewrite(temp_git_repo: Path) -> None:
    planning_run(temp_git_repo, 2)
    (temp_git_repo / FOREIGN_FILE).parent.mkdir(parents=True, exist_ok=True)
    (temp_git_repo / FOREIGN_FILE).write_text("latin\n")
    run_test_git(temp_git_repo, "add", "-A")
    subprocess.run(
        ["git", "-c", "i18n.commitEncoding=latin1", "commit", "-q", "-F", "-"],
        cwd=temp_git_repo,
        input=b"feat: caf\xe9\r\n",
        check=True,
    )
    raw_message = _raw_message(temp_git_repo, "HEAD")

    _squash(temp_git_repo)

    assert _raw_message(temp_git_repo, "HEAD") == raw_message


def _raw_message(repo: Path, rev: str) -> bytes:
    raw = subprocess.run(["git", "cat-file", "commit", rev], cwd=repo, capture_output=True, check=True)
    return raw.stdout.partition(b"\n\n")[2]
