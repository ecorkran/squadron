"""Input gathering for ``sq pr create`` (D7): commits, slice artifacts, review.

Every input here is either present or explicitly absent. A branch or an
artifact that cannot be resolved degrades to "absent" with a WARNING —
never fatal, because a PR should still open — except where the design
requires a refusal (base selection, preconditions), which live elsewhere.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from squadron.documents.frontmatter import read_frontmatter
from squadron.integrations.context_forge import ContextForgeError, ContextForgeNotAvailable
from squadron.pr.branch import parse_slice_branch
from squadron.pr.tasks import TaskItems, parse_task_items
from squadron.review.git_utils import (
    CommitRecord,
    GitRangeUnavailableError,
    commits_in_range,
    run_git,
)
from squadron.review.models import Verdict
from squadron.review.persistence import TASKS_DIR, CfClientProtocol, SliceInfo, resolve_slice_info
from squadron.review.reviews_dir import resolve_reviews_dir

_logger = logging.getLogger(__name__)


class EmptyCommitRangeError(Exception):
    """``base..head`` holds no commits, so there is nothing to open a PR for.

    A branch pushed at the base's own commit passes every precondition, so
    this is refused here — before any model call (D8) — rather than left to
    surface as an empty title and the host's own rejection.
    """


@dataclass(frozen=True)
class SliceInputs:
    """Slice artifacts gathered for a branch that names a slice, or None fields."""

    index: int | None
    design_file: str | None
    task_items: TaskItems | None


@dataclass(frozen=True)
class PrInputs:
    """Every input assembly needs, each present or explicitly absent."""

    commits: tuple[CommitRecord, ...]
    slice: SliceInputs


def gather_commits_and_slice(
    cf_client: CfClientProtocol,
    *,
    base: str,
    head: str,
    cwd: str,
) -> PrInputs:
    """Gather the commit range and, when ``head`` names a slice, its artifacts.

    A branch that does not match the slice convention yields no slice
    inputs and makes no ``cf`` call. A slice index ``cf`` cannot resolve, or
    a missing/unreadable task file, degrades to absent with a WARNING
    naming the condition — not fatal, because a PR should still open.

    Raises ``GitRangeUnavailableError`` when git cannot resolve the range in
    the local clone, and ``EmptyCommitRangeError`` when the range is empty.
    """
    commits = tuple(commits_in_range(base, head, cwd=cwd))
    if not commits:
        raise EmptyCommitRangeError(
            f"{head} has no commits that {base} lacks, so there is no pull request to open."
        )

    index = parse_slice_branch(head)
    if index is None:
        no_slice = SliceInputs(index=None, design_file=None, task_items=None)
        return PrInputs(commits=commits, slice=no_slice)

    try:
        info: SliceInfo = resolve_slice_info(cf_client, index)
    except (ValueError, ContextForgeNotAvailable, ContextForgeError) as exc:
        _logger.warning(
            "sq pr create: branch names slice %d, but cf could not resolve it (%s); "
            "describing commits only",
            index,
            exc,
        )
        unresolved = SliceInputs(index=index, design_file=None, task_items=None)
        return PrInputs(commits=commits, slice=unresolved)

    task_items = _read_task_items(info, cwd)
    return PrInputs(
        commits=commits,
        slice=SliceInputs(index=index, design_file=info["design_file"], task_items=task_items),
    )


@dataclass(frozen=True)
class ReviewProvenance:
    """The review whose reviewed sha lies in ``base..head``, if any (D7)."""

    path: Path
    verdict: Verdict
    reviewed_sha: str


def find_latest_in_range_review(
    *,
    base: str,
    head: str,
    cwd: str,
    host: str,
    owner: str,
    repository: str,
    reviews_dir_flag: str | None = None,
) -> ReviewProvenance | None:
    """Return the newest review whose reviewed sha lies in ``base..head``.

    Range **membership**, not ancestry of head — a review of a merged
    ancestor branch is an ancestor of head but not in the range, so it never
    qualifies. This is what keeps a neighboring slice's review off this PR.

    An artifact with no ``reviewedSha``, an unparseable sha, or a sha git
    does not recognize is skipped with a WARNING naming the file — not
    fatal, and not silent.
    """
    reviews_dir, _rule = resolve_reviews_dir(
        flag=reviews_dir_flag, cwd=cwd, host=host, owner=owner, repository=repository
    )
    if not reviews_dir.is_dir():
        return None

    in_range_shas = _shas_in_range(base, head, cwd=cwd)

    best: ReviewProvenance | None = None
    best_index = -1
    for path in sorted(reviews_dir.glob("*-review.*.md")):
        frontmatter = read_frontmatter(path)
        if frontmatter is None:
            _logger.warning("sq pr create: %s has no readable frontmatter; skipping", path.name)
            continue

        raw_sha = frontmatter.get("reviewedSha")
        if not isinstance(raw_sha, str) or not raw_sha.strip():
            _logger.warning("sq pr create: %s carries no reviewedSha; skipping", path.name)
            continue
        sha = raw_sha.strip()

        if sha not in in_range_shas:
            continue

        verdict = _parse_verdict(frontmatter.get("verdict"))

        index = in_range_shas.index(sha)
        if index > best_index:
            best_index = index
            best = ReviewProvenance(path=path, verdict=verdict, reviewed_sha=sha)

    return best


def _parse_verdict(raw: object) -> Verdict:
    """The frontmatter's own recorded verdict, or UNKNOWN when unreadable.

    Matches ``resolution_evidence.load_review``'s handling: the verdict is
    never re-derived, only read, so a garbled value degrades rather than
    raising and losing the whole review.
    """
    if not isinstance(raw, str):
        return Verdict.UNKNOWN
    try:
        return Verdict(raw.upper())
    except ValueError:
        return Verdict.UNKNOWN


def _shas_in_range(base: str, head: str, *, cwd: str) -> list[str]:
    """Full shas in ``base..head``, oldest first — index is recency rank.

    An unparseable or unrecognized sha in a review simply never appears
    here, which correctly excludes it without a separate check.

    Raises ``GitRangeUnavailableError`` when git cannot answer: an empty
    list there would let the body claim no review covers these commits.
    """
    result = run_git(["rev-list", "--reverse", f"{base}..{head}"], cwd=cwd)
    if result is None or result.returncode != 0:
        detail = result.stderr.strip() if result is not None else "git could not run"
        raise GitRangeUnavailableError(f"Cannot list shas in {base}..{head}: {detail}.")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _read_task_items(info: SliceInfo, cwd: str) -> TaskItems | None:
    """Read and parse the slice's first task file, or None when absent/unreadable."""
    if not info["task_files"]:
        return None
    path = Path(cwd) / TASKS_DIR / info["task_files"][0]
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        _logger.warning(
            "sq pr create: slice %d's task file %s could not be read; "
            "leaving the design file as the only 'why' input",
            info["index"],
            path,
        )
        return None
    return parse_task_items(text)
