"""squadron.usage-stamp — POST_ACTION action that folds a phase dispatch's usage record
into the frontmatter of the artifact it wrote (slice 178).

Never fails a run (178 D1/D6, as ``revision-stamp``): a cost stamp must not fail a
converging loop, so every resolution, parse or write failure is logged at WARNING and
the action returns success. It never alters ``result`` and never reads ``result.outputs``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from squadron.core.usage import UsageRecord
from squadron.documents.frontmatter import FrontmatterError, read_frontmatter, update_frontmatter
from squadron.events import EventType, register_event_action
from squadron.events.builtin.artifact_paths import dispatch_artifact_paths
from squadron.events.contexts import EventContext, PostActionContext
from squadron.integrations.context_forge import ContextForgeError
from squadron.pipeline.models import ActionResult, ValidationError
from squadron.providers.base import USAGE_KEY
from squadron.review.artifact_usage import (
    USAGE_ROUNDS_KEY,
    artifact_usage_fields,
    fold,
    read_artifact_usage,
)

_logger = logging.getLogger(__name__)


def _usage_record(context: PostActionContext) -> UsageRecord | None:
    """The dispatch's ``UsageRecord`` from result metadata, or None (logged) when unusable."""
    raw = context.result.metadata.get(USAGE_KEY)
    if raw is None:
        _logger.debug("usage stamp: step %s recorded no usage; nothing to stamp", context.step_name)
        return None
    try:
        if not isinstance(raw, Mapping):
            raise ValueError(f"usage is not a mapping: {raw!r:.200}")
        return UsageRecord.from_dict(cast("Mapping[str, object]", raw))
    except ValueError as exc:
        # A malformed record is reported and skipped; a cost stamp never fails the run.
        _logger.warning(
            "usage stamp: step %s has an unreadable usage record: %s", context.step_name, exc
        )
        return None


def _stamp_target(context: PostActionContext) -> Path | None:
    """The one existing artifact this dispatch wrote, or None (logged) when not exactly one."""
    kind = context.expected_artifact_kind
    assert kind is not None  # eligibility guarantees it
    slice_param = context.params.get("slice")
    plan_param = context.params.get("plan")
    try:
        paths = dispatch_artifact_paths(kind, slice_param, plan_param, context.cf_client, context.cwd)
    except (ContextForgeError, ValueError, TypeError, FileNotFoundError) as exc:
        # Resolution failed (cf error, no arch doc, non-numeric param): no stamp, run unaffected.
        _logger.warning(
            "usage stamp: could not resolve %s artifact path (slice=%s plan=%s): %s",
            kind.value,
            slice_param,
            plan_param,
            exc,
        )
        return None
    base_dir = Path(context.cwd) if context.cwd else Path(".")
    existing = [base_dir / rel for rel in paths if (base_dir / rel).exists()]
    if len(existing) > 1:
        _logger.warning(
            "usage stamp: %d %s candidates exist, none stamped: %s",
            len(existing),
            kind.value,
            ", ".join(str(p) for p in existing),
        )
    return existing[0] if len(existing) == 1 else None


def _stamp(path: Path, record: UsageRecord, iteration: int) -> None:
    """Read the prior total from ``path``, fold ``record`` into it and write it back."""
    front = read_frontmatter(path)
    if front is None:
        raise FrontmatterError(f"No readable YAML frontmatter in {path}")
    prior = read_artifact_usage(path, front)
    if prior is None and iteration >= 1 and USAGE_ROUNDS_KEY not in front:
        _logger.warning(
            "usage stamp: no prior usage keys on revision round %d of %s; "
            "total restarts and undercounts",
            iteration,
            path,
        )
    fields = artifact_usage_fields(fold(prior, record))
    update_frontmatter(path, fields, today=datetime.now(UTC).strftime("%Y%m%d"))


class UsageStampAction:
    """POST_ACTION event action: stamp a dispatch's cost onto the artifact it wrote."""

    name = "squadron.usage-stamp"
    events = frozenset({EventType.POST_ACTION})

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        return []

    async def execute(self, context: EventContext) -> ActionResult:
        assert isinstance(context, PostActionContext)
        done = ActionResult(success=True, action_type=self.name, outputs={})
        if (
            context.action_type != "dispatch"
            or not context.result.success
            or context.expected_artifact_kind is None
        ):
            return done
        record = _usage_record(context)
        if record is None:
            return done
        path = _stamp_target(context)
        if path is None:
            return done
        try:
            _stamp(path, record, context.iteration)
        except (FrontmatterError, OSError) as exc:
            # Unparseable frontmatter or a failed write: no stamp, run unaffected.
            _logger.warning("usage stamp failed for %s: %s: %s", path, type(exc).__name__, exc)
        return done


register_event_action(UsageStampAction())
