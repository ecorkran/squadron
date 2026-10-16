"""Per-round review verdicts, read from committed artifact versions (slice 176 D6).

Every review round is committed (941), so the rounds of a slice's review type are the
committed versions of ``{index}-review.{type}.*.md``, at top level and in ``archive/``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from squadron.documents.frontmatter import parse_frontmatter
from squadron.pipeline.loop_config import LoopCondition
from squadron.review.persistence import ARCHIVE_SUBDIR, REVIEWS_DIR
from squadron.stats.git_history import (
    STATUS_DELETED,
    Commit,
    GitHistory,
    ReviewRound,
    path_matches,
)

_logger = logging.getLogger(__name__)

#: The author date of slice 941's branch tip, when ``commit_each_iteration: true`` became
#: required on review-revise loops. A review whose earliest round predates it may have had
#: rounds that were never committed, so its round count is a lower bound.
COMMIT_EACH_ITERATION_SINCE = datetime.fromisoformat("2026-10-13T12:28:49-06:00")


@dataclass(frozen=True)
class ReviewRoundsRead:
    """The rounds of one review type, plus what could not be read."""

    rounds: tuple[ReviewRound, ...]
    skipped: int  # versions whose `git show` failed or whose frontmatter did not parse
    lower_bound: bool  # the earliest round predates COMMIT_EACH_ITERATION_SINCE


@dataclass(frozen=True)
class _Version:
    commit: Commit
    path: str


def review_rounds(history: GitHistory, index: int, review_type: str) -> ReviewRoundsRead:
    """Read slice ``index``'s ``review_type`` rounds: one `git show` per distinct version."""
    rounds: list[ReviewRound] = []
    skipped = 0
    for version in _distinct_versions(history, index, review_type):
        round_ = _read_round(history, version, review_type)
        if round_ is None:
            skipped += 1
        else:
            rounds.append(round_)
    rounds.sort(key=lambda r: r.authored_at)
    lower_bound = bool(rounds) and rounds[0].authored_at < COMMIT_EACH_ITERATION_SINCE
    return ReviewRoundsRead(rounds=tuple(rounds), skipped=skipped, lower_bound=lower_bound)


def rounds_to_accept(rounds: tuple[ReviewRound, ...]) -> int | None:
    """Rounds up to and including the first the review loop would accept; ``None`` if none."""
    for position, round_ in enumerate(rounds, start=1):
        if round_.verdict is not None and LoopCondition.REVIEW_CONCERNS_OR_BETTER.met_by_verdict(
            round_.verdict
        ):
            return position
    return None


def _distinct_versions(history: GitHistory, index: int, review_type: str) -> list[_Version]:
    """Each distinct file version once, from the earliest commit that carried its blob."""
    name = f"{index}-review.{review_type}.*.md"
    patterns = [f"{REVIEWS_DIR}/{name}", f"{REVIEWS_DIR}/{ARCHIVE_SUBDIR}/{name}"]
    seen: set[str] = set()
    versions: list[_Version] = []
    for commit in reversed(_touching(history, patterns)):  # oldest first
        for change in commit.changes:
            if change.status == STATUS_DELETED or change.blob_id in seen:
                continue
            if any(path_matches(change.path, pattern) for pattern in patterns):
                seen.add(change.blob_id)
                versions.append(_Version(commit=commit, path=change.path))
    return versions


def _touching(history: GitHistory, patterns: list[str]) -> list[Commit]:
    found: dict[str, Commit] = {}
    for pattern in patterns:
        for commit in history.commits_touching(pattern):
            found[commit.sha] = commit
    return sorted(found.values(), key=lambda c: c.authored_at, reverse=True)


def _read_round(history: GitHistory, version: _Version, review_type: str) -> ReviewRound | None:
    text = history.show(version.commit.sha, version.path)
    if text is None:
        return None  # GitHistory.show logged the WARNING
    front = parse_frontmatter(text)
    if front is None:
        _logger.warning(
            "unreadable frontmatter in %s at %s; skipping this review round",
            version.path,
            version.commit.sha,
        )
        return None
    return ReviewRound(
        review_type=review_type,
        sha=version.commit.sha,
        authored_at=version.commit.authored_at,
        verdict=_text(front.get("verdict")),
        model=_text(front.get("aiModel")),
        run_id=_text(front.get("runId")),
    )


def _text(value: object) -> str | None:
    return None if value is None else str(value)
