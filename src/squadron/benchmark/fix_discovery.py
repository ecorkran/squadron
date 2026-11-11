"""Fix-candidate discovery from git history (slice 422 D1).

Every commit reachable from ``HEAD`` whose message closes an issue is a candidate or
carries exactly one discovery-stage rejection. A closing commit that adds no test is
still discovered: the yield report needs to show how much fix history has no tests.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from squadron.benchmark.build_errors import BuildHalted, halt
from squadron.codehost.errors import (
    AmbiguousHostRemoteError,
    ForeignRepositoryError,
    NoHostRemoteError,
)
from squadron.codehost.models import LocalRemote, RepositoryLocator
from squadron.codehost.protocol import CodeHost
from squadron.codehost.remotes import select_remote
from squadron.codehost.targets import PullRequestTarget, TargetForm
from squadron.core.process_runner import (
    ProcessNotFoundError,
    ProcessResult,
    ProcessRunner,
    ProcessTimedOutError,
)
from squadron.metrology.benchmark_models import CandidateRejection

_logger = logging.getLogger(__name__)

#: ASCII record and unit separators: they cannot occur in a commit message in practice,
#: so the log splits unambiguously whatever a message contains.
_RECORD_SEPARATOR = "\x1e"
_FIELD_SEPARATOR = "\x1f"
#: sha, parents, committer date (strict ISO 8601), full message. The message goes last
#: because it is free text.
GIT_LOG_FORMAT = "%x1e%H%x1f%P%x1f%cI%x1f%B"
_FIELD_COUNT = 4

#: A GitHub closing keyword, then ``#n`` or ``owner/repo#n``. Keyword and reference may be
#: separated by any whitespace or a colon. Defined once; a bare ``(#283)`` has no keyword
#: and so is not a reference.
CLOSING_REFERENCE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b[\s:]+(?:([\w.-]+/[\w.-]+))?#(\d+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FixCandidate:
    """A closing commit that reached the next stage.

    ``parent_sha`` is the first parent; a root commit is rejected in discovery.
    """

    sha: str
    parent_sha: str
    committer_date: datetime
    issue_ref: str
    repository: str | None
    number: int


@dataclass(frozen=True)
class DiscoveryRejection:
    """Why a closing commit is not a candidate.

    ``parent_sha`` (first parent, empty for a root commit) and ``issue_ref`` (the first
    reference as written) let the rejection be stored as a ``FixQualification``.
    """

    sha: str
    rejection: CandidateRejection
    detail: str
    parent_sha: str = ""
    issue_ref: str | None = None


@dataclass(frozen=True)
class DiscoveryResult:
    candidates: tuple[FixCandidate, ...]
    rejections: tuple[DiscoveryRejection, ...]


@dataclass(frozen=True)
class _ClosingCommit:
    sha: str
    parents: tuple[str, ...]
    committer_date: datetime
    #: Distinct references in first-written order: (as written, repository, number).
    references: tuple[tuple[str, str | None, int], ...]


def _run_git_log(runner: ProcessRunner, repo_root: Path, timeout_seconds: float) -> ProcessResult:
    argv = ["git", "log", f"--format={GIT_LOG_FORMAT}", "HEAD"]
    command = " ".join(argv)
    try:
        result = runner.run(argv, cwd=str(repo_root), timeout=timeout_seconds)
    except ProcessTimedOutError as exc:
        _logger.exception("%s timed out", command)
        raise BuildHalted(f"{command} exceeded {timeout_seconds}s in {repo_root}") from exc
    except ProcessNotFoundError as exc:
        _logger.exception("git is not available")
        raise BuildHalted(f"{command}: git is not on PATH") from exc
    if result.returncode != 0:
        raise halt(f"{command} exited {result.returncode} in {repo_root}: {result.stderr.strip()}")
    return result


def _references_in(message: str) -> tuple[tuple[str, str | None, int], ...]:
    """Distinct closing references, as written, in first-seen order."""
    seen: dict[tuple[str | None, int], str] = {}
    for match in CLOSING_REFERENCE.finditer(message):
        repository, number = match.group(1), int(match.group(2))
        as_written = f"{repository}#{number}" if repository else f"#{number}"
        seen.setdefault((repository, number), as_written)
    return tuple((written, key[0], key[1]) for key, written in seen.items())


def _parse_record(record: str) -> _ClosingCommit | None:
    fields = record.split(_FIELD_SEPARATOR, _FIELD_COUNT - 1)
    if len(fields) != _FIELD_COUNT:
        raise halt(f"git log record has {len(fields)} fields, expected {_FIELD_COUNT}: {record!r}")
    sha, parents, date_text = fields[0].strip(), fields[1].strip(), fields[2].strip()
    message = fields[3]
    references = _references_in(message)
    if not references:
        return None
    try:
        committer_date = datetime.fromisoformat(date_text)
    except ValueError as exc:
        _logger.exception("unparseable committer date for %s", sha)
        raise BuildHalted(
            f"git log gave an unparseable committer date for {sha}: {date_text!r}"
        ) from exc
    return _ClosingCommit(sha, tuple(parents.split()), committer_date, references)


def _closing_commits(stdout: str) -> list[_ClosingCommit]:
    commits = (_parse_record(record) for record in stdout.split(_RECORD_SEPARATOR) if record.strip())
    return [commit for commit in commits if commit is not None]


def _closers_by_issue(commits: Sequence[_ClosingCommit]) -> dict[tuple[str | None, int], int]:
    """How many closing commits name each issue, whatever each commit's own outcome."""
    counts: dict[tuple[str | None, int], int] = defaultdict(int)
    for commit in commits:
        for _, repository, number in commit.references:
            counts[(repository, number)] += 1
    return counts


