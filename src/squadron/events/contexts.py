"""Event-typed contexts passed to EventAction.execute.

Deliberately not the pipeline ActionContext (see slice 173 design D1): a
commit event has no pipeline_name/run_id/resolver, and a post-action event
carries fields no commit ever has. Each event type gets exactly the fields
it can honestly provide.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from squadron.events import EventType

if TYPE_CHECKING:
    from squadron.pipeline.models import ActionResult
    from squadron.pipeline.steps.phase import ArtifactKind
    from squadron.review.persistence import CfClientProtocol


@dataclass(frozen=True)
class EventContext:
    """Common base for every event-typed context."""

    event: EventType
    cwd: str
    params: dict[str, object]


@dataclass(frozen=True)
class CommitContext(EventContext):
    """Context for a COMMIT event, fired externally by git."""

    staged_paths: tuple[str, ...]


@dataclass(frozen=True)
class PostActionContext(EventContext):
    """Context for a POST_ACTION event, fired by the executor.

    ``result.outputs`` is ``{}`` in prompt-only mode (D9) — event actions
    may not depend on it (D4).
    """

    action_type: str
    result: ActionResult
    run_id: str
    run_started_at: datetime | None
    run_state_error: str | None
    step_name: str
    step_type: str
    expected_artifact_kind: ArtifactKind | None
    iteration: int
    cf_client: CfClientProtocol
