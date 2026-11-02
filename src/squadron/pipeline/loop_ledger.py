"""The commit ledger of a planning review loop (slice 202).

A ``commit_each_iteration`` loop claims every commit its own actions make, plus those of
the phase step just before it, so that on completion it can replace them with one commit.
The commits are not all the pipeline's: a dispatch agent commits its own work too. So the
ledger does not list shas. Each dispatch and commit result is stamped with the HEAD it
started from and the HEAD it left (``head_stamp``), and the ledger claims a result only
when its start is the ledger's tip. A gap means someone else committed, and the ledger
becomes unprovable. The ledger lives on ``StepResult`` and ``StepState`` so a pause
carries it across a resume.

This module must not import ``executor`` at module level: the executor imports it.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel

from squadron.pipeline.actions import ActionType
from squadron.pipeline.actions.commit import commit_target_from_params, commit_target_outputs
from squadron.pipeline.commit_plan import CommitSubject, CommitTarget
from squadron.pipeline.head_stamp import (
    HEAD_AFTER_KEY,
    HEAD_BEFORE_KEY,
    STAMPED_ACTION_TYPES,
    read_head,
)
from squadron.pipeline.models import ActionResult
from squadron.review.git_utils import run_git

_logger = logging.getLogger(__name__)


class LoopCommitLedger(BaseModel):
    """The commits a loop claimed: the sha before the first, the sha after the last, how many."""

    base_sha: str
    tip_sha: str
    commit_count: int = 0
    # True when the loop cannot prove the commits are its own; collapse then refuses.
    unprovable: bool = False


def start_ledger(
    *,
    commit_params: dict[str, object],
    prior_outputs: Mapping[str, ActionResult],
    cwd: str,
    resumed: bool,
    run_id: str,
    step_name: str,
    runs_dir: Path | None,
) -> LoopCommitLedger | None:
    """The ledger a loop invocation starts with: carried from run state, or freshly opened.

    A resumed invocation takes the ledger its paused run stored. One with no stored
    record, and every fresh invocation (an ``each`` item included), opens a new one. A
    code loop never has a ledger, so a resume cannot hand it an unprovable one.
    """
    if not _collapses(commit_params):
        return None
    if resumed:
        carried = _stored_ledger(run_id, step_name, runs_dir)
        if carried is not None:
            return carried
    return open_ledger(commit_params, prior_outputs, cwd)


def _stored_ledger(run_id: str, step_name: str, runs_dir: Path | None) -> LoopCommitLedger | None:
    # Imported here: state imports this module for the ledger type.
    from squadron.pipeline.state import StateManager

    try:
        return StateManager(runs_dir=runs_dir).loop_ledger_for(run_id, step_name)
    except FileNotFoundError:
        # No run state to carry from; the fresh ledger only claims commits made from now.
        _logger.warning("loop commits: no run state for %s; opening a fresh ledger", run_id)
        return None


def _loop_target(commit_params: dict[str, object]) -> CommitTarget:
    target = commit_target_from_params(commit_params, 0)
    if target is None:
        raise ValueError("loop commit params name no commit subject")
    return target


def _collapses(commit_params: dict[str, object]) -> bool:
    """Whether a loop with these round commit params ever collapses (code loops do not)."""
    return _loop_target(commit_params).subject is not CommitSubject.CODE


def open_ledger(
    commit_params: dict[str, object], prior_outputs: Mapping[str, ActionResult], cwd: str
) -> LoopCommitLedger | None:
    """A fresh ledger for a loop about to start, or ``None`` when it never collapses.

    ``commit_params`` is the loop's ``round_commit_params`` result. A code loop gets no
    ledger. The phase step's commit joins the ledger only when it is HEAD and covers the
    same document the loop's rounds commit; the dispatch agent's commits just before it
    join too, found by chaining the dispatch's stamps to the commit's.
    """
    target = _loop_target(commit_params)
    if target.subject is CommitSubject.CODE:
        return None

    start_head = read_head(cwd)
    if start_head is None:
        _logger.warning("loop commits: cannot read HEAD; the loop will not collapse its commits")
        return LoopCommitLedger(base_sha="", tip_sha="", unprovable=True)

    phase = _newest_commit_result(prior_outputs)
    if phase is None:
        return _empty_ledger(start_head)
    mismatch = _phase_mismatch(phase, start_head, target)
    if mismatch is not None:
        _logger.warning("loop commits: the phase commit is left out of the collapse: %s", mismatch)
        return _empty_ledger(start_head)

    phase_start = str(phase.metadata[HEAD_BEFORE_KEY])
    base = _agent_start(prior_outputs, phase_start) or phase_start
    count = _count_commits(base, start_head, cwd)
    if count is None:
        return LoopCommitLedger(base_sha=base, tip_sha=start_head, unprovable=True)
    return LoopCommitLedger(base_sha=base, tip_sha=start_head, commit_count=count)


def _empty_ledger(head: str) -> LoopCommitLedger:
    return LoopCommitLedger(base_sha=head, tip_sha=head)


def claim_actions(ledger: LoopCommitLedger, results: Sequence[ActionResult], cwd: str) -> None:
    """Claim the commits the stamped ``results`` made, oldest first; a gap makes it unprovable.

    Call once per action, in order: a result is claimed only when the HEAD it started
    from is the ledger's tip, so a commit landing between two actions (an operator's,
    say, during a pause) breaks the chain instead of being swallowed.
    """
    for result in results:
        if ledger.unprovable:
            return
        if result.action_type not in STAMPED_ACTION_TYPES:
            continue
        before = result.metadata.get(HEAD_BEFORE_KEY)
        after = result.metadata.get(HEAD_AFTER_KEY)
        if not isinstance(before, str) or not isinstance(after, str):
            _make_unprovable(ledger, f"a {result.action_type} action has no HEAD stamp")
            return
        if before != ledger.tip_sha:
            _make_unprovable(
                ledger,
                f"HEAD was {before} when a {result.action_type} action started, "
                f"not the loop's last commit {ledger.tip_sha}",
            )
            return
        count = _count_commits(before, after, cwd)
        if count is None:
            _make_unprovable(ledger, f"cannot count the commits from {before} to {after}")
            return
        ledger.commit_count += count
        ledger.tip_sha = after


def _make_unprovable(ledger: LoopCommitLedger, reason: str) -> None:
    _logger.warning("loop commits: %s; the loop will not collapse its commits", reason)
    ledger.unprovable = True


def _count_commits(before: str, after: str, cwd: str) -> int | None:
    """How many commits ``after`` has beyond ``before``, or ``None`` when git cannot say."""
    result = run_git(["rev-list", "--count", f"{before}..{after}"], cwd=cwd)
    if result is None or result.returncode != 0:
        return None
    return int(result.stdout.strip())


def _newest_commit_result(prior_outputs: Mapping[str, ActionResult]) -> ActionResult | None:
    """The newest commit action result that made a commit; ``prior_outputs`` is in run order."""
    for result in reversed(list(prior_outputs.values())):
        if result.action_type == ActionType.COMMIT and result.outputs.get("committed") is True:
            return result
    return None


def _phase_mismatch(phase: ActionResult, start_head: str, target: CommitTarget) -> str | None:
    """Why ``phase`` is not the loop's own phase commit, or ``None`` when it is."""
    sha = phase.outputs.get("sha")
    if sha != start_head:
        return f"its sha {sha} is not HEAD {start_head}"
    if not isinstance(phase.metadata.get(HEAD_BEFORE_KEY), str):
        return "it has no HEAD stamp, so the commits before it cannot be told apart"
    expected = commit_target_outputs(target)
    if any(phase.outputs.get(key) != value for key, value in expected.items()):
        return f"it covered a different document than {expected}"
    return None


def _agent_start(prior_outputs: Mapping[str, ActionResult], phase_start: str) -> str | None:
    """Where the phase's dispatch started, when it left HEAD at ``phase_start``.

    One hop only: a phase step has a single dispatch, and chaining further back would
    pull in the previous document's commits.
    """
    for result in reversed(list(prior_outputs.values())):
        if result.action_type == ActionType.DISPATCH and (
            result.metadata.get(HEAD_AFTER_KEY) == phase_start
        ):
            before = result.metadata.get(HEAD_BEFORE_KEY)
            return before if isinstance(before, str) else None
    return None
