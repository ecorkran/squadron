"""Commit messages composed from what was staged (slice 196 D2, #164).

Internal step names (``phase-4``, ``loop-2``) never appear: a message says what
the commit contains, in the repo's semantic-prefix style.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from squadron.pipeline.commit_plan import CommitSubject, CommitTarget


class ArtifactChange(StrEnum):
    """How the phase artifact changed, from its ``git status`` entry."""

    ADD = "add"  # untracked or added
    REVISE = "revise"  # modified


@dataclass(frozen=True)
class StagedFacts:
    """What the staged set contains; the only input a message depends on."""

    artifact: ArtifactChange | None  # None when the artifact itself is not staged
    review_staged: bool
    review_verdict: str | None  # the review file's frontmatter ``verdict``, as written


# What each subject's artifact is called in a message.
_NOUN_BY_SUBJECT: dict[CommitSubject, str] = {
    CommitSubject.DESIGN: "design",
    CommitSubject.TASKS: "tasks",
    CommitSubject.ARCHITECTURE: "architecture",
}


def compose_message(target: CommitTarget, facts: StagedFacts) -> str:
    """The commit message for ``target`` given what was staged."""
    match target.subject:
        case CommitSubject.DEVLOG:
            suffix = f" for slice {target.slice_index}" if target.slice_index is not None else ""
            return f"docs: add DEVLOG entry{suffix}"
        case CommitSubject.CODE:
            return f"feat: implement slice {target.slice_index}{_review_clause(facts)}"
        case _:
            return _planning_message(target, facts)


def _review_clause(facts: StagedFacts, *, label: bool = True) -> str:
    """`` (review: V)`` when a review file is staged and its verdict is known.

    A review-only commit already says "review" in its prefix, so it passes
    ``label=False`` and gets a bare `` (V)``.
    """
    if not facts.review_staged or facts.review_verdict is None:
        return ""
    return f" (review: {facts.review_verdict})" if label else f" ({facts.review_verdict})"


def _scope(target: CommitTarget) -> str:
    """``slice 105`` or ``initiative 180``."""
    if target.slice_index is not None:
        return f"slice {target.slice_index}"
    return f"initiative {target.plan}"


def _planning_message(target: CommitTarget, facts: StagedFacts) -> str:
    noun = _NOUN_BY_SUBJECT[target.subject]
    scope = _scope(target)
    clause = _review_clause(facts)
    bare_clause = _review_clause(facts, label=False)
    round_suffix = f", round {target.round}" if target.round >= 1 else ""

    if facts.artifact is ArtifactChange.ADD:
        return f"docs: add {scope} {noun}{clause}"
    if facts.artifact is ArtifactChange.REVISE:
        # An initiative's architecture reads "revise initiative 180 architecture".
        return f"docs: revise {scope} {noun}{round_suffix}{clause}"
    if facts.review_staged:
        if target.round >= 1:
            return f"review: re-review {scope} {noun}{round_suffix}{bare_clause}"
        return f"review: add {scope} {noun} review{bare_clause}"
    # Only supporting files (the slice plan, DEVLOG) changed.
    return f"docs: update {scope} {noun} files"
