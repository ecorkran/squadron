"""The commit ledger of a planning review loop (slice 202).

A ``commit_each_iteration`` loop records the shas of the commits it makes, plus the
phase commit made just before it, so that on completion it can replace exactly those
commits with one. The ledger lives on ``StepResult`` and ``StepState`` so a pause
carries it across a resume.

This module must not import ``executor`` at module level: the executor imports it.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from pydantic import BaseModel, Field

from squadron.pipeline.actions import ActionType
from squadron.pipeline.actions.commit import (
    UNKNOWN_SHA,
    commit_target_from_params,
    commit_target_outputs,
)
from squadron.pipeline.commit_plan import CommitSubject, CommitTarget
from squadron.pipeline.models import ActionResult
from squadron.review.git_utils import run_git

_logger = logging.getLogger(__name__)


class LoopCommitLedger(BaseModel):
    """The commits a loop made, oldest first, and the sha they sit on."""

    base_sha: str
    commits: list[str] = Field(default_factory=lambda: [])
    # True when the loop cannot prove which commits are its own; collapse then refuses.
    unprovable: bool = False


def open_ledger(
    commit_params: dict[str, object], prior_outputs: Mapping[str, ActionResult], cwd: str
) -> LoopCommitLedger | None:
    """A fresh ledger for a loop about to start, or ``None`` when it never collapses.

    ``commit_params`` is the loop's ``round_commit_params`` result. A code loop gets no
    ledger. The phase commit just before the loop joins the ledger only when it is
    HEAD and covers the same document the loop's rounds commit.
    """
    target = commit_target_from_params(commit_params, 0)
    if target is None:
        raise ValueError("loop commit params name no commit subject")
    if target.subject is CommitSubject.CODE:
        return None

    start_head = _rev_parse("HEAD", cwd)
    if start_head is None:
        _logger.warning("loop commits: cannot read HEAD; the loop will not collapse its commits")
        return LoopCommitLedger(base_sha="", unprovable=True)

    phase = _newest_commit_result(prior_outputs)
    if phase is None:
        return LoopCommitLedger(base_sha=start_head)
    mismatch = _phase_mismatch(phase, start_head, target)
    if mismatch is not None:
        _logger.warning("loop commits: the phase commit is left out of the collapse: %s", mismatch)
        return LoopCommitLedger(base_sha=start_head)

    parent = _rev_parse(f"{start_head}^", cwd)
    if parent is None:
        # A root commit has no parent to rewrite onto.
        _logger.warning("loop commits: the phase commit %s has no parent; no collapse", start_head)
        return LoopCommitLedger(base_sha=start_head, unprovable=True)
    return LoopCommitLedger(base_sha=parent, commits=[start_head])


def record_round_commit(ledger: LoopCommitLedger, commit_result: ActionResult) -> None:
    """Add a round's commit to ``ledger``; a commit whose sha is unknown makes it unprovable.

    A round that committed nothing, or whose commit failed, changes nothing: the
    failed round's loop status is the executor's business, not the ledger's.
    """
    if not commit_result.success or commit_result.outputs.get("committed") is not True:
        return
    sha = commit_result.outputs.get("sha")
    if not isinstance(sha, str) or sha in ("", UNKNOWN_SHA):
        _logger.warning("loop commits: a round commit's sha is unknown; the loop will not collapse")
        ledger.unprovable = True
        return
    ledger.commits.append(sha)


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
    expected = commit_target_outputs(target)
    if any(phase.outputs.get(key) != value for key, value in expected.items()):
        return f"it covered a different document than {expected}"
    return None


def _rev_parse(ref: str, cwd: str) -> str | None:
    """The sha ``ref`` names, or ``None`` when git cannot say."""
    result = run_git(["rev-parse", "--verify", ref], cwd=cwd)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip()
