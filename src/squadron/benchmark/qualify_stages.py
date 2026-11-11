"""The pre-sandbox qualification stages (slice 422 D1, D2, D3, D13).

Stage 1 resolves the issue repository, fetches the issue and freezes its text. Stage 2
classifies the fix commit's diff from git alone. Nothing here builds a sandbox. A candidate
either gets a rejection record here or goes on to ``deps.sandbox_stages``.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace

from squadron.benchmark.build_errors import BuildHalted
from squadron.benchmark.diff_classify import (
    DiffClassification,
    DiffRejection,
    classify_diff,
    parse_name_status,
)
from squadron.benchmark.fairness import HarnessFailure
from squadron.benchmark.fix_discovery import (
    DiscoveryRejection,
    FixCandidate,
    resolve_locator,
)
from squadron.benchmark.issue_freeze import FrozenIssue, freeze_issue
from squadron.benchmark.qualify_types import QualifyDeps, QualifyResult, record_outcome
from squadron.codehost.errors import (
    CodeHostError,
    GitHubCliMissingError,
    IssueNotFoundError,
    ReferenceIsPullRequestError,
)
from squadron.codehost.models import LocalRemote, RepositoryLocator
from squadron.codehost.remotes import parse_remote_url
from squadron.core.process_runner import (
    ProcessNotFoundError,
    ProcessResult,
    ProcessTimedOutError,
)
from squadron.metrology.benchmark_models import CandidateRejection, QualificationOutcome

_logger = logging.getLogger(__name__)


class GitCommandFailed(Exception):
    """A git command in the user's checkout timed out, was not found, or exited non-zero."""


def run_git(deps: QualifyDeps, argv: Sequence[str]) -> ProcessResult:
    """Run ``git`` in the checkout; anything but a clean exit raises ``GitCommandFailed``."""
    command = " ".join(argv)
    try:
        result = deps.runner.run(list(argv), cwd=str(deps.repo_root), timeout=deps.git_timeout_seconds)
    except (ProcessTimedOutError, ProcessNotFoundError) as exc:
        raise GitCommandFailed(f"{command}: {exc}") from exc
    if result.returncode != 0:
        raise GitCommandFailed(f"{command} exited {result.returncode}: {result.stderr.strip()}")
    return result


def _remotes(deps: QualifyDeps) -> list[LocalRemote]:
    """The checkout's remotes; unlike ``list_remotes`` a failing git command is not 'no remotes'."""
    names = run_git(deps, ["git", "remote"]).stdout.split()
    return [
        parse_remote_url(name, run_git(deps, ["git", "remote", "get-url", name]).stdout.strip())
        for name in names
    ]


def _path_exists_at(deps: QualifyDeps, sha: str, path: str) -> bool:
    """Whether ``path`` exists in the tree at ``sha`` (``ls-tree`` answers with empty output)."""
    return bool(run_git(deps, ["git", "ls-tree", "--name-only", sha, "--", path]).stdout.strip())


def _read_text_at_or_none(deps: QualifyDeps, sha: str, path: str) -> str | None:
    """File text at ``sha``, ``None`` when the path is absent there."""
    if not _path_exists_at(deps, sha, path):
        return None
    return run_git(deps, ["git", "show", f"{sha}:{path}"]).stdout


@dataclass(frozen=True)
class _Rejected:
    rejection: CandidateRejection
    detail: str
    issue_ref: str | None = None


def _locate_and_freeze(deps: QualifyDeps, candidate: FixCandidate) -> tuple[str, str] | _Rejected:
    """``(normalized issue ref, frozen task text)``, or why the candidate stops here."""
    located = resolve_locator(candidate, _remotes(deps), deps.host)
    if isinstance(located, DiscoveryRejection):
        return _Rejected(located.rejection, located.detail)
    return _fetch_and_freeze(deps, candidate, located)


