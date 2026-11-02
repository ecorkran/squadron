"""Collapse a planning loop's own commits into one (slice 202).

A ``commit_each_iteration`` loop leaves a commit per round. When it completes, the
commits in its ledger are replaced by a single commit of identical tree, but only after
every check here proves they are still the unpublished, unmixed tail of the target.
A failed proof leaves history exactly as it is; it never changes the loop's status.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from squadron.integrations.context_forge import ContextForgeError
from squadron.pipeline.actions.commit import commit_target_from_params
from squadron.pipeline.commit_message import ArtifactChange, StagedFacts, compose_message
from squadron.pipeline.commit_plan import CommitTargetError, staged_verdict, subject_paths
from squadron.pipeline.git_ops import GitEnvironmentError, GitStateUnknownError, SliceNotInPlanError
from squadron.pipeline.loop_ledger import LoopCommitLedger
from squadron.review.git_utils import run_git
from squadron.review.persistence import CfClientProtocol

_logger = logging.getLogger(__name__)

# Namespace of the backup refs; outside refs/heads and refs/tags, so a normal push and
# ``git branch``/``git tag`` never see them (D5).
BACKUP_REF_PREFIX = "refs/squadron/pre-collapse"
_SHORT_SHA_LENGTH = 7

GitRunner = Callable[..., subprocess.CompletedProcess[str] | None]

# ``git diff --name-status`` letter for a path the range added.
_ADDED = "A"


class CollapseOutcome(StrEnum):
    COLLAPSED = "collapsed"
    NOTHING_TO_COLLAPSE = "nothing_to_collapse"
    REFUSED = "refused"  # a proof check failed; history was left alone
    GIT_FAILED = "git_failed"  # a git command failed or timed out


@dataclass(frozen=True)
class CollapseResult:
    """What a collapse did: ``reason`` explains a refusal or failure, ``new_sha`` a success."""

    outcome: CollapseOutcome
    reason: str = ""
    new_sha: str | None = None
    message: str = ""  # the collapsed commit's message, when collapsed


class CollapseGitError(Exception):
    """A git read failed or timed out; the message carries the command text."""


def run_checked(args: list[str], cwd: str) -> str:
    """Stdout of ``git args``; raises ``CollapseGitError`` naming the command on any failure."""
    result = run_git(args, cwd=cwd)
    if result is None or result.returncode != 0:
        detail = (result.stderr.strip() if result is not None else "") or "timed out or could not run"
        raise CollapseGitError(f"git {' '.join(args)}: {detail}")
    return result.stdout


def check_collapse(ledger: LoopCommitLedger, target_branch: str, cwd: str) -> CollapseResult | None:
    """``None`` when the ledger's commits are proven collapsible, else the result to return.

    Checks run in order and the first failure wins (D3). An unprovable ledger is refused
    before the commit count is looked at, so a loop resumed from a state file that
    predates ledgers says why it did not collapse.
    """
    try:
        return _first_failure(ledger, target_branch, cwd)
    except CollapseGitError as exc:
        return CollapseResult(CollapseOutcome.GIT_FAILED, str(exc))


def _first_failure(ledger: LoopCommitLedger, target_branch: str, cwd: str) -> CollapseResult | None:
    if ledger.unprovable:
        return _refused("the loop cannot prove which commits are its own")
    if len(ledger.commits) < 2:
        return CollapseResult(CollapseOutcome.NOTHING_TO_COLLAPSE)

    branch = run_checked(["branch", "--show-current"], cwd).strip()
    if branch != target_branch:
        return _refused(f"on {branch or 'a detached HEAD'}, not the target {target_branch}")

    head = run_checked(["rev-parse", "HEAD"], cwd).strip()
    last = ledger.commits[-1]
    if head != last:
        return _refused(f"HEAD {head} is not the loop's last commit {last}")

    expected = list(reversed(ledger.commits))
    chain = run_checked(["rev-list", "--first-parent", f"{ledger.base_sha}..HEAD"], cwd).split()
    if chain != expected:
        return _refused(
            f"the commits from {ledger.base_sha} to HEAD are {chain}, not the loop's {expected}"
        )

    first = ledger.commits[0]
    remote_refs = run_checked(
        ["for-each-ref", "--contains", first, "--format=%(refname)", "refs/remotes"], cwd
    ).split()
    if remote_refs:
        return _refused(f"commit {first} is already on {remote_refs[0]}")
    return None


def _refused(reason: str) -> CollapseResult:
    return CollapseResult(CollapseOutcome.REFUSED, reason)


def collapse_message(
    ledger: LoopCommitLedger,
    commit_params: dict[str, object],
    cwd: str,
    cf_client: CfClientProtocol,
) -> str:
    """The one message for the collapsed commit (D4).

    Subject and scope come from the loop's own commit params, never from the commit
    messages being replaced. What the range did to the document (added or revised) and
    which review it carries come from git, as the commit action reads them.
    """
    target = commit_target_from_params(commit_params, 0)
    if target is None:
        raise ValueError("loop commit params name no commit subject")
    subject = subject_paths(target, Path(cwd), cf_client)
    changes = {
        path: status
        for path, status in _changed_paths(ledger.base_sha, cwd).items()
        if subject.contains(path)
    }
    artifact = next((path for path in subject.artifact_repo_paths() if path in changes), None)
    reviews = [c for c in subject.candidates if c.is_review and c.repo_path in changes]
    facts = StagedFacts(
        artifact=(
            None
            if artifact is None
            else ArtifactChange.ADD
            if changes[artifact] == _ADDED
            else ArtifactChange.REVISE
        ),
        review_staged=bool(reviews),
        review_verdict=staged_verdict([Path(cwd) / review.path for review in reviews]),
    )
    return compose_message(target, facts)


def _changed_paths(base_sha: str, cwd: str) -> dict[str, str]:
    """Each path changed between ``base_sha`` and HEAD, repo-relative, with its status letter."""
    output = run_checked(["diff", "--name-status", "-z", "--no-renames", base_sha, "HEAD"], cwd)
    tokens = output.split("\0")
    # Tokens alternate status, path; the trailing NUL leaves one empty token to drop.
    return dict(zip(tokens[1::2], tokens[0::2], strict=False))


def collapse_loop_commits(
    ledger: LoopCommitLedger,
    target_branch: str,
    commit_params: dict[str, object],
    step_name: str,
    cwd: str,
    cf_client: CfClientProtocol,
) -> CollapseResult:
    """Replace the ledger's commits with one, or leave history alone and say why.

    ``target_branch`` is the integration target and ``commit_params`` the loop's
    ``round_commit_params`` result. The outcome is logged once (INFO collapsed, WARNING
    refused or failed, nothing for nothing-to-collapse). Never raises for a refusal or a
    failed git command; only ``GitStateUnknownError`` (a timed-out ref write) propagates.
    """
    result = _collapse(ledger, target_branch, commit_params, step_name, cwd, cf_client)
    _log_outcome(result, len(ledger.commits), step_name)
    return result


def _collapse(
    ledger: LoopCommitLedger,
    target_branch: str,
    commit_params: dict[str, object],
    step_name: str,
    cwd: str,
    cf_client: CfClientProtocol,
) -> CollapseResult:
    refusal = check_collapse(ledger, target_branch, cwd)
    if refusal is not None:
        return refusal
    try:
        message = collapse_message(ledger, commit_params, cwd, cf_client)
    except CollapseGitError as exc:
        return CollapseResult(CollapseOutcome.GIT_FAILED, str(exc))
    except (
        CommitTargetError,
        SliceNotInPlanError,
        FileNotFoundError,
        ContextForgeError,
        GitEnvironmentError,
    ) as exc:
        # cf or the plan cannot name the document, so there is no message to write.
        # The loop's commits stay as they are, and the warning carries the reason.
        return _refused(f"cannot compose the collapse message: {exc}")
    return write_collapse(
        base_sha=ledger.base_sha,
        old_head=ledger.commits[-1],
        message=message,
        step_name=step_name,
        cwd=cwd,
    )


def write_collapse(
    *,
    base_sha: str,
    old_head: str,
    message: str,
    step_name: str,
    cwd: str,
    run: GitRunner = run_git,
) -> CollapseResult:
    """Write the collapsed commit, its backup ref, then move HEAD to it (D2, D5, D6).

    The new commit reuses ``old_head``'s tree, so the index and working tree are never
    touched. The final ``update-ref`` names ``old_head`` as the expected value, so if
    HEAD moved since the checks git refuses and nothing changes. A backup ref left
    behind by a refused swap points at the unchanged head and is harmless.

    Raises:
        GitStateUnknownError: an ``update-ref`` timed out; whether it landed is unknown.
    """
    created = run(["commit-tree", f"{old_head}^{{tree}}", "-p", base_sha, "-m", message], cwd=cwd)
    if created is None or created.returncode != 0:
        return _git_failed("git commit-tree", created)
    new_sha = created.stdout.strip()

    note = f"squadron: collapse loop {step_name}"
    saved = _update_ref(run, ["-m", note, f"{BACKUP_REF_PREFIX}/{new_sha}", old_head], cwd)
    if saved.returncode != 0:
        return _git_failed("git update-ref (backup ref)", saved)
    swapped = _update_ref(run, ["-m", note, "HEAD", new_sha, old_head], cwd)
    if swapped.returncode != 0:
        return _refused(f"HEAD moved after the checks, so nothing changed: {swapped.stderr.strip()}")
    return CollapseResult(CollapseOutcome.COLLAPSED, new_sha=new_sha, message=message)


def _update_ref(run: GitRunner, args: list[str], cwd: str) -> subprocess.CompletedProcess[str]:
    """Run ``git update-ref``; a timeout means nobody knows whether the write landed."""
    result = run(["update-ref", *args], cwd=cwd)
    if result is None:
        message = (
            f"git update-ref {' '.join(args)} timed out or could not run: "
            "the ref may be left in an unknown state"
        )
        _logger.error(message)
        raise GitStateUnknownError(message)
    return result


def _git_failed(label: str, result: subprocess.CompletedProcess[str] | None) -> CollapseResult:
    detail = (result.stderr.strip() if result is not None else "") or "timed out or could not run"
    return CollapseResult(CollapseOutcome.GIT_FAILED, f"{label}: {detail}")


def _log_outcome(result: CollapseResult, commit_count: int, step_name: str) -> None:
    match result.outcome:
        case CollapseOutcome.COLLAPSED:
            new_sha = result.new_sha or ""
            _logger.info(
                'loop %s: collapsed %d commits into %s "%s" (pre-collapse head: %s/%s)',
                step_name,
                commit_count,
                new_sha[:_SHORT_SHA_LENGTH],
                result.message,
                BACKUP_REF_PREFIX,
                new_sha,
            )
        case CollapseOutcome.REFUSED | CollapseOutcome.GIT_FAILED:
            _logger.warning(
                "loop %s: left %d commits uncollapsed: %s", step_name, commit_count, result.reason
            )
        case CollapseOutcome.NOTHING_TO_COLLAPSE:
            pass  # nothing was attempted, so there is nothing to report
