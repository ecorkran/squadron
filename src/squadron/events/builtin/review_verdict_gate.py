"""squadron.review-verdict-gate — COMMIT action rejecting invalid review verdicts.

A review artifact's ``verdict:`` is what a pipeline gate reads and what a human
returns to. Nothing checked it against :class:`Verdict`, so slice 266 committed
two artifacts reading ``verdict: RESOLVED`` and the commit gate accepted them.
Downstream an unrecognized value degrades to ``UNKNOWN``, and
``CheckpointTrigger.ON_CONCERNS`` includes ``UNKNOWN`` — so an invalid verdict
trips a checkpoint indistinguishably from a real one (#77).

The allowed set is derived from the enum at runtime. A literal list here would
drift the first time a member is added.

Keyed on ``docType: review``, not on path: the reviews directory is a
convention, the docType is the document's own declaration. A file with no
frontmatter is not a review and is skipped. A file whose frontmatter is
present but unreadable is *not* passed — same posture the frontmatter gate
holds, that a gate which cannot determine validity must not pass.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

import yaml

from squadron.documents.frontmatter import split_document
from squadron.documents.schema import DocType
from squadron.events import EventType, register_event_action
from squadron.events.contexts import CommitContext, EventContext
from squadron.pipeline.models import ActionResult, ValidationError
from squadron.review.models import Verdict

_logger = logging.getLogger(__name__)

_UNREADABLE_TEMPLATE = "{path}: could not read frontmatter to check its verdict ({reason})"
_MISSING_VERDICT_TEMPLATE = (
    "{path}: docType is '{doctype}' but the document has no 'verdict' key — allowed values: {allowed}"
)
_INVALID_VERDICT_TEMPLATE = (
    "{path}: verdict {value!r} is not a review verdict — allowed values: {allowed}"
)


def _allowed_verdicts() -> str:
    """The allowed set, rendered from the enum so it cannot drift."""
    return ", ".join(member.value for member in Verdict)


class ReviewVerdictGateAction:
    """COMMIT event action: reject a commit staging a review whose verdict is
    missing or not a :class:`Verdict` member."""

    name = "squadron.review-verdict-gate"
    events = frozenset({EventType.COMMIT})

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        return []

    async def execute(self, context: EventContext) -> ActionResult:
        assert isinstance(context, CommitContext)

        violations: list[str] = []
        for staged in context.staged_paths:
            if not staged.endswith(".md"):
                continue
            violation = self._check(Path(context.cwd) / staged, staged)
            if violation is not None:
                violations.append(violation)

        if not violations:
            return ActionResult(success=True, action_type=self.name, outputs={})

        for violation in violations:
            _logger.warning("review-verdict-gate: %s", violation)
        return ActionResult(
            success=False, action_type=self.name, outputs={}, error="\n".join(violations)
        )

    def _check(self, path: Path, display: str) -> str | None:
        """Return a violation message for *path*, or ``None`` when it passes.

        A file that is not a review — no frontmatter block, or a docType other
        than ``review`` — passes by not applying.
        """
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            # A staged path we cannot open. Not necessarily a review, but we
            # cannot tell, and a gate that cannot determine validity must not
            # pass. Deleted-but-staged paths do not reach here: git stages the
            # deletion, and the reader is only asked for paths still present.
            return _UNREADABLE_TEMPLATE.format(path=display, reason=exc)

        split = split_document(text)
        if split is None:
            # No frontmatter block at all: not a review document.
            return None

        _, raw_block, _ = split
        try:
            loaded = yaml.safe_load(raw_block)
        except yaml.YAMLError as exc:
            return _UNREADABLE_TEMPLATE.format(path=display, reason=exc)
        if not isinstance(loaded, dict):
            return _UNREADABLE_TEMPLATE.format(
                path=display, reason="frontmatter did not parse to a mapping"
            )

        frontmatter: dict[str, object] = {
            str(key): value for key, value in cast("dict[object, object]", loaded).items()
        }
        if str(frontmatter.get("docType", "")) != DocType.REVIEW.value:
            return None

        allowed = _allowed_verdicts()
        if "verdict" not in frontmatter:
            return _MISSING_VERDICT_TEMPLATE.format(
                path=display, doctype=DocType.REVIEW.value, allowed=allowed
            )

        value = str(frontmatter["verdict"])
        if value not in {member.value for member in Verdict}:
            return _INVALID_VERDICT_TEMPLATE.format(path=display, value=value, allowed=allowed)
        return None


register_event_action(ReviewVerdictGateAction())
