"""Tests for squashing a run buried under later commits, on real repositories (#271)."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest

from squadron.pipeline.squash import (
    NothingToSquash,
    SquashKind,
    SquashPlan,
    SquashRefusedError,
    apply_squash,
    plan_squash,
)
from tests.conftest import run_test_git
from tests.pipeline.commit_fixtures import DESIGN_FILE, PLAN_FILE, TASKS_FILE, cf_client
from tests.pipeline.squash_helpers import (
    DEVLOG,
    FOREIGN_FILE,
    commit_files,
    head,
    planning_run,
    squash_target,
)


def _plan(repo: Path, kind: SquashKind = SquashKind.SLICE) -> SquashPlan | None:
    return plan_squash(squash_target(kind), "main", repo, cf_client())


def _squash(repo: Path, kind: SquashKind = SquashKind.SLICE) -> str:
    plan = _plan(repo, kind)
    assert isinstance(plan, SquashPlan)
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
    assert isinstance(plan, SquashPlan) and plan.later == 2

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
    assert isinstance(_plan(temp_git_repo, SquashKind.TASKS), NothingToSquash)
    assert isinstance(_plan(temp_git_repo, SquashKind.SLICE), NothingToSquash)


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


# ---------------------------------------------------------------------------
# #276: the run is the newest stretch with two commits, not the newest stretch
# ---------------------------------------------------------------------------


def test_old_run_is_found_past_a_newer_one_commit_stretch(temp_git_repo: Path) -> None:
    shas = planning_run(temp_git_repo, 3)
    commit_files(temp_git_repo, "feat: code", FOREIGN_FILE)
    commit_files(temp_git_repo, "docs: devlog entry", DEVLOG)
    commit_files(temp_git_repo, "docs: check off tasks", DESIGN_FILE)

    plan = _plan(temp_git_repo)

    assert isinstance(plan, SquashPlan)
    assert [c.sha for c in plan.commits] == shas
    assert plan.later == 3


def test_mixed_bookkeeping_commit_above_the_run_does_not_hide_it(temp_git_repo: Path) -> None:
    shas = planning_run(temp_git_repo, 3)
    commit_files(temp_git_repo, "docs: mark slice complete", DESIGN_FILE, PLAN_FILE, FOREIGN_FILE)

    plan = _plan(temp_git_repo)

    assert isinstance(plan, SquashPlan)
    assert [c.sha for c in plan.commits] == shas


def test_nothing_to_squash_names_the_commit_that_cut_the_stretch(temp_git_repo: Path) -> None:
    commit_files(temp_git_repo, "docs: planning round 1", DESIGN_FILE)
    cutter = commit_files(temp_git_repo, "docs: mark other slice complete", DESIGN_FILE, FOREIGN_FILE)
    commit_files(temp_git_repo, "docs: planning round 2", DESIGN_FILE)

    plan = _plan(temp_git_repo)

    assert isinstance(plan, NothingToSquash)
    assert cutter[:8] in plan.reason
    assert FOREIGN_FILE in plan.reason
    assert "1 commit" in plan.reason


def test_nothing_to_squash_without_any_artifact_commit_says_so(temp_git_repo: Path) -> None:
    commit_files(temp_git_repo, "feat: code", FOREIGN_FILE)

    plan = _plan(temp_git_repo)

    assert isinstance(plan, NothingToSquash)
    assert "no unpushed commit touches" in plan.reason
