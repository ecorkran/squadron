"""Tests for CommitAction with the ``fix`` subject (slice 423 D5, D6)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from squadron.pipeline.actions import ActionType
from squadron.pipeline.actions.commit import CommitAction
from squadron.pipeline.commit_plan import SUBJECT_PARAM, CommitSubject
from squadron.pipeline.failure_kind import FAILURE_KIND_KEY, FailureKind
from squadron.pipeline.fix_keys import (
    COMMIT_TO_KEY,
    ISSUE_NUMBER_KEY,
    START_BRANCH_KEY,
    START_HEAD_KEY,
    CommitTo,
)
from squadron.pipeline.models import ActionContext, ActionResult, local_output_key
from tests.conftest import run_test_git

STEP = "fix"
SUMMARY = "handle a missing template directory"


def _reply(**overrides: object) -> str:
    report: dict[str, object] = {
        "summary": SUMMARY,
        "failing_tests": ["tests/test_templates.py::test_missing_dir"],
        "failed_before_change": True,
        "gates": [{"command": "ruff check", "exit_code": 0}],
    }
    report.update(overrides)
    return json.dumps(report)


def _head(repo: Path) -> str:
    return run_test_git(repo, "rev-parse", "HEAD").strip()


def _context(
    repo: Path,
    reply: str,
    *,
    with_fix_context: bool = True,
    earlier: dict[str, ActionResult] | None = None,
) -> ActionContext:
    prior: dict[str, ActionResult] = dict(earlier or {})
    if with_fix_context:
        prior[local_output_key(ActionType.FIX_CONTEXT, 0)] = ActionResult(
            success=True,
            action_type=ActionType.FIX_CONTEXT,
            outputs={
                ISSUE_NUMBER_KEY: 301,
                COMMIT_TO_KEY: CommitTo.CURRENT.value,
                START_HEAD_KEY: _head(repo),
                START_BRANCH_KEY: "main",
            },
        )
    prior[local_output_key(ActionType.DISPATCH, 1)] = ActionResult(
        success=True, action_type=ActionType.DISPATCH, outputs={"response": reply}
    )
    return ActionContext(
        pipeline_name="fix",
        run_id="run-001",
        params={SUBJECT_PARAM: CommitSubject.FIX.value},
        step_name=STEP,
        step_index=0,
        prior_outputs=prior,
        resolver=MagicMock(),
        cf_client=MagicMock(),
        cwd=str(repo),
    )


async def test_fix_commit_lands_one_commit_with_the_report(temp_git_repo: Path) -> None:
    context = _context(temp_git_repo, _reply())
    (temp_git_repo / "README.md").write_text("changed\n")
    (temp_git_repo / "new_test.py").write_text("def test_x(): ...\n")
    before = run_test_git(temp_git_repo, "rev-list", "--count", "HEAD").strip()

    result = await CommitAction().execute(context)

    assert result.success, result.error
    assert result.outputs["committed"] is True
    assert result.outputs["sha"] == _head(temp_git_repo)
    assert run_test_git(temp_git_repo, "rev-list", "--count", "HEAD").strip() == str(int(before) + 1)
    assert run_test_git(temp_git_repo, "log", "-1", "--format=%B").strip() == (
        f"fix: {SUMMARY}\n\nFixes #301"
    )
    assert run_test_git(temp_git_repo, "status", "--porcelain") == ""
    assert result.metadata["fix_report"] == {
        "summary": SUMMARY,
        "failing_tests": ["tests/test_templates.py::test_missing_dir"],
        "failed_before_change": True,
        "gates": [{"command": "ruff check", "exit_code": 0}],
    }


async def test_report_defect_fails_with_kind_and_keeps_the_changes(temp_git_repo: Path) -> None:
    context = _context(temp_git_repo, _reply(gates=[]))
    (temp_git_repo / "README.md").write_text("changed\n")
    head = _head(temp_git_repo)

    result = await CommitAction().execute(context)

    assert not result.success
    assert result.metadata[FAILURE_KIND_KEY] == FailureKind.FIX_REPORT.value
    assert "gates" in (result.error or "")
    assert run_test_git(temp_git_repo, "status", "--porcelain").strip() == "M README.md"
    assert _head(temp_git_repo) == head


async def test_moved_head_fails_without_a_kind(temp_git_repo: Path) -> None:
    context = _context(temp_git_repo, _reply())
    run_test_git(temp_git_repo, "commit", "-q", "--allow-empty", "-m", "agent commit")
    (temp_git_repo / "README.md").write_text("changed\n")

    result = await CommitAction().execute(context)

    assert not result.success
    assert "HEAD moved" in (result.error or "")
    assert FAILURE_KIND_KEY not in result.metadata


async def test_blocked_report_fails_with_its_reason(temp_git_repo: Path) -> None:
    context = _context(temp_git_repo, json.dumps({"blocked": "needs a decision"}))

    result = await CommitAction().execute(context)

    assert not result.success
    assert result.error == "fix blocked: needs a decision"
    assert result.metadata[FAILURE_KIND_KEY] == FailureKind.FIX_REPORT.value


async def test_missing_fix_context_result_fails_by_name(temp_git_repo: Path) -> None:
    context = _context(temp_git_repo, _reply(), with_fix_context=False)

    result = await CommitAction().execute(context)

    assert not result.success
    assert ActionType.FIX_CONTEXT.value in (result.error or "")


def _decoys() -> dict[str, ActionResult]:
    """Results of earlier steps as the executor keys them: a finished step's under
    ``step:type-n``, an earlier inner step of a loop or ``each`` body under ``i-type-n``."""
    context_result = ActionResult(
        success=True,
        action_type=ActionType.FIX_CONTEXT,
        outputs={
            ISSUE_NUMBER_KEY: 999,
            COMMIT_TO_KEY: CommitTo.CURRENT.value,
            START_HEAD_KEY: "0" * 40,
            START_BRANCH_KEY: "decoy",
        },
    )
    reply = ActionResult(
        success=True,
        action_type=ActionType.DISPATCH,
        outputs={"response": json.dumps({"blocked": "an earlier step's reply"})},
    )
    return {
        "earlier:fix-context-0": context_result,
        "earlier:dispatch-1": reply,
        "0-fix-context-0": context_result,
        "0-dispatch-1": reply,
    }


async def test_results_of_earlier_container_steps_are_not_this_steps(temp_git_repo: Path) -> None:
    context = _context(temp_git_repo, _reply(), earlier=_decoys())
    (temp_git_repo / "README.md").write_text("changed\n")

    result = await CommitAction().execute(context)

    assert result.success, result.error
    assert run_test_git(temp_git_repo, "log", "-1", "--format=%B").strip() == (
        f"fix: {SUMMARY}\n\nFixes #301"
    )


async def test_an_earlier_steps_reply_is_not_used_when_this_step_has_none(
    temp_git_repo: Path,
) -> None:
    context = _context(temp_git_repo, _reply(), earlier=_decoys())
    del context.prior_outputs[local_output_key(ActionType.DISPATCH, 1)]

    result = await CommitAction().execute(context)

    assert not result.success
    assert ActionType.DISPATCH.value in (result.error or "")


async def test_agent_created_names_are_committed_literally_not_as_pathspecs(
    temp_git_repo: Path,
) -> None:
    context = _context(temp_git_repo, _reply())
    (temp_git_repo / "README.md").write_text("changed\n")
    (temp_git_repo / ":(exclude)notes.txt").write_text("pathspec magic in a file name\n")
    (temp_git_repo / "a[1].txt").write_text("a glob character in a file name\n")

    result = await CommitAction().execute(context)

    assert result.success, result.error
    assert run_test_git(temp_git_repo, "status", "--porcelain") == ""
    shown = run_test_git(temp_git_repo, "show", "--name-only", "-z", "--format=", "HEAD")
    assert sorted(name for name in shown.split("\0") if name) == [
        ":(exclude)notes.txt",
        "README.md",
        "a[1].txt",
    ]
