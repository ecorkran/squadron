"""What a pipeline commit stages and says (slice 196 D1, D2).

One builder serves both executors: ``CommitAction`` (SDK) and the hidden
``sq _commit`` command (prompt-only) call the same function, so their results
cannot drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CommitSubject(StrEnum):
    """What a commit is about; it decides the candidate paths and the message."""

    DESIGN = "design"
    TASKS = "tasks"
    ARCHITECTURE = "architecture"
    CODE = "code"
    DEVLOG = "devlog"


class UnmappedTemplateError(ValueError):
    """A review template has no commit subject, so a loop round's scope is unknown."""


# The one template -> subject definition. A loop round takes its subject from its
# last review action's template; the executor and the prompt renderer both use it.
_SUBJECT_BY_TEMPLATE: dict[str, CommitSubject] = {
    "slice": CommitSubject.DESIGN,
    "tasks": CommitSubject.TASKS,
    "code": CommitSubject.CODE,
    "arch": CommitSubject.ARCHITECTURE,
}


def subject_for_template(template: str) -> CommitSubject:
    """The commit subject a review ``template`` implies; raises when it has none."""
    try:
        return _SUBJECT_BY_TEMPLATE[template]
    except KeyError:
        known = ", ".join(sorted(_SUBJECT_BY_TEMPLATE))
        raise UnmappedTemplateError(
            f"commit scope unknown: review template {template!r} has no commit subject (known: {known})"
        ) from None


@dataclass(frozen=True)
class CommitTarget:
    """The work a commit covers."""

    subject: CommitSubject
    slice_index: int | None  # None means initiative-scoped (plan)
    plan: str | None
    review_template: str | None
    round: int  # 0 for the step's own commit, n for loop round n


@dataclass(frozen=True)
class CommitPlan:
    """What to stage and the message to commit with."""

    paths: tuple[str, ...]  # empty means nothing to commit
    stage_all: bool  # CODE only (D3)
    message: str
    left_out: tuple[str, ...]  # dirty paths not staged, named in a WARNING