def _rejection_for(
    commit: _ClosingCommit, closers: dict[tuple[str | None, int], int]
) -> DiscoveryRejection | None:
    """The one discovery rejection: root, merge, then several issues, then several closers."""
    if not commit.parents:
        return DiscoveryRejection(
            commit.sha,
            CandidateRejection.ROOT_COMMIT,
            "no parent commit to diff against",
            issue_ref=commit.references[0][0],
        )
    parent = commit.parents[0]
    if len(commit.parents) > 1:
        return DiscoveryRejection(
            commit.sha,
            CandidateRejection.MERGE_COMMIT,
            f"{len(commit.parents)} parents",
            parent,
            commit.references[0][0],
        )
    # A commit is only built with at least one reference, so != 1 means several.
    if len(commit.references) != 1:
        named = ", ".join(written for written, _, _ in commit.references)
        return DiscoveryRejection(
            commit.sha,
            CandidateRejection.MULTIPLE_ISSUES_CLOSED,
            named,
            parent,
            commit.references[0][0],
        )
    written, repository, number = commit.references[0]
    if closers[(repository, number)] > 1:
        return DiscoveryRejection(
            commit.sha,
            CandidateRejection.MULTIPLE_CLOSING_COMMITS,
            f"{written} is closed by {closers[(repository, number)]} commits",
            parent,
            written,
        )
    return None


def discover(runner: ProcessRunner, repo_root: Path, *, timeout_seconds: float) -> DiscoveryResult:
    """Candidates and rejections for every closing commit reachable from ``HEAD``.

    Raises ``BuildHalted`` (after an ERROR log) when ``git log`` cannot run or its output
    cannot be read: with no history there is nothing to report on.
    """
    commits = _closing_commits(_run_git_log(runner, repo_root, timeout_seconds).stdout)
    closers = _closers_by_issue(commits)
    candidates: list[FixCandidate] = []
    rejections: list[DiscoveryRejection] = []
    for commit in commits:
        rejection = _rejection_for(commit, closers)
        if rejection is not None:
            rejections.append(rejection)
            continue
        written, repository, number = commit.references[0]
        parent = commit.parents[0]  # a root commit was rejected above
        candidates.append(
            FixCandidate(commit.sha, parent, commit.committer_date, written, repository, number)
        )
    return DiscoveryResult(tuple(candidates), tuple(rejections))


def _issue_target(candidate: FixCandidate) -> PullRequestTarget:
    """The target form ``select_remote`` needs for the candidate's reference."""
    if candidate.repository is None:
        return PullRequestTarget(form=TargetForm.NUMBER, number=candidate.number)
    owner, _, repository = candidate.repository.partition("/")
    return PullRequestTarget(
        form=TargetForm.OWNER_REPO_NUMBER, owner=owner, repository=repository, number=candidate.number
    )


def resolve_locator(
    candidate: FixCandidate, remotes: Sequence[LocalRemote], host: CodeHost
) -> RepositoryLocator | DiscoveryRejection:
    """The repository holding the candidate's issue, or ``no_issue_host``.

    An ``owner/repo#n`` reference uses the host of the remote that points at that
    repository. A bare ``#n`` needs exactly one remote on a host ``host`` serves, the
    same rule ``select_remote`` applies to a bare pull-request target. Anything the
    selection cannot settle (no remote, several remotes, a host nobody serves) has no
    issue host; ``detail`` carries the selection's own message.
    """
    try:
        locator = select_remote(_issue_target(candidate), remotes, host.serves_host)
    except (ForeignRepositoryError, NoHostRemoteError, AmbiguousHostRemoteError) as exc:
        return DiscoveryRejection(candidate.sha, CandidateRejection.NO_ISSUE_HOST, str(exc))
    if not host.serves_host(locator.host):
        detail = (
            f"remote {locator.remote_name} is on {locator.host}, which the code host does not serve"
        )
        return DiscoveryRejection(candidate.sha, CandidateRejection.NO_ISSUE_HOST, detail)
    return locator
