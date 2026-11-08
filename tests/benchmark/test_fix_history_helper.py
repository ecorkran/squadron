"""The ``fix_history`` helper builds the two-commit repositories later tasks qualify."""

from __future__ import annotations

from pathlib import Path

from squadron.benchmark.diff_classify import ChangeStatus, parse_name_status
from squadron.benchmark.fix_discovery import discover
from squadron.core.process_runner import SubprocessRunner
from tests.benchmark.support import fix_history, hermetic_git


def test_two_commits_exist_with_the_base_as_parent(tmp_path: Path) -> None:
    history = fix_history("fixfair_project", "sort_sets", tmp_path)
    assert history.parent_sha != history.fix_sha
    assert hermetic_git(history.repo, "rev-parse", f"{history.fix_sha}^") == history.parent_sha
    assert hermetic_git(history.repo, "rev-list", "--count", "HEAD") == "2"


def test_the_diff_lists_exactly_the_scenarios_writes_and_removals(tmp_path: Path) -> None:
    history = fix_history("fixfair_project", "sort_sets", tmp_path)
    raw = hermetic_git(
        history.repo, "diff", "--name-status", "--no-renames", history.parent_sha, history.fix_sha
    )
    changes = {(change.status, change.path) for change in parse_name_status(raw)}
    assert changes == {
        (ChangeStatus.MODIFIED, "tests/conftest.py"),
        (ChangeStatus.MODIFIED, "tests/test_reach.py"),
        (ChangeStatus.ADDED, "tests/test_new_feature.py"),
        (ChangeStatus.DELETED, "tests/test_other.py"),
    }


def test_the_fix_commit_message_carries_a_closing_keyword(tmp_path: Path) -> None:
    history = fix_history("fixfair_project", "sort_sets", tmp_path)
    result = discover(SubprocessRunner(), history.repo, timeout_seconds=60.0)
    assert [candidate.sha for candidate in result.candidates] == [history.fix_sha]
    assert result.candidates[0].parent_sha == history.parent_sha
    assert result.candidates[0].number == 1


def test_the_base_commit_holds_the_whole_fixture_project(tmp_path: Path) -> None:
    history = fix_history("fixfair_project", "sort_sets", tmp_path)
    tracked = hermetic_git(
        history.repo, "ls-tree", "-r", "--name-only", history.parent_sha
    ).splitlines()
    assert {"pyproject.toml", "uv.lock", "src/fixpkg/__init__.py", "tests/test_other.py"} <= set(
        tracked
    )
