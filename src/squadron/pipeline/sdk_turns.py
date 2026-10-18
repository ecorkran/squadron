"""Turn tracking for one persistent-session dispatch (slice 932 D5/D6).

Pure bookkeeping over SDK messages — no client, no I/O. ``SDKExecutionSession``
reads the stream and feeds each message here; this module decides which text
belongs to the response and which background agents are still running.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from claude_agent_sdk import (
    TERMINAL_TASK_STATUSES,
    AssistantMessage,
    ResultMessage,
    SystemMessage,
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
from squadron.providers.sdk.usage import SessionCostMeter, read_result_usage

__all__ = [
    "SESSION_STATE_ENV",
    "WAITED_TASK_TYPES",
    "BackgroundLedger",
    "DispatchTurns",
    "SessionReply",
    "SessionState",
    "is_own_result",
    "is_session_state_frame",
]

# Makes the CLI emit `session_state_changed` frames to the SDK consumer (slice
# 947 D12). The SDK sets its own SDK_READS_SESSION_STATE but marks those frames
# host-only and drops them, so the consumer-visible frames need this opt-in.
SESSION_STATE_ENV: Final = "CLAUDE_CODE_EMIT_SESSION_STATE_EVENTS"
_SESSION_STATE_SUBTYPE: Final = "session_state_changed"


class SessionState(StrEnum):
    """The CLI's own report of whether it still has work in hand."""

    IDLE = "idle"
    RUNNING = "running"
    REQUIRES_ACTION = "requires_action"


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


def is_session_state_frame(msg: object) -> bool:
    """True for the CLI's ``session_state_changed`` frame."""
    return isinstance(msg, SystemMessage) and msg.subtype == _SESSION_STATE_SUBTYPE


@dataclass(frozen=True)
class SessionReply:
    """A session call's response text and what it spent (slice 175 D4)."""

    text: str
    telemetry: RunTelemetry


@dataclass
class DispatchTurns:
    """Response text and task state accumulated across one dispatch's turns.

    The dispatch ends once our own result is in and the CLI reports ``idle``
    (D12). A CLI that sends no state frames falls back to the ledger: the
    dispatch ends once no tracked background agent is running.
    """

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
    # The connection's meter: results report the session's running cost total.
    cost_meter: SessionCostMeter = field(default_factory=SessionCostMeter)
    # The CLI's latest reported state, None until a frame arrives (D12). A string
    # the CLI sent that SessionState doesn't name is kept as-is and never idle.
    session_state: str | None = None
    unknown_state_warned: bool = False

    def collect(self, msg: object) -> str | None:
        """Record one message; return the session id it carries, if any."""
        self.progressed = True
        self.ledger.observe(msg)
        if isinstance(msg, SystemMessage) and is_session_state_frame(msg):
            self.observe_state(msg)
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
        self.telemetry.fold_result(turns=turns, usage=usage, cost_usd=self.cost_meter.charge(cost))

    def observe_state(self, msg: SystemMessage) -> None:
        """Record the state a ``session_state_changed`` frame carries."""
        state = msg.data.get("state")
        if not isinstance(state, str):
            state = repr(state)
        self.session_state = state
        if state not in SessionState and not self.unknown_state_warned:
            self.unknown_state_warned = True
            _logger.warning("SDK session reported unknown state %r; treating it as not idle", state)

    @property
    def waiting(self) -> bool:
        """Our own result is in, but the CLI still has work in hand.

        With state frames, that is any state but ``idle`` (D12): the CLI knows
        about every follow-up turn it owes, including ones the ledger never
        saw. Without them, it is a tracked background agent still running.
        """
        if not self.own_result_seen:
            return False
        if self.session_state is None:
            return self.ledger.active
        return self.session_state != SessionState.IDLE

    @property
    def settled(self) -> bool:
        """Our own result is in and nothing is owed: the dispatch is done."""
        return self.own_result_seen and not self.waiting

    def text(self) -> str:
        return "\n".join(self.parts)

    def discard(self) -> str:
        """Drop the text collected so far and return it (D6 leftover turn)."""
        dropped = self.text()
        self.parts.clear()
        return dropped
