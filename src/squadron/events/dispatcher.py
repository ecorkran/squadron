"""Event dispatcher — the one execution path for both COMMIT and POST_ACTION.

Semantics (design D4/D5): COMMIT runs every binding and collects every
failure — a commit gate that stops at the first finding hides the second.
POST_ACTION stops at the first failure, expressing the 909-before-911
ordering as registration-then-manifest order. An action that raises or
exceeds its timeout is treated as Fail, attributed to the action name — the
one deliberate ``except Exception`` in this slice, at the dispatch boundary.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import StrEnum

from squadron.config.manager import get_typed_config
from squadron.events import (
    EventType,
    bootstrap_event_actions,
    get_event_action,
    list_event_actions,
)
from squadron.events.contexts import EventContext
from squadron.events.discovery import discover_plugins
from squadron.events.manifest import Binding, load_manifest, resolve_bindings
from squadron.pipeline.models import ActionResult

_logger = logging.getLogger(__name__)


class OutcomeErrorKind(StrEnum):
    """Why a binding's outcome was a failure, or that it wasn't."""

    NONE = "none"
    RAISED = "raised"
    TIMEOUT = "timeout"
    DISABLED = "disabled"


@dataclass(frozen=True)
class EventOutcome:
    """One binding's result from a dispatch run."""

    action_name: str
    result: ActionResult | None
    error_kind: OutcomeErrorKind


async def _run_binding(binding: Binding, context: EventContext, timeout_seconds: int) -> EventOutcome:
    action = get_event_action(binding.action)
    start = time.monotonic()
    try:
        result = await asyncio.wait_for(action.execute(context), timeout=timeout_seconds)
    except TimeoutError:
        _logger.warning("%s: timed out after %ss", binding.action, timeout_seconds)
        return EventOutcome(
            action_name=binding.action, result=None, error_kind=OutcomeErrorKind.TIMEOUT
        )
    except Exception:
        # Deliberately broad (project exception-handling rule, clause c): this
        # is the dispatch boundary between squadron and third-party plugin
        # code. Per design D5, any exception an action raises — a plugin bug,
        # not an expected failure mode squadron itself defines — is attributed
        # Fail, logged with the traceback, and the run continues per the
        # event's semantics (COMMIT keeps going, POST_ACTION stops).
        _logger.exception("%s: raised during execute", binding.action)
        return EventOutcome(action_name=binding.action, result=None, error_kind=OutcomeErrorKind.RAISED)

    duration = time.monotonic() - start
    if result.success:
        _logger.debug("%s: ok (%.2fs)", binding.action, duration)
    else:
        _logger.warning("%s: failed (%.2fs): %s", binding.action, duration, result.error)
    return EventOutcome(action_name=binding.action, result=result, error_kind=OutcomeErrorKind.NONE)


async def fire(
    context: EventContext,
    bindings: list[Binding],
    *,
    cwd: str = ".",
) -> list[EventOutcome]:
    """Run every binding for *context*'s event, per the event's semantics.

    *bindings* must already be filtered/ordered by the caller (built-ins
    then manifest, in file order) and scoped to ``context.event`` — this
    function does not consult the manifest itself.
    """
    timeout_seconds = int(get_typed_config("events.timeout_seconds", int, cwd=cwd))

    outcomes: list[EventOutcome] = []
    for binding in bindings:
        outcome = await _run_binding(binding, context, timeout_seconds)
        outcomes.append(outcome)

        failed = outcome.error_kind is not OutcomeErrorKind.NONE or (
            outcome.result is not None and not outcome.result.success
        )
        if failed and context.event is EventType.POST_ACTION:
            break

    return outcomes


async def run_event(context: EventContext) -> list[EventOutcome]:
    """Resolve the manifest, discover plugins, and fire *context*'s event.

    The single orchestration entry point shared by ``sq events fire`` (D8)
    and the executor's POST_ACTION call site: load manifest (project ->
    user, first found), import declared plugins (attributed hard-fail —
    ``PluginLoadError`` propagates, never skipped), resolve every binding's
    action name against the registry, then run only the bindings scoped to
    ``context.event``.
    """
    bootstrap_event_actions()

    manifest = load_manifest(cwd=context.cwd)
    manifest_source = str(manifest.manifest_path) if manifest.manifest_path is not None else "defaults"
    discover_plugins(manifest.plugins, manifest_source=manifest_source, cwd=context.cwd)
    resolve_bindings(manifest, list_event_actions(), get_event_action)

    scoped = [b for b in manifest.bindings if b.event is context.event]
    return await fire(context, scoped, cwd=context.cwd)
