"""Tests for finding a squash run and refusing unsafe ones, on real repositories (slice 948 D1-D3)."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest

import squadron.pipeline.squash as squash_module
from squadron.pipeline.git_ops import GitEnvironmentError
from squadron.pipeline.squash import SquashKind, SquashRefusedError, plan_squash
from squadron.review.git_utils import run_git
from tests.conftest import run_test_git
from tests.pipeline.commit_fixtures import (
    ARCH_FILE,
    DESIGN_FILE,
    DESIGN_REVIEW,
    PLAN_FILE,
    TASKS_FILE,
    cf_client,
)
from tests.pipeline.squash_helpers import (
    DEVLOG,
    FOREIGN_FILE,
    assert_history_unchanged,
    commit_files,
    head,
    history,
    planning_run,
    squash_target,
)


def _plan(repo: Path, target_branch: str = "main", **target: object):  # type: ignore[no-untyped-def]
    return plan_squash(squash_target(**target), target_branch, repo, cf_client())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Run detection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("count", [2, 7])
def test_run_is_found_oldest_first_with_oldest_as_survivor(temp_git_repo: Path, count: int) -> None:
    before_run = head(temp_git_repo)
    shas = planning_run(temp_git_repo, count)
    before = history(temp_git_repo)

    plan = _plan(temp_git_repo)

    assert plan is not None
    assert [c.sha for c in plan.commits] == shas
    assert plan.commits[0].subject == "docs: planning round 1"
    assert plan.survivor == shas[0]
    assert plan.parent == before_run
    assert plan.tree == run_test_git(temp_git_repo, "rev-parse", "HEAD^{tree}").strip()
    assert plan.tag_exists is False
    assert_history_unchanged(temp_git_repo, before)


def test_run_of_one_is_nothing_to_squash(temp_git_repo: Path) -> None:
    planning_run(temp_git_repo, 1)
    before = history(temp_git_repo)

    assert _plan(temp_git_repo) is None
    assert_history_unchanged(temp_git_repo, before)


def test_foreign_commit_ends_the_run(temp_git_repo: Path) -> None:
    planning_run(temp_git_repo, 2)
    commit_files(temp_git_repo, "feat: code", FOREIGN_FILE)
    newer = planning_run(temp_git_repo, 3)
    before = history(temp_git_repo)

    plan = _plan(temp_git_repo)

    assert plan is not None
    assert [c.sha for c in plan.commits] == newer
    assert_history_unchanged(temp_git_repo, before)


def test_merge_commit_ends_the_run(temp_git_repo: Path) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "side")
    planning_run(temp_git_repo, 2)
    run_test_git(temp_git_repo, "checkout", "-q", "main")
    run_test_git(temp_git_repo, "merge", "-q", "--no-ff", "-m", "merge side", "side")
    newer = planning_run(temp_git_repo, 2)
    before = history(temp_git_repo)

    plan = _plan(temp_git_repo)

    assert plan is not None
    assert [c.sha for c in plan.commits] == newer
    assert_history_unchanged(temp_git_repo, before)


def test_commit_touching_two_artifacts_ends_the_run(temp_git_repo: Path) -> None:
    planning_run(temp_git_repo, 2)
    commit_files(temp_git_repo, "docs: both", DESIGN_FILE, TASKS_FILE)
    newer = planning_run(temp_git_repo, 2)
    before = history(temp_git_repo)

    plan = _plan(temp_git_repo)

    assert plan is not None
    assert [c.sha for c in plan.commits] == newer
    assert_history_unchanged(temp_git_repo, before)


def test_devlog_only_commits_stay_inside_but_are_trimmed_at_the_oldest_end(temp_git_repo: Path) -> None:
    commit_files(temp_git_repo, "docs: devlog a", DEVLOG)
    commit_files(temp_git_repo, "docs: devlog b", DEVLOG)
    first = commit_files(temp_git_repo, "docs: design", DESIGN_FILE)
    middle = commit_files(temp_git_repo, "docs: devlog c", DEVLOG)
    last = commit_files(temp_git_repo, "docs: revise design", DESIGN_FILE)
    before = history(temp_git_repo)

    plan = _plan(temp_git_repo)

    assert plan is not None
    assert [c.sha for c in plan.commits] == [first, middle, last]
    assert plan.survivor == first
    assert_history_unchanged(temp_git_repo, before)


def test_plan_only_commits_are_trimmed_at_both_ends(temp_git_repo: Path) -> None:
    """Plan-only commits belong to the slice's path set but not at either end of its run."""
    commit_files(temp_git_repo, "docs: plan round 1", PLAN_FILE)
    commit_files(temp_git_repo, "review: design review", DESIGN_REVIEW)
    first = commit_files(temp_git_repo, "docs: add design", DESIGN_FILE)
    middle = commit_files(temp_git_repo, "docs: plan amended by the review", PLAN_FILE)
    last = commit_files(temp_git_repo, "docs: revise design", DESIGN_FILE)
    commit_files(temp_git_repo, "docs: plan touch-up", PLAN_FILE)
    before = history(temp_git_repo)

    plan = _plan(temp_git_repo)

    assert plan is not None
    assert [c.sha for c in plan.commits] == [first, middle, last]
    assert plan.commits[0].subject == "docs: add design"
    assert_history_unchanged(temp_git_repo, before)


def test_design_review_response_that_amends_the_architecture_stays_in_the_run(
    temp_git_repo: Path,
) -> None:
    first = commit_files(temp_git_repo, "docs: add design", DESIGN_FILE)
    both = commit_files(temp_git_repo, "docs: address design review", DESIGN_FILE, ARCH_FILE)
    before = history(temp_git_repo)

    plan = _plan(temp_git_repo)

    assert plan is not None
    assert [c.sha for c in plan.commits] == [first, both]
    assert_history_unchanged(temp_git_repo, before)