def _fetch_and_freeze(
    deps: QualifyDeps, candidate: FixCandidate, locator: RepositoryLocator
) -> tuple[str, str] | _Rejected:
    issue_ref = f"{locator.owner}/{locator.repository}#{candidate.number}"
    try:
        snapshot = deps.host.get_issue(locator, candidate.number)
    except IssueNotFoundError as exc:
        return _Rejected(CandidateRejection.ISSUE_NOT_FOUND, str(exc), issue_ref)
    except ReferenceIsPullRequestError as exc:
        return _Rejected(CandidateRejection.REFERENCE_IS_PULL_REQUEST, str(exc), issue_ref)
    frozen = freeze_issue(snapshot, candidate.committer_date)
    if isinstance(frozen, FrozenIssue):
        return issue_ref, frozen.task_text
    return _Rejected(frozen, f"{issue_ref} was edited after the fix commit", issue_ref)


def _classify(deps: QualifyDeps, candidate: FixCandidate) -> DiffClassification | _Rejected:
    """Stage 2: the parent's project config file, then the diff, classified."""
    config_name = deps.adapter.project_config_name
    parent_pyproject = _read_text_at_or_none(deps, candidate.parent_sha, config_name)
    if parent_pyproject is None:
        return _Rejected(
            CandidateRejection.NO_FIX_CASE_ADAPTER, f"no {config_name} at the parent commit"
        )
    diff = run_git(
        deps,
        ["git", "diff", "--name-status", "--no-renames", f"{candidate.parent_sha}..{candidate.sha}"],
    )
    classified = classify_diff(
        parse_name_status(diff.stdout),
        deps.adapter,
        parent_pyproject,
        lambda path: _read_text_at_or_none(deps, candidate.parent_sha, path),
        lambda path: _read_text_at_or_none(deps, candidate.sha, path),
    )
    if isinstance(classified, DiffRejection):
        return _Rejected(classified.rejection, classified.detail)
    return classified


def _rejected(
    deps: QualifyDeps, candidate: FixCandidate, why: _Rejected, issue_ref: str | None
) -> QualifyResult:
    return record_outcome(
        deps,
        candidate,
        QualificationOutcome.REJECTED,
        issue_ref=why.issue_ref or issue_ref,
        rejection=why.rejection,
        detail=why.detail,
    )


def _harness_error(
    deps: QualifyDeps, candidate: FixCandidate, detail: str, issue_ref: str | None
) -> QualifyResult:
    return record_outcome(
        deps, candidate, QualificationOutcome.HARNESS_ERROR, issue_ref=issue_ref, detail=detail
    )


def run_pre_sandbox_stages(deps: QualifyDeps, candidate: FixCandidate) -> QualifyResult:
    """Stages 1 and 2, then ``deps.sandbox_stages`` for a candidate that survived both.

    Every outcome is stored. A ``CodeHostError`` other than not-found, a failing git command
    and a project config the adapter cannot parse are ``harness_error`` records (never a
    rejection that blames the case); a missing ``gh`` halts the build because every later
    candidate would fail the same way.
    """
    issue_ref: str | None = None
    try:
        first = _locate_and_freeze(deps, candidate)
        if isinstance(first, _Rejected):
            return _rejected(deps, candidate, first, None)
        issue_ref, task_text = first
        second = _classify(deps, candidate)
        if isinstance(second, _Rejected):
            return _rejected(deps, candidate, second, issue_ref)
    except GitHubCliMissingError as exc:
        _logger.exception("gh is missing; the build cannot continue")
        raise BuildHalted(f"gh is not available: {exc}") from exc
    except CodeHostError as exc:
        _logger.exception("code host failure qualifying %s", candidate.sha[:12])
        return _harness_error(deps, candidate, f"{type(exc).__name__}: {exc}", issue_ref)
    except GitCommandFailed as exc:
        _logger.exception("git failure qualifying %s", candidate.sha[:12])
        return _harness_error(deps, candidate, str(exc), issue_ref)
    except HarnessFailure as exc:
        _logger.exception("classification failed for %s", candidate.sha[:12])
        return _harness_error(deps, candidate, exc.detail, issue_ref)
    # The sandbox stages record the resolved reference, not the spelling in the commit message.
    return deps.sandbox_stages(replace(candidate, issue_ref=issue_ref), second, task_text, deps)
