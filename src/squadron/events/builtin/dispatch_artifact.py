"""squadron.dispatch-artifact — POST_ACTION check that a phase-step dispatch
wrote its expected artifact this run.

Migrated from squadron.pipeline.executor (slice 909), unchanged in
behavior. The "dispatch post-condition" log prefix is asserted by existing
tests and must survive.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from squadron.events import EventType, register_event_action
from squadron.events.contexts import EventContext, PostActionContext
from squadron.pipeline.models import ActionResult, ValidationError
from squadron.pipeline.steps.phase import ArtifactKind
from squadron.review.persistence import TASKS_DIR, CfClientProtocol, resolve_slice_info

_logger = logging.getLogger(__name__)


def _expected_artifact_paths(
    kind: ArtifactKind, slice_index: int, cf_client: CfClientProtocol
) -> list[str]:
    """Resolve the expected artifact path(s) for a phase's artifact kind.

    Raises:
        ValueError, TypeError: If the slice cannot be resolved via CF —
            propagated to the caller, which treats it as "path unresolvable".
    """
    info = resolve_slice_info(cf_client, slice_index)
    if kind is ArtifactKind.DESIGN:
        return [info["design_file"]] if info["design_file"] else []
    return [str(TASKS_DIR / f) for f in info["task_files"]]


def _check_dispatch_artifact_written(
    *,
    kind: ArtifactKind,
    slice_index: int,
    cf_client: CfClientProtocol,
    cwd: str,
    run_started_at: datetime,
) -> str | None:
    """Verify a phase-step dispatch wrote its expected artifact this run.

    Returns None if the post-condition is satisfied, else an error message
    naming the failure mode. Every failure mode fails closed (returns a
    message) and is logged at WARNING — never a silent pass.
    """
    try:
        paths = _expected_artifact_paths(kind, slice_index, cf_client)
    except (ValueError, TypeError) as exc:
        msg = f"could not resolve expected {kind.value} artifact path for slice {slice_index}: {exc}"
        _logger.warning("dispatch post-condition: %s", msg)
        return msg

    if not paths:
        msg = f"no {kind.value} artifact path registered for slice {slice_index}"
        _logger.warning("dispatch post-condition: %s", msg)
        return msg

    base_dir = Path(cwd) if cwd else Path(".")
    for rel_path in paths:
        full_path = base_dir / rel_path
        try:
            if not full_path.exists():
                continue
            mtime = datetime.fromtimestamp(full_path.stat().st_mtime, tz=UTC)
            if mtime >= run_started_at:
                return None
        except OSError as exc:
            msg = f"could not verify {kind.value} artifact at {rel_path}: {exc}"
            _logger.warning("dispatch post-condition: %s", msg)
            return msg

    msg = (
        f"phase dispatch completed but no {kind.value} artifact was written "
        f"for slice {slice_index} (expected one of: {', '.join(paths)})"
    )
    _logger.warning("dispatch post-condition: %s", msg)
    return msg


def _dispatch_artifact_post_condition_error(
    *,
    kind: ArtifactKind,
    slice_param: object,
    cf_client: CfClientProtocol,
    cwd: str,
    run_started_at: datetime | None,
    run_state_error: str | None,
) -> str | None:
    """Resolve the dispatch artifact post-condition for one dispatch action.

    Returns None if satisfied, else the failure message. Every branch fails
    closed and is logged at WARNING (see docstrings on the helpers it calls).
    """
    if run_state_error is not None:
        return run_state_error
    if run_started_at is None:
        # Only reachable if a future caller sets expected_kind without also
        # resolving run_started_at/run_state_error — guards the invariant.
        msg = "run start time unavailable"
        _logger.warning("dispatch post-condition: %s", msg)
        return msg
    if slice_param is None:
        msg = f"could not resolve expected {kind.value} artifact path: no 'slice' param in scope"
        _logger.warning("dispatch post-condition: %s", msg)
        return msg
    try:
        slice_index = int(str(slice_param))
    except ValueError:
        msg = (
            f"could not resolve expected {kind.value} artifact path: "
            f"'slice' param {slice_param!r} is not a numeric index"
        )
        _logger.warning("dispatch post-condition: %s", msg)
        return msg
    return _check_dispatch_artifact_written(
        kind=kind,
        slice_index=slice_index,
        cf_client=cf_client,
        cwd=cwd,
        run_started_at=run_started_at,
    )


class DispatchArtifactAction:
    """POST_ACTION event action: fail a dispatch that wrote no artifact."""

    name = "squadron.dispatch-artifact"
    events = frozenset({EventType.POST_ACTION})

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        return []

    async def execute(self, context: EventContext) -> ActionResult:
        assert isinstance(context, PostActionContext)

        if (
            context.action_type != "dispatch"
            or not context.result.success
            or context.expected_artifact_kind is None
        ):
            return ActionResult(success=True, action_type=self.name, outputs={})

        error = _dispatch_artifact_post_condition_error(
            kind=context.expected_artifact_kind,
            slice_param=context.params.get("slice"),
            cf_client=context.cf_client,
            cwd=context.cwd,
            run_started_at=context.run_started_at,
            run_state_error=context.run_state_error,
        )
        if error is not None:
            return ActionResult(success=False, action_type=self.name, outputs={}, error=error)
        return ActionResult(success=True, action_type=self.name, outputs={})


register_event_action(DispatchArtifactAction())