def test_arch_run_keeps_slice_plan_edits_but_not_trailing_plan_commits(temp_git_repo: Path) -> None:
    first = commit_files(temp_git_repo, "docs: add architecture", ARCH_FILE)
    both = commit_files(temp_git_repo, "docs: address arch review", ARCH_FILE, PLAN_FILE)
    commit_files(temp_git_repo, "docs: add slice plan", PLAN_FILE)
    commit_files(temp_git_repo, "docs: revise slice plan", PLAN_FILE)

    arch = _plan(temp_git_repo, kind=SquashKind.ARCH, index=100)
    slice_plan = _plan(temp_git_repo, kind=SquashKind.PLAN, index=100)

    assert arch is not None and [c.sha for c in arch.commits] == [first, both]
    assert slice_plan is not None and [c.subject for c in slice_plan.commits] == [
        "docs: add slice plan",
        "docs: revise slice plan",
    ]


def test_arch_target_finds_its_run(temp_git_repo: Path) -> None:
    shas = planning_run(temp_git_repo, 3, artifact=ARCH_FILE)
    before = history(temp_git_repo)

    plan = _plan(temp_git_repo, kind=SquashKind.ARCH, index=100)

    assert plan is not None
    assert [c.sha for c in plan.commits] == shas
    assert plan.backup_tag.startswith("squash-backup/arch-100-")
    assert_history_unchanged(temp_git_repo, before)


def test_plan_target_finds_its_slice_plan_run(temp_git_repo: Path) -> None:
    commit_files(temp_git_repo, "docs: plan and design", PLAN_FILE, DESIGN_FILE)
    shas = planning_run(temp_git_repo, 3, artifact=PLAN_FILE)
    before = history(temp_git_repo)

    plan = _plan(temp_git_repo, kind=SquashKind.PLAN, index=100)

    assert plan is not None
    assert [c.sha for c in plan.commits] == shas
    assert plan.backup_tag.startswith("squash-backup/plan-100-")
    assert_history_unchanged(temp_git_repo, before)


def test_plan_without_a_slice_plan_file_raises(temp_git_repo: Path) -> None:
    with pytest.raises(FileNotFoundError, match="999-slices"):
        _plan(temp_git_repo, kind=SquashKind.PLAN, index=999)


# ---------------------------------------------------------------------------
# Refusals (D3)
# ---------------------------------------------------------------------------


def _assert_refused(repo: Path, caplog: pytest.LogCaptureFixture, match: str, **kwargs: object) -> None:
    before = history(repo)
    with caplog.at_level(logging.WARNING, logger="squadron.pipeline.squash"):
        with pytest.raises(SquashRefusedError, match=match):
            _plan(repo, **kwargs)
    assert any(r.levelno == logging.WARNING and match in r.getMessage() for r in caplog.records)
    assert_history_unchanged(repo, before)


def test_dirty_tree_refuses(temp_git_repo: Path, caplog: pytest.LogCaptureFixture) -> None:
    planning_run(temp_git_repo, 2)
    (temp_git_repo / "README.md").write_text("edited\n")
    _assert_refused(temp_git_repo, caplog, "not clean")


def test_wrong_branch_refuses(temp_git_repo: Path, caplog: pytest.LogCaptureFixture) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "elsewhere")
    planning_run(temp_git_repo, 2)
    _assert_refused(temp_git_repo, caplog, "not the target branch")


def test_run_reaching_the_root_commit_refuses(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    repo = tmp_path / "rootless"
    repo.mkdir()
    run_test_git(repo, "init", "-q", "-b", "main")
    planning_run(repo, 3)
    _assert_refused(repo, caplog, "root commit")


def test_pushed_commits_are_never_part_of_the_run(temp_git_repo: Path) -> None:
    shas = planning_run(temp_git_repo, 3)
    run_test_git(temp_git_repo, "update-ref", "refs/remotes/origin/main", shas[0])

    plan = _plan(temp_git_repo)

    assert plan is not None
    assert [c.sha for c in plan.commits] == shas[1:]
    assert plan.parent == shas[0]


def test_run_pushed_down_to_one_commit_is_nothing_to_squash(temp_git_repo: Path) -> None:
    shas = planning_run(temp_git_repo, 3)
    run_test_git(temp_git_repo, "update-ref", "refs/remotes/origin/main", shas[1])

    assert _plan(temp_git_repo) is None


def test_backup_tag_pointing_elsewhere_refuses(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    planning_run(temp_git_repo, 2)
    plan = _plan(temp_git_repo)
    assert plan is not None
    run_test_git(temp_git_repo, "tag", plan.backup_tag, plan.parent)
    _assert_refused(temp_git_repo, caplog, "already exists")


def test_backup_tag_at_head_is_reused(temp_git_repo: Path) -> None:
    planning_run(temp_git_repo, 2)
    first = _plan(temp_git_repo)
    assert first is not None
    run_test_git(temp_git_repo, "tag", first.backup_tag, "HEAD")

    again = _plan(temp_git_repo)

    assert again is not None
    assert again.tag_exists is True


def test_git_that_cannot_answer_raises_environment_error(
    temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    planning_run(temp_git_repo, 2)

    def time_out_tag_lookup(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
        if args[:3] == ["rev-parse", "-q", "--verify"]:
            return None
        return run_git(args, cwd=cwd)

    monkeypatch.setattr(squash_module, "run_git", time_out_tag_lookup)
    with pytest.raises(GitEnvironmentError, match="timed out or could not run"):
        _plan(temp_git_repo)
