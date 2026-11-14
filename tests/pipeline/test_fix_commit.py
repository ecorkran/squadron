"""Tests for the fix commit plan (slice 423 D5, D6), against a real temporary git repo."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import NoReturn
from unittest.mock import MagicMock

import pytest

from squadron.integrations.context_forge import ContextForgeError
from squadron.pipeline.failure_kind import FailureKind
from squadron.pipeline.fix_commit import (
    NO_CHANGES_MESSAGE,
    FixCommitPlan,
    FixCommitRefusal,
    FixCommitRequest,
    fix_commit_plan,
)
from squadron.pipeline.fix_git import SUBPROCESS_GIT, FixGit
from squadron.pipeline.fix_keys import CommitTo
from squadron.pipeline.git_ops import GitEnvironmentError
from tests.conftest import run_test_git
from tests.pipeline.fix_git_fake import FakeFixGit

SUMMARY = "handle a missing template directory"
ISSUE = 301


def _reply(**overrides: object) -> str:
    report: dict[str, object] = {
        "summary": SUMMARY,
        "failing_tests": ["tests/test_templates.py::test_missing_dir"],
        "failed_before_change": True,
        "gates": [{"command": "ruff check", "exit_code": 0}],
    }
    report.update(overrides)
    return f"Done.\n{json.dumps(report)}"


def _head(repo: Path) -> str:
    return run_test_git(repo, "rev-parse", "HEAD").strip()


def _cf(integration_branch: str = "") -> MagicMock:
    cf = MagicMock()
    cf.get_config.return_value = integration_branch
    return cf


def _request(
    repo: Path,
    *,
    commit_to: CommitTo = CommitTo.TARGET,
    reply: str | None = None,
    start_branch: str = "main",
    start_head: str | None = None,
) -> FixCommitRequest:
    return FixCommitRequest(
        issue_number=ISSUE,
        commit_to=commit_to,
        start_head=start_head or _head(repo),
        start_branch=start_branch,
        reply_text=_reply() if reply is None else reply,
    )


def _plan(
    repo: Path,
    request: FixCommitRequest,
    cf: MagicMock | None = None,
    git: FixGit | None = None,
) -> FixCommitPlan | FixCommitRefusal:
    return fix_commit_plan(
        request, repo, cf if cf is not None else _cf(), git if git is not None else SUBPROCESS_GIT
    )


def _edit(repo: Path) -> None:
    (repo / "README.md").write_text("changed\n")


def _expect_plan(result: FixCommitPlan | FixCommitRefusal) -> FixCommitPlan:
    assert isinstance(result, FixCommitPlan), result
    return result


def _expect_refusal(result: FixCommitPlan | FixCommitRefusal) -> FixCommitRefusal:
    assert isinstance(result, FixCommitRefusal), result
    return result


@pytest.mark.parametrize("commit_to", [CommitTo.TARGET, CommitTo.CURRENT])
def test_valid_report_gives_the_exact_message(temp_git_repo: Path, commit_to: CommitTo) -> None:
    _edit(temp_git_repo)
    result = _expect_plan(_plan(temp_git_repo, _request(temp_git_repo, commit_to=commit_to)))
    assert result.plan.message == f"fix: {SUMMARY}\n\nFixes #{ISSUE}"
    assert result.plan.paths == ("README.md",)
    assert result.plan.stage_all is False
    assert result.report.summary == SUMMARY


def test_target_refuses_a_branch_that_is_not_the_target(temp_git_repo: Path) -> None:
    _edit(temp_git_repo)
    refusal = _expect_refusal(
        _plan(temp_git_repo, _request(temp_git_repo), _cf(integration_branch="dev/erik"))
    )
    assert "dev/erik" in refusal.message
    assert "main" in refusal.message
    assert refusal.failure_kind is None


def test_target_accepts_the_configured_integration_branch(temp_git_repo: Path) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "dev/erik")
    _edit(temp_git_repo)
    request = _request(temp_git_repo, start_branch="dev/erik")
    _expect_plan(_plan(temp_git_repo, request, _cf(integration_branch="dev/erik")))


def test_current_refuses_a_branch_switched_at_the_same_commit(temp_git_repo: Path) -> None:
    request = _request(temp_git_repo, commit_to=CommitTo.CURRENT)
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "elsewhere")
    _edit(temp_git_repo)
    refusal = _expect_refusal(_plan(temp_git_repo, request))
    assert "'main'" in refusal.message
    assert "'elsewhere'" in refusal.message


def test_current_refuses_a_detached_head(temp_git_repo: Path) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "--detach")
    _edit(temp_git_repo)
    request = _request(temp_git_repo, commit_to=CommitTo.CURRENT)
    assert "detached" in _expect_refusal(_plan(temp_git_repo, request)).message


def test_current_never_touches_cf(temp_git_repo: Path) -> None:
    _edit(temp_git_repo)
    cf = MagicMock()
    cf.get_config.side_effect = AssertionError("cf was read under commit-to current")
    request = _request(temp_git_repo, commit_to=CommitTo.CURRENT)
    _expect_plan(_plan(temp_git_repo, request, cf))


def test_unreadable_branch_propagates(temp_git_repo: Path) -> None:
    def boom(cwd: str) -> str:
        raise GitEnvironmentError("cannot read the current branch: boom")

    _edit(temp_git_repo)
    with pytest.raises(GitEnvironmentError, match="boom"):
        _plan(temp_git_repo, _request(temp_git_repo), git=FakeFixGit(branch=boom))


def test_unreadable_target_propagates(temp_git_repo: Path) -> None:
    _edit(temp_git_repo)
    cf = MagicMock()
    cf.get_config.side_effect = ContextForgeError("cf is down")
    with pytest.raises(GitEnvironmentError, match="cf is down"):
        _plan(temp_git_repo, _request(temp_git_repo), cf)


def test_moved_head_is_refused_naming_both_shas(temp_git_repo: Path) -> None:
    request = _request(temp_git_repo)
    run_test_git(temp_git_repo, "commit", "-q", "--allow-empty", "-m", "agent commit")
    _edit(temp_git_repo)
    refusal = _expect_refusal(_plan(temp_git_repo, request))
    assert request.start_head[:12] in refusal.message
    assert _head(temp_git_repo)[:12] in refusal.message
    assert "must not commit" in refusal.message


def test_unreadable_head_is_refused_naming_unknown(
    temp_git_repo: Path,
) -> None:
    request = _request(temp_git_repo)
    _edit(temp_git_repo)

    def unreadable(cwd: str) -> None:
        return None

    refusal = _expect_refusal(_plan(temp_git_repo, request, git=FakeFixGit(head=unreadable)))
    assert "unknown" in refusal.message


def test_untracked_modified_deleted_and_renamed_paths_are_all_planned(
    temp_git_repo: Path,
) -> None:
    for name in ("gone.txt", "old.txt"):
        (temp_git_repo / name).write_text(f"{name}\n")
    run_test_git(temp_git_repo, "add", "gone.txt", "old.txt")
    run_test_git(temp_git_repo, "commit", "-q", "-m", "more files")
    request = _request(temp_git_repo)
    _edit(temp_git_repo)  # modified
    (temp_git_repo / "new.txt").write_text("new\n")  # untracked
    (temp_git_repo / "gone.txt").unlink()  # deleted
    run_test_git(temp_git_repo, "mv", "old.txt", "renamed.txt")  # renamed
    result = _expect_plan(_plan(temp_git_repo, request))
    assert set(result.plan.paths) == {
        "README.md",
        "new.txt",
        "gone.txt",
        "old.txt",
        "renamed.txt",
    }


def test_report_defect_refuses_before_any_git_read(temp_git_repo: Path) -> None:
    def unreachable(cwd: str) -> NoReturn:
        raise AssertionError("git was read after a report defect")

    git = FakeFixGit(branch=unreachable, head=unreachable, changed=unreachable)
    request = _request(temp_git_repo, reply=_reply(gates=[]))
    refusal = _expect_refusal(_plan(temp_git_repo, request, git=git))
    assert refusal.failure_kind is FailureKind.FIX_REPORT
    assert "gates" in refusal.message


def test_blocked_report_is_a_fix_report_refusal_with_the_reason(temp_git_repo: Path) -> None:
    request = _request(temp_git_repo, reply=json.dumps({"blocked": "needs a decision"}))
    refusal = _expect_refusal(_plan(temp_git_repo, request))
    assert refusal.message == "fix blocked: needs a decision"
    assert refusal.failure_kind is FailureKind.FIX_REPORT


def test_long_summary_is_kept_and_logged(temp_git_repo: Path, caplog: pytest.LogCaptureFixture) -> None:
    _edit(temp_git_repo)
    summary = "x" * 100
    request = _request(temp_git_repo, reply=_reply(summary=summary))
    with caplog.at_level(logging.WARNING):
        result = _expect_plan(_plan(temp_git_repo, request))
    assert result.plan.message == f"fix: {summary}\n\nFixes #{ISSUE}"
    assert any("100 characters" in record.getMessage() for record in caplog.records)


def test_clean_tree_is_refused_and_history_is_unchanged(temp_git_repo: Path) -> None:
    before = run_test_git(temp_git_repo, "log", "--format=%H")
    refusal = _expect_refusal(_plan(temp_git_repo, _request(temp_git_repo)))
    assert refusal.message == NO_CHANGES_MESSAGE
    assert refusal.failure_kind is FailureKind.FIX_REPORT
    assert run_test_git(temp_git_repo, "log", "--format=%H") == before


def test_only_an_ignored_file_changed_is_refused(temp_git_repo: Path) -> None:
    (temp_git_repo / ".gitignore").write_text("ignored.log\n")
    run_test_git(temp_git_repo, "add", ".gitignore")
    run_test_git(temp_git_repo, "commit", "-q", "-m", "ignore")
    request = _request(temp_git_repo)
    before = run_test_git(temp_git_repo, "log", "--format=%H")
    (temp_git_repo / "ignored.log").write_text("noise\n")
    refusal = _expect_refusal(_plan(temp_git_repo, request))
    assert refusal.message == NO_CHANGES_MESSAGE
    assert refusal.failure_kind is FailureKind.FIX_REPORT
    assert run_test_git(temp_git_repo, "log", "--format=%H") == before


def test_nothing_is_staged_by_the_function(temp_git_repo: Path) -> None:
    _edit(temp_git_repo)
    _expect_plan(_plan(temp_git_repo, _request(temp_git_repo)))
    assert run_test_git(temp_git_repo, "diff", "--cached", "--name-only") == ""


def test_unreadable_changed_paths_is_a_refusal_naming_the_git_error(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def unreadable(cwd: str) -> str:
        return "fatal: unable to read the index\n"

    git = FakeFixGit(changed=unreadable)
    with caplog.at_level(logging.WARNING):
        refusal = _expect_refusal(_plan(temp_git_repo, _request(temp_git_repo), git=git))
    assert refusal.message == "cannot list the changed paths: fatal: unable to read the index"
    assert refusal.failure_kind is None
    assert any("unable to read the index" in record.getMessage() for record in caplog.records)
