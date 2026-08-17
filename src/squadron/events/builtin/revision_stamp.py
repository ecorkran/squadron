"""squadron.revision-stamp — POST_ACTION action that stamps a monotonic
``revision_number`` onto an artifact a loop-iteration dispatch just wrote.

Migrated from squadron.pipeline.executor (slice 911), unchanged in
behavior. Never fails (design D4): a failed evidence stamp must not fail a
converging loop, so every parse/write failure is logged at WARNING and
swallowed — this is 911's own tested contract, not a runner clamp.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from squadron.documents.frontmatter import FrontmatterError, read_frontmatter, update_frontmatter
from squadron.events import EventType, register_event_action
from squadron.events.builtin.artifact_paths import expected_artifact_paths
from squadron.events.contexts import EventContext, PostActionContext
from squadron.pipeline.models import ActionResult, ValidationError
from squadron.pipeline.steps.phase import ArtifactKind
from squadron.review.persistence import CfClientProtocol

_logger = logging.getLogger(__name__)


def _stamp_revision_number(
    *,
    kind: ArtifactKind,
    slice_param: object,
    cf_client: CfClientProtocol,
    cwd: str,
) -> None:
    """Stamp a monotonic ``revision_number`` onto each artifact this dispatch
    just wrote, called only after the artifact post-condition has passed.

    Value rule: absent or non-int prior value -> 1; present int n -> n + 1.
    It counts squadron stamps, not the loop iteration. A failed evidence
    stamp must not fail a converging loop, so any parse/write failure is
    logged at WARNING (naming the path and reason) and swallowed.
    """
    if slice_param is None:
        return
    try:
        slice_index = int(str(slice_param))
    except ValueError:
        return
    try:
        paths = expected_artifact_paths(kind, slice_index, cf_client)
    except Exception as exc:  # noqa: BLE001
        # cf_client is duck-typed (CfClientProtocol); any implementation can
        # raise its own error type here, not just ValueError/TypeError. The
        # contract above is unconditional — every resolution failure must be
        # swallowed and logged, not just the two types the built-in CF client
        # happens to raise.
        _logger.warning(
            "revision_number stamp: could not resolve %s artifact path for slice %s: %s",
            kind.value,
            slice_index,
            exc,
            exc_info=True,
        )
        return

    if not paths:
        _logger.warning(
            "revision_number stamp: no %s artifact path registered for slice %s",
            kind.value,
            slice_index,
        )
        return

    base_dir = Path(cwd) if cwd else Path(".")
    for rel_path in paths:
        full_path = base_dir / rel_path
        try:
            existing = read_frontmatter(full_path)
            prior = existing.get("revision_number") if existing is not None else None
            next_value = prior + 1 if isinstance(prior, int) else 1
            today = datetime.now(UTC).strftime("%Y%m%d")
            update_frontmatter(full_path, {"revision_number": next_value}, today=today)
        except (FrontmatterError, OSError) as exc:
            _logger.warning("revision_number stamp failed for %s: %s", full_path, exc)


class RevisionStampAction:
    """POST_ACTION event action: stamp revision_number after a loop dispatch."""

    name = "squadron.revision-stamp"
    events = frozenset({EventType.POST_ACTION})

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        return []

    async def execute(self, context: EventContext) -> ActionResult:
        assert isinstance(context, PostActionContext)

        kind = context.expected_artifact_kind
        eligible = (
            context.action_type == "dispatch"
            and context.result.success
            and kind is not None
            and context.iteration >= 1
        )
        if eligible and kind is not None:
            _stamp_revision_number(
                kind=kind,
                slice_param=context.params.get("slice"),
                cf_client=context.cf_client,
                cwd=context.cwd,
            )
        return ActionResult(success=True, action_type=self.name, outputs={})


register_event_action(RevisionStampAction())
