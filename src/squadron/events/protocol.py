"""EventAction protocol — the interface every user-definable action satisfies."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from squadron.events import EventType
from squadron.events.contexts import EventContext
from squadron.pipeline.models import ActionResult, ValidationError


@runtime_checkable
class EventAction(Protocol):
    """Interface for all event action implementations.

    ``name`` and ``events`` are plain attributes (matching every built-in
    implementation) rather than properties — there is no computed logic
    behind either, so a property would only add ceremony.

    ``execute`` is async so ``asyncio.wait_for`` is the timeout mechanism
    (design D2). An action narrows *context* to the concrete subtype it
    expects and returns a failed ``ActionResult`` naming the mismatch if
    bound to an event it does not support.
    """

    #: Namespaced action identifier, e.g. 'squadron.frontmatter-gate'.
    name: str

    #: The events this action may be bound to.
    events: frozenset[EventType]

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        """Validate this action's binding params. Empty list if valid."""
        ...

    async def execute(self, context: EventContext) -> ActionResult:
        """Execute this action and return its result."""
        ...
