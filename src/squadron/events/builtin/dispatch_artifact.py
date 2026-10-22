"""squadron.dispatch-artifact — POST_ACTION check that a phase-step dispatch
wrote its expected artifact this run.

Migrated from squadron.pipeline.executor (slice 909), unchanged in
behavior. The "dispatch post-condition" log prefix is asserted by existing
tests and must survive.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from squadron.events import EventType, register_event_action
from squadron.events.builtin.artifact_paths import dispatch_artifact_paths, dispatch_scope
from squadron.events.contexts import EventContext, PostActionContext
from squadron.integrations.context_forge import ContextForgeError
from squadron.pipeline.actions import ActionType
from squadron.pipeline.actions.dispatch import SKIPPED_KEY
from squadron.pipeline.commit_plan import PLAN_PARAM, SLICE_PARAM
from squadron.pipeline.failure_kind import AGENT_QUESTION_KEY, FAILURE_KIND_KEY, FailureKind
from squadron.pipeline.models import ActionResult, ValidationError
from squadron.pipeline.steps.phase import ArtifactKind
from squadron.pipeline.text_tail import tail_text
from squadron.review.persistence import CfClientProtocol

_logger = logging.getLogger(__name__)


def _resolve_paths(kind: ArtifactKind, scope: str, resolve: Callable[[], list[str]]) -> list[str] | str:
    """Run *resolve*; the paths, or a failure message (logged at WARNING, or ERROR for a cf error)."""
    try:
        paths = resolve()
    except ContextForgeError as exc:
        # Expected, named failure (D5, #202): the cf message already says what to fix, so
        # it is the whole error: logged at ERROR without a traceback.
        _logger.error("dispatch post-condition: %s", exc)
        return str(exc)
    except (ValueError, TypeError, FileNotFoundError) as exc:
        msg = f"could not resolve expected {kind.value} artifact path for {scope}: {exc}"
        _logger.warning("dispatch post-condition: %s", msg)
        return msg
    if not paths:
        msg = (
            f"agent wrote no {kind.value} artifact for {scope} "
            f"(Context Forge lists no {kind.value} files for it)"
        )
        _logger.warning("dispatch post-condition: %s", msg)
        return msg
    return paths


def _check_dispatch_artifact_written(
    *,
    kind: ArtifactKind,
    scope: str,
    paths: list[str],
    cwd: str,
    run_started_at: datetime,
) -> str | None:
    """Verify one of *paths* was written this run.

    Returns None if the post-condition is satisfied, else an error message
    naming the failure mode. Every failure mode fails closed (returns a
    message) and is logged at WARNING — never a silent pass.
    """

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
        f"for {scope} (expected one of: {', '.join(paths)})"
    )
    _logger.warning("dispatch post-condition: %s", msg)
    return msg


def _dispatch_artifact_post_condition_error(
    *,
    kind: ArtifactKind,
    slice_param: object,
    plan_param: object,
    cf_client: CfClientProtocol,
    cwd: str,
    run_started_at: datetime | None,
    run_state_error: str | None,
) -> str | None:
    """Resolve the dispatch artifact post-condition for one dispatch action.

    Returns None if satisfied, else the failure message. Every branch fails
    closed and is logged at WARNING, or ERROR for a Context Forge error (see the
    helpers it calls).
    """
    if run_state_error is not None:
        return run_state_error
    if run_started_at is None:
        # Only reachable if a future caller sets expected_kind without also
        # resolving run_started_at/run_state_error — guards the invariant.
        msg = "run start time unavailable"
        _logger.warning("dispatch post-condition: %s", msg)
        return msg
    try:
        scope = dispatch_scope(slice_param, plan_param).label
    except ValueError as exc:
        msg = f"could not resolve expected {kind.value} artifact path: {exc}"
        _logger.warning("dispatch post-condition: %s", msg)
        return msg
    paths = _resolve_paths(
        kind, scope, lambda: dispatch_artifact_paths(kind, slice_param, plan_param, cf_client, cwd)
    )
    if isinstance(paths, str):
        return paths
    return _check_dispatch_artifact_written(
        kind=kind, scope=scope, paths=paths, cwd=cwd, run_started_at=run_started_at
    )


_QUESTION_CLOSERS = "*_`\"')]"


def _failure_metadata(response: str, final_text: str) -> dict[str, object]:
    """An agent whose last words are a question is waiting for an answer, not broken (#249).

    Heuristic: markdown emphasis and closing quotes after the question mark don't count.
    """
    if response.rstrip().rstrip(_QUESTION_CLOSERS).endswith("?"):
        return {
            FAILURE_KIND_KEY: FailureKind.AGENT_QUESTION.value,
            AGENT_QUESTION_KEY: final_text,
        }
    return {FAILURE_KIND_KEY: FailureKind.ARTIFACT_MISSING.value}


class DispatchArtifactAction:
    """POST_ACTION event action: fail a dispatch that wrote no artifact."""

    name = "squadron.dispatch-artifact"
    events = frozenset({EventType.POST_ACTION})

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        return []

    async def execute(self, context: EventContext) -> ActionResult:
        assert isinstance(context, PostActionContext)

        if (
            context.action_type != ActionType.DISPATCH
            or not context.result.success
            or context.expected_artifact_kind is None
            # A step that kept its existing artifact wrote nothing this run, by design.
            or context.result.outputs.get(SKIPPED_KEY)
        ):
            return ActionResult(success=True, action_type=self.name, outputs={})

        error = _dispatch_artifact_post_condition_error(
            kind=context.expected_artifact_kind,
            slice_param=context.params.get(SLICE_PARAM),
            plan_param=context.params.get(PLAN_PARAM),
            cf_client=context.cf_client,
            cwd=context.cwd,
            run_started_at=context.run_started_at,
            run_state_error=context.run_state_error,
        )
        if error is not None:
            # The agent's last words say why no artifact exists (D7). Appended
            # here, once, so every failure branch carries it.
            response = str(context.result.outputs.get("response", ""))
            final_text = tail_text(response)
            error = f'{error}; agent\'s final text: "{final_text}"'
            return ActionResult(
                success=False,
                action_type=self.name,
                outputs={},
                error=error,
                metadata=_failure_metadata(response, final_text),
            )
        return ActionResult(success=True, action_type=self.name, outputs={})


register_event_action(DispatchArtifactAction())
