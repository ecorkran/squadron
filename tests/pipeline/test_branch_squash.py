"""Tests for squashing a slice branch into one commit before it merges."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.pipeline.branch_squash import squash_slice_branch
from tests.conftest import run_test_git

SLICE = 105
NAME = "Batch Foo"
BRANCH = "105-slice.batch-foo"


def _commit_file(repo: Path, name: str) -> None:
    (repo / name).write_text(f"{name}\n")
    run_test_git(repo, "add", name)
    run_test_git(repo, "commit", "-q", "-m", f"add {name}")


def _count(repo: Path, rev_range: str) -> int:
    return int(run_test_git(repo, "rev-list", "--count", rev_range).strip())


def _squash(repo: Path) -> int:
    return squash_slice_branch(SLICE, NAME, BRANCH, "main", str(repo))


@pytest.fixture
def branch_repo(temp_git_repo: Path) -> Path:
    """On the slice branch with three commits of its own."""
    run_test_git(temp_git_repo, "checkout", "-q", "-b", BRANCH)
    for name in ("one.py", "two.py", "three.py"):
        _commit_file(temp_git_repo, name)
    return temp_git_repo


def test_several_commits_become_one_with_the_same_tree(branch_repo: Path) -> None:
    tree = run_test_git(branch_repo, "rev-parse", "HEAD^{tree}")

    assert _squash(branch_repo) == 3

    assert _count(branch_repo, "main..HEAD") == 1
    assert run_test_git(branch_repo, "rev-parse", "HEAD^{tree}") == tree
    assert run_test_git(branch_repo, "rev-parse", "HEAD^") == run_test_git(
        branch_repo, "rev-parse", "main"
    )
    subject = run_test_git(branch_repo, "log", "-1", "--format=%s").strip()
    assert subject == "feat: implement slice 105 — Batch Foo"
    assert run_test_git(branch_repo, "status", "--porcelain").strip() == ""


def test_a_single_commit_is_left_alone(temp_git_repo: Path) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", BRANCH)
    _commit_file(temp_git_repo, "only.py")
    head = run_test_git(temp_git_repo, "rev-parse", "HEAD")

    assert _squash(temp_git_repo) == 0
    assert run_test_git(temp_git_repo, "rev-parse", "HEAD") == head


def test_a_branch_with_no_commits_is_left_alone(temp_git_repo: Path) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", BRANCH)

    assert _squash(temp_git_repo) == 0


def test_a_catch_up_merge_of_the_target_is_not_part_of_the_squash(branch_repo: Path) -> None:
    run_test_git(branch_repo, "checkout", "-q", "main")
    _commit_file(branch_repo, "from_main.py")
    run_test_git(branch_repo, "checkout", "-q", BRANCH)
    run_test_git(branch_repo, "merge", "-q", "--no-ff", "-m", "merge: main", "main")
    _commit_file(branch_repo, "four.py")

    assert _squash(branch_repo) == 5  # three commits, the catch-up merge, one more

    changed = run_test_git(branch_repo, "diff", "--name-only", "main", "HEAD").split()
    assert sorted(changed) == ["four.py", "one.py", "three.py", "two.py"]
    assert (branch_repo / "from_main.py").exists()


def test_pushed_commits_are_not_rewritten_and_the_skip_is_logged(
    branch_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    run_test_git(branch_repo, "update-ref", f"refs/remotes/origin/{BRANCH}", "HEAD~1")
    head = run_test_git(branch_repo, "rev-parse", "HEAD")

    with caplog.at_level(logging.WARNING):
        assert _squash(branch_repo) == 0

    assert run_test_git(branch_repo, "rev-parse", "HEAD") == head
    assert "not squashed" in caplog.text
