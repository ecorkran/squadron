"""What a fix commit stages and says (slice 423 D5, D6).

``fix_commit_plan`` is the one function behind both the SDK ``commit`` action and the
hidden ``sq _commit --subject fix``, so the two accept, refuse and word the message
the same way. It stages nothing itself: it returns a plan or a refusal.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from squadron.pipeline.actions import ActionType
from squadron.pipeline.actions.dispatch_io import RESPONSE_KEY
from squadron.pipeline.commit_plan import CommitPlan
from squadron.pipeline.failure_kind import FailureKind
from squadron.pipeline.fix_branch import branch_problem
from squadron.pipeline.fix_git import SUBPROCESS_GIT, FixGit
from squadron.pipeline.fix_keys import (
    COMMIT_TO_KEY,
    ISSUE_NUMBER_KEY,
    START_BRANCH_KEY,
    START_HEAD_KEY,
    CommitTo,
)
from squadron.pipeline.fix_report import FixReport, FixReportError, parse_fix_report
from squadron.pipeline.git_ops import (
    ConfigReader,
)
from squadron.pipeline.models import ActionContext, ActionResult, results_in_current_step

_logger = logging.getLogger(__name__)

# The longest subject line git tooling shows whole; a longer summary is kept and logged.
_SUBJECT_WIDTH = 72
_SHA_WIDTH = 12
NO_CHANGES_MESSAGE = "report claims a fix but the tree has no changes"


@dataclass(frozen=True)
class FixCommitRequest:
    """What the fix-context step recorded plus the agent's reply."""

    issue_number: int
    commit_to: CommitTo
    start_head: str
    start_branch: str
    reply_text: str


@dataclass(frozen=True)
class FixCommitRefusal:
    """The commit cannot be made; ``message`` names why."""

    message: str
    failure_kind: FailureKind | None = None


@dataclass(frozen=True)
class FixCommitPlan:
    """The checked report and the commit it produces."""

    plan: CommitPlan
    report: FixReport


def _refuse(message: str, kind: FailureKind | None = None) -> FixCommitRefusal:
    _logger.warning("fix commit refused: %s", message)
    return FixCommitRefusal(message, kind)


def _head_refusal(request: FixCommitRequest, head: str | None) -> str | None:
    if head == request.start_head:
        return None
    now = head[:_SHA_WIDTH] if head else "unknown"
    return (
        f"HEAD moved from {request.start_head[:_SHA_WIDTH]} to {now}: "
        "the agent must not commit; the pipeline makes the one fix commit"
    )


def fix_commit_plan(
    request: FixCommitRequest,
    cwd: str | Path,
    cf_client: ConfigReader,
    git: FixGit = SUBPROCESS_GIT,
) -> FixCommitPlan | FixCommitRefusal:
    """The fix commit for ``request``, or the refusal naming why there is none.

    Checks run in order: the report, the branch, HEAD, the tree. ``cf_client`` is read
    only under ``commit-to: target``; ``git`` supplies the branch, HEAD and changed paths.
    A ``GitEnvironmentError`` from reading the branch or the target propagates: an
    unreadable git state ends the run.
    """
    cwd_text = str(cwd)
    try:
        report = parse_fix_report(request.reply_text)
    except FixReportError as exc:
        return _refuse(str(exc), FailureKind.FIX_REPORT)
    branch = git.current_branch(cwd_text)  # a GitEnvironmentError ends the run
    problem = branch_problem(branch, request.commit_to, cf_client, start_branch=request.start_branch)
    if problem is not None:
        return _refuse(problem)
    if (problem := _head_refusal(request, git.head(cwd_text))) is not None:
        return _refuse(problem)
    paths = git.changed_paths(cwd_text)
    if isinstance(paths, str):
        return _refuse(f"cannot list the changed paths: {paths.strip()}")
    if not paths:
        return _refuse(NO_CHANGES_MESSAGE, FailureKind.FIX_REPORT)
    if len(report.summary) > _SUBJECT_WIDTH:
        _logger.warning(
            "fix summary is %d characters, over %d; kept as written",
            len(report.summary),
            _SUBJECT_WIDTH,
        )
    message = f"fix: {report.summary}\n\nFixes #{request.issue_number}"
    plan = CommitPlan(paths=tuple(paths), stage_all=False, message=message, left_out=())
    return FixCommitPlan(plan=plan, report=report)


def _last_result(results: list[ActionResult], action_type: ActionType) -> ActionResult | None:
    matching = [result for result in results if result.action_type == action_type]
    return matching[-1] if matching else None


def _request_from_results(results: list[ActionResult]) -> FixCommitRequest | str:
    """The request this step's prior results describe, or the refusal text naming the gap."""
    context_result = _last_result(results, ActionType.FIX_CONTEXT)
    if context_result is None:
        return f"no {ActionType.FIX_CONTEXT} result in this step; nothing records the fix start"
    dispatch_result = _last_result(results, ActionType.DISPATCH)
    if dispatch_result is None:
        return f"no {ActionType.DISPATCH} result in this step; there is no reply to read"
    outputs = context_result.outputs
    reply = dispatch_result.outputs.get(RESPONSE_KEY)
    if not isinstance(reply, str):
        return f"the {ActionType.DISPATCH} result has no '{RESPONSE_KEY}' text"
    try:
        issue_number = int(str(outputs[ISSUE_NUMBER_KEY]))
        commit_to = CommitTo(str(outputs[COMMIT_TO_KEY]))
        start_head = str(outputs[START_HEAD_KEY])
        start_branch = str(outputs[START_BRANCH_KEY])
    except KeyError as exc:
        return f"the {ActionType.FIX_CONTEXT} result lacks {exc}"
    except ValueError as exc:
        return f"the {ActionType.FIX_CONTEXT} result has an unusable value: {exc}"
    return FixCommitRequest(issue_number, commit_to, start_head, start_branch, reply)


def fix_plan_from_context(context: ActionContext) -> FixCommitPlan | FixCommitRefusal:
    """``fix_commit_plan`` for the request this step's earlier actions describe.

    The SDK ``commit`` action and ``sq _commit`` both come here; the latter builds the
    same prior outputs from its flags and report file.
    """
    request = _request_from_results(results_in_current_step(context.prior_outputs))
    if isinstance(request, str):
        return _refuse(request)
    return fix_commit_plan(request, context.cwd, context.cf_client)
