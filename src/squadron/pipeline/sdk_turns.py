"""Turn tracking for one persistent-session dispatch (slice 932 D5/D6).

Pure bookkeeping over SDK messages — no client, no I/O. ``SDKExecutionSession``
reads the stream and feeds each message here; this module decides which text
belongs to the response and which background agents are still running.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from claude_agent_sdk import (
    TERMINAL_TASK_STATUSES,
    AssistantMessage,
    ResultMessage,
    TaskNotificationMessage,
    TaskStartedMessage,
    TaskUpdatedMessage,
)

from squadron.core.models import (
    RATE_LIMIT_EVENT_TYPE,
    SDK_RESULT_TYPE,
    TOOL_RESULT_TYPE,
    TOOL_USE_TYPE,
)
from squadron.core.usage import RunTelemetry
from squadron.logging import get_logger
from squadron.providers.sdk.translation import translate_sdk_message
from squadron.providers.sdk.usage import read_result_usage

__all__ = ["WAITED_TASK_TYPES", "BackgroundLedger", "DispatchTurns", "SessionReply", "is_own_result"]

# Background task types a dispatch waits for. Mirrors the SDK's private
# DEFERRING_TASK_TYPES (claude_agent_sdk/_internal/query.py), redeclared on
# purpose because the SDK constant is internal. Shells and monitors may run
# forever, so they never hold a dispatch.
WAITED_TASK_TYPES: Final = frozenset({"local_agent", "local_workflow"})

# Translated message types that are not response prose. ResultMessage
# duplicates the assistant text as its `result` field (appending both doubles
# the response). tool_use/tool_result narrate tool calls and mixing them in
# produced an unreadable run-on line (issue #23, same class as #22/#20). An
# informational RateLimitEvent is a usage-meter notice, not prose.
_NON_PROSE_TYPES: Final = frozenset(
    {SDK_RESULT_TYPE, TOOL_USE_TYPE, TOOL_RESULT_TYPE, RATE_LIMIT_EVENT_TYPE}
)

_logger = get_logger(__name__)


class BackgroundLedger:
    """Background agents a single dispatch has seen start and not yet finish."""

    def __init__(self) -> None:
        self._active: dict[str, str] = {}
        self._seen: set[str] = set()

    def observe(self, msg: object) -> None:
        """Track or clear a task from one lifecycle message; ignore others."""
        if isinstance(msg, TaskStartedMessage):
            if msg.task_type in WAITED_TASK_TYPES:
                self._active[msg.task_id] = msg.description
                self._seen.add(msg.task_id)
        elif isinstance(msg, TaskNotificationMessage) or (
            isinstance(msg, TaskUpdatedMessage) and msg.status in TERMINAL_TASK_STATUSES
        ):
            # Either can be the only terminal signal (SDK docs).
            self._active.pop(msg.task_id, None)

    @property
    def active(self) -> bool:
        return bool(self._active)

    @property
    def seen_count(self) -> int:
        """Distinct waited-for agents ever tracked by this dispatch."""
        return len(self._seen)

    def active_ids(self) -> list[str]:
        return list(self._active)

    def descriptions(self) -> str:
        return ", ".join(self._active.values())

    def clear(self) -> None:
        self._active.clear()


def is_own_result(msg: ResultMessage) -> bool:
    """True for the result of our own prompt, False for an injected turn.

    The SDK says to treat any unrecognized origin kind as "not human".
    """
    return msg.origin is None or msg.origin.get("kind") == "human"


@dataclass(frozen=True)
class SessionReply:
    """A session call's response text and what it spent (slice 175 D4)."""

    text: str
    telemetry: RunTelemetry


@dataclass
class DispatchTurns:
    """Response text and task state accumulated across one dispatch's turns."""

    ledger: BackgroundLedger = field(default_factory=BackgroundLedger)
    parts: list[str] = field(default_factory=list[str])
    own_result_seen: bool = False
    waiting_logged: bool = False
    # Per read attempt: set once any non-rejected message arrives, so the
    # rate-limit retry budget bounds consecutive failures only.
    progressed: bool = False
    # Turns, tokens, and cost of every ResultMessage this dispatch read: its own,
    # injected follow-up turns, and interrupt drains (slice 175 D2). Each is real spend.
    telemetry: RunTelemetry = field(default_factory=RunTelemetry)
    usage_warned: bool = False

    def collect(self, msg: object) -> str | None:
        """Record one message; return the session id it carries, if any."""
        self.progressed = True
        self.ledger.observe(msg)
        if isinstance(msg, ResultMessage):
            self.fold_result(msg)
        # A subagent's own messages stream through too (parent_tool_use_id set); its
        # report reaches the main agent as a tool result, so its prose is not ours.
        is_subagent = isinstance(msg, AssistantMessage) and msg.parent_tool_use_id is not None
        session_id: str | None = None
        for translated in translate_sdk_message(msg, sender="pipeline"):
            if not is_subagent and translated.metadata.get("sdk_type") not in _NON_PROSE_TYPES:
                self.parts.append(translated.content)
            sid = translated.metadata.get("session_id")
            if isinstance(sid, str) and sid:
                session_id = sid
        return session_id

    def fold_result(self, msg: ResultMessage) -> None:
        """Add one result's usage; warn once per dispatch when it reported none."""
        usage, turns, cost = read_result_usage(msg)
        if usage is None and not self.usage_warned:
            self.usage_warned = True
            _logger.warning("SDK session result reported no token usage; usage will not be recorded")
        self.telemetry.fold_result(turns=turns, usage=usage, cost_usd=cost)

    @property
    def waiting(self) -> bool:
        """Our own result is in, but background agents are still running."""
        return self.own_result_seen and self.ledger.active

    def text(self) -> str:
        return "\n".join(self.parts)

    def discard(self) -> str:
        """Drop the text collected so far and return it (D6 leftover turn)."""
        dropped = self.text()
        self.parts.clear()
        return dropped
