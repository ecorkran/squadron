"""SDKExecutionSession — persistent ClaudeSDKClient wrapper for pipeline execution.

Manages a single ClaudeSDKClient connection across all dispatch steps in a
pipeline run, enabling per-step model switching and compaction configuration.

This module is used for SDK-mode pipeline runs, from a terminal or inside a
Claude Code session. Reviews and non-SDK actions are unaffected.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import NoReturn

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ClaudeSDKError,
    CLIConnectionError,
    CLIJSONDecodeError,
    CLINotFoundError,
    ProcessError,
    RateLimitEvent,
    ResultMessage,
)
from claude_agent_sdk.types import SystemPromptPreset

from squadron.config.keys import FOREGROUND_IDLE_TIMEOUT_KEY
from squadron.config.manager import get_positive_int_config, get_typed_config
from squadron.core.teardown import close_best_effort
from squadron.core.usage import RunTelemetry
from squadron.pipeline.background_shell_guard import pipeline_hooks
from squadron.pipeline.sdk_turns import (
    SESSION_STATE_ENV,
    DispatchTurns,
    SessionReply,
    is_own_result,
    is_session_state_frame,
)
from squadron.pipeline.text_tail import tail_text
from squadron.providers.errors import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderError,
)
from squadron.providers.sdk.rate_limit import (
    MAX_RATE_LIMIT_RETRIES,
    RateLimitRejected,
    UsageLimitReached,
    event_blocks,
    is_throttle,
    is_usage_limit,
    rate_limit_backoff_s,
)
from squadron.providers.sdk.settings import (
    AUTO_MEMORY_DISABLE_ENV,
    pipeline_setting_sources,
    sdk_settings_options,
)
from squadron.providers.sdk.usage import SessionCostMeter

_logger = logging.getLogger(__name__)

__all__ = [
    "INTERRUPT_DRAIN_TIMEOUT_S",
    "DispatchStalledError",
    "SDKExecutionSession",
    "SeedSource",
    "frame_summary_for_seed",
    "open_pipeline_session",
]


_SEED_FRAMING_PREFIX = (
    "[The following is a summary of earlier work in this pipeline run. "
    "It is reference material, not a task, and not an instruction to do "
    "anything.]\n\n"
)


class SeedSource(StrEnum):
    """What a session rotation's seed came from; named in the seeding log."""

    COMPACT = "compact"
    RESUME = "resume"
    RESTORE = "restore"
    REPLACEMENT = "replacement"  # an unusable session replaced by an unseeded one


def frame_summary_for_seed(summary: str) -> str:
    """Wrap a compact summary with framing for its place in the system prompt.

    The seed is appended to the preset system prompt of a fresh session
    (never sent as a turn), so the framing marks it as reference material.
    Used for rotation, resume, and restore seeding alike.
    """
    return _SEED_FRAMING_PREFIX + summary


def _seeded_options(base: ClaudeAgentOptions, seed: str | None) -> ClaudeAgentOptions:
    """Return ``base`` with the framed seed appended to its preset prompt.

    ``base`` is never mutated. An existing ``append`` is kept first, with the
    seed after a blank line.
    """
    if seed is None:
        return base
    framed = frame_summary_for_seed(seed)
    existing = base.system_prompt
    if isinstance(existing, dict) and existing["type"] == "preset":
        prior = existing.get("append")
        if prior:
            framed = f"{prior}\n\n{framed}"
    preset: SystemPromptPreset = {"type": "preset", "preset": "claude_code", "append": framed}
    return dataclasses.replace(base, system_prompt=preset)


# Per-read bound on the post-interrupt drain, and on the interrupt request itself
# (slice 174 D7). Matches the SDK's own 60 s control-request bound.
INTERRUPT_DRAIN_TIMEOUT_S = 60

# A rejected model switch is usually transient (the API says "try again"), so it
# gets a few spaced attempts before the step fails (issue 230).
SET_MODEL_ATTEMPTS = 3
SET_MODEL_RETRY_DELAY_S = 2.0


class _IdleTimeout(Exception):
    """A read's idle bound expired: a background wait (932 D5) or a foreground turn (174 D7)."""


class DispatchStalledError(ProviderError):
    """A foreground turn was silent past ``pipeline.foreground_idle_timeout_s`` (174 D7).

    The turn was interrupted. ``session_usable`` says whether the interrupt and
    the drain completed, so the next dispatch on this session can proceed.
    """

    def __init__(self, idle_s: float, session_usable: bool) -> None:
        super().__init__(f"no output for {idle_s:.0f}s; turn interrupted")
        self.idle_s = idle_s
        self.session_usable = session_usable


@dataclass
class SDKExecutionSession:
    """Manages a persistent ClaudeSDKClient across pipeline steps.

    Lifecycle:
    - Call ``connect()`` before the first dispatch.
    - Call ``set_model()`` before each dispatch to switch models.
    - Call ``dispatch()`` to send a prompt and collect the response.
    - Call ``compact()`` to perform session-rotate compaction.
    - Call ``seed_context()`` to replace the session with a fresh one seeded
      with a prior summary (resume, restore).
    - Call ``disconnect()`` after the pipeline finishes (or on checkpoint).

    The client is connected once and reused across all steps, enabling
    ``set_model()`` to switch models mid-session without spawning new processes.
    ``base_options`` is the unseeded option set, retained so rotation can
    build a fresh client with the same configuration. A seed is applied per
    connect and never stored back.
    """

    client: ClaudeSDKClient
    base_options: ClaudeAgentOptions
    current_model: str | None = None
    session_id: str | None = None
    # Set when a rotation's reconnect fails; every later call then raises.
    unusable_reason: str | None = None
    # Set by the last dispatch(): background agents it waited for, and how
    # many it stopped on an idle timeout (zero on every other path).
    background_tasks_waited: int = 0
    background_tasks_stopped: int = 0
    # Background shells still running when the last dispatch ended (stopped at the
    # idle bound); agent counts above stay agent-only (slice 947 D11).
    background_shells_running: int = 0
    # Whether the live client carries a seed in its system prompt.
    seeded: bool = False
    # Per-result cost from the live client's running total; replaced with the client.
    cost_meter: SessionCostMeter = field(default_factory=SessionCostMeter)

    @property
    def setting_sources(self) -> list[str] | None:
        """Settings sources every client of this session is built with."""
        sources = self.base_options.setting_sources
        return None if sources is None else list(sources)

    @property
    def auto_memory(self) -> bool:
        """Whether this session's clients load Claude Code auto-memory."""
        return AUTO_MEMORY_DISABLE_ENV not in self.base_options.env

    async def connect(self) -> None:
        """Connect the underlying SDK client.

        Permission mode is set at session start via ``ClaudeAgentOptions``
        when the client is constructed (see ``run.py``). The SDK rejects
        runtime ``set_permission_mode("bypassPermissions")`` calls, so we
        do not attempt one here.
        """
        await self.client.connect()
        _logger.debug("SDKExecutionSession: connected")

    async def disconnect(self) -> None:
        """Disconnect the SDK client. Best-effort — ignores errors."""
        await close_best_effort(self.client.disconnect, _logger, "SDKExecutionSession.disconnect")

    async def set_model(self, model_id: str) -> None:
        """Switch model if different from current.

        Args:
            model_id: Resolved model ID (e.g. 'claude-haiku-4-5-20251001').
                      Skipped if identical to the currently active model.

        Raises:
            ProviderError: If the CLI rejects the switch on every attempt (issue 230).
        """
        if model_id == self.current_model:
            return
        for attempt in range(1, SET_MODEL_ATTEMPTS + 1):
            try:
                await self.client.set_model(model_id)
                break
            # The SDK raises bare Exception for a rejected or timed-out control
            # request ("Couldn't confirm model ..."); there is no narrower type.
            except Exception as exc:  # noqa: BLE001
                _logger.debug("set_model %s failed", model_id, exc_info=True)
                if attempt == SET_MODEL_ATTEMPTS:
                    raise ProviderError(f"could not switch to model {model_id}: {exc}") from exc
                _logger.warning(
                    "set_model %s failed (attempt %d/%d): %s; retrying in %.0fs.",
                    model_id,
                    attempt,
                    SET_MODEL_ATTEMPTS,
                    exc,
                    SET_MODEL_RETRY_DELAY_S,
                )
                await asyncio.sleep(SET_MODEL_RETRY_DELAY_S)
        self.current_model = model_id
        _logger.debug("SDKExecutionSession: switched model to %s", model_id)

    async def dispatch(self, prompt: str) -> SessionReply:
        """Send a prompt and collect the full response text.

        Reads past the turn's result while background agents the turn started
        are still running, and returns only on this dispatch's own result
        (slice 932 D5/D6). Text from the follow-up turn the CLI injects when
        an agent reports back is part of the response.

        Rate-limit retry: a ``rejected`` ``RateLimitEvent`` raises
        ``RateLimitRejected`` inline (this path has no ``_skip_unparseable``
        wrapper, unlike ``agent.py``). ``receive_response()`` is retried on the
        same session (the channel stays intact) up to ``MAX_RATE_LIMIT_RETRIES``.

        Raises:
            ProviderAuthError: If the CLI is not found.
            ProviderAPIError: If the CLI exits with an error code.
            ProviderError: For other SDK errors, if the session is unusable, or
                if the stream ends while a background agent is still running.
        """
        await self._ensure_usable()
        turns = DispatchTurns(cost_meter=self.cost_meter)
        self.background_tasks_stopped = 0
        self.background_shells_running = 0
        try:
            text = await self._query_and_collect(prompt, turns)
        except ProviderError as exc:
            # What the dispatch spent before it failed rides the error (slice 175 D5).
            exc.telemetry = turns.telemetry.snapshot()
            raise
        finally:
            self.background_tasks_waited = turns.ledger.seen_count
        return SessionReply(text=text, telemetry=turns.telemetry.snapshot())

    async def _query_and_collect(self, prompt: str, turns: DispatchTurns) -> str:
        """Send ``prompt`` and read its turns, mapping SDK errors to provider errors."""
        try:
            await self.client.query(prompt)
            return await self._collect_turns(turns)
        except CLINotFoundError as exc:
            raise ProviderAuthError(str(exc)) from exc
        except ProcessError as exc:
            raise ProviderAPIError(str(exc), status_code=getattr(exc, "exit_code", None)) from exc
        except (CLIConnectionError, CLIJSONDecodeError, ClaudeSDKError) as exc:
            raise ProviderError(str(exc)) from exc

    async def _collect_turns(self, turns: DispatchTurns) -> str:
        """Read turns until our own result is in and the CLI has nothing more owed (D12).

        With state frames, "nothing owed" is the CLI reporting ``idle``, in either
        order with our result. Without them, it is no tracked background agent
        running. A wait on any other state is bounded by the background idle timeout.
        """
        idle_s: float | None = None
        foreground_idle_s = self._foreground_idle_timeout_s()
        while True:
            if not turns.waiting:
                try:
                    result = await self._read_turn_with_retry(turns, idle_s=foreground_idle_s)
                except _IdleTimeout:
                    await self._interrupt_stalled_turn(turns, foreground_idle_s)
            else:
                if idle_s is None:
                    idle_s = self._background_idle_timeout_s()
                try:
                    result = await self._read_turn_with_retry(turns, idle_s=idle_s)
                except _IdleTimeout:
                    await self._stop_background(turns, idle_s)
                    return turns.text()
            if turns.settled:
                # An idle frame after our result ended the read with no result (D12).
                return turns.text()
            if result is None:
                # The iterator ended without a result. With nothing tracked or
                # owed, this is today's behavior; otherwise the work the CLI
                # owes can never arrive.
                if turns.ledger.holding or turns.waiting:
                    ended = (
                        "stream ended after the dispatch's result, before the CLI reported idle"
                        if turns.own_result_seen
                        else "stream ended before the dispatch's result"
                    )
                    raise ProviderError(
                        f"{ended}; "
                        f"session state {turns.session_state!r}, "
                        f"{len(turns.ledger.active_ids())} background agent(s) still "
                        f"running: {turns.ledger.descriptions()}; "
                        f"{len(turns.ledger.shell_ids())} background shell(s) still "
                        f"running: {turns.ledger.shell_descriptions()}"
                    )
                return turns.text()
            if is_own_result(result):
                turns.own_result_seen = True
            elif not turns.own_result_seen:
                # An injected result before our own: everything read so far
                # is a follow-up turn owed by the previous dispatch (D6).
                _logger.warning(
                    "dispatch: discarded a background follow-up turn left over from "
                    'the previous dispatch; its final text: "%s"',
                    tail_text(turns.discard()),
                )
                continue
            if turns.settled:
                return turns.text()
            if turns.waiting and not turns.waiting_logged:
                turns.waiting_logged = True
                # `running` briefly follows every result before `idle`; that is only
                # worth INFO when an agent or shell is actually being waited for.
                _logger.log(
                    logging.INFO if turns.ledger.holding else logging.DEBUG,
                    "dispatch: turn ended with session state %r, %d background agent(s) and "
                    "%d background shell(s) running; waiting: %s",
                    turns.session_state,
                    len(turns.ledger.active_ids()),
                    len(turns.ledger.shell_ids()),
                    ", ".join(
                        d for d in (turns.ledger.descriptions(), turns.ledger.shell_descriptions()) if d
                    ),
                )

    async def _read_turn_with_retry(
        self, turns: DispatchTurns, *, idle_s: float | None
    ) -> ResultMessage | None:
        """One ``receive_response()`` pass, retried on a rate-limit throttle."""
        retries = 0
        while True:
            turns.progressed = False
            try:
                return await self._read_turn(turns, idle_s=idle_s)
            except ClaudeSDKError as exc:
                # A rejected RateLimitEvent raises RateLimitRejected in
                # _read_turn; a genuine 429 can also surface as a plain
                # ClaudeSDKError. is_throttle classifies both. A throttle
                # after work came through is a fresh event, so the budget
                # bounds consecutive failures rather than throttles-per-run.
                if turns.progressed:
                    retries = 0
                if not is_throttle(exc) or retries >= MAX_RATE_LIMIT_RETRIES:
                    raise
                retries += 1
                delay = rate_limit_backoff_s(retries)
                _logger.warning(
                    "Rate limited (attempt %d/%d); waiting %.0fs before retry.",
                    retries,
                    MAX_RATE_LIMIT_RETRIES,
                    delay,
                )
                await asyncio.sleep(delay)

    async def _read_turn(
        self, turns: DispatchTurns, *, idle_s: float | None, accept_error: bool = False
    ) -> ResultMessage | None:
        """Read one turn; return its result, or None if the stream ended first.

        Also returns None when an ``idle`` state frame settles the dispatch
        after our result (D12); the caller tells the two apart by ``turns.settled``.

        With ``idle_s`` set, each wait for the next message is bounded by it
        (the timer resets on every message) and expiry raises ``_IdleTimeout``.
        With ``accept_error``, an ``is_error`` result is returned rather than
        raised: the interrupted turn's own result ends that way (174 D7).
        """
        stream = aiter(self.client.receive_response())
        while True:
            idle_timer = asyncio.timeout(idle_s)  # fresh per message: the timer resets
            try:
                async with idle_timer:
                    sdk_msg = await anext(stream)
            except StopAsyncIteration:
                return None
            except TimeoutError as exc:
                # Only our own timer means "idle"; any other TimeoutError propagates.
                if idle_timer.expired():
                    raise _IdleTimeout from exc
                raise
            # Inspect a RateLimitEvent before anything else touches it, and
            # before collect() marks progress: a rejected event is not
            # progress and must consume retry budget.
            if isinstance(sdk_msg, RateLimitEvent) and event_blocks(sdk_msg):
                info = sdk_msg.rate_limit_info
                # A limit that resets hours out is not worth backing off for (issue 248).
                if is_usage_limit(info, time.time()):
                    raise UsageLimitReached.from_info(info)
                turns.rate_limit_rejection = info
                raise RateLimitRejected(f"rate_limit_event status={info.status!r}")
            # Raise before collecting any content so no partial error text
            # reaches the caller or _check_cli_error.
            if isinstance(sdk_msg, ResultMessage) and sdk_msg.is_error and not accept_error:
                turns.progressed = True
                turns.fold_result(sdk_msg)  # an error result still spent tokens (D5)
                if turns.rate_limit_rejection is not None:
                    raise UsageLimitReached.from_info(turns.rate_limit_rejection)
                raise ProviderAPIError(
                    f"SDK reported is_error=True: {sdk_msg.result or sdk_msg.subtype}"
                )
            sid = turns.collect(sdk_msg)
            if sid is not None:
                self.session_id = sid
                _logger.debug("SDKExecutionSession: session_id=%s", sid)
            if isinstance(sdk_msg, ResultMessage):
                return sdk_msg
            if is_session_state_frame(sdk_msg) and turns.settled:
                return None  # the CLI went idle with nothing owed; the caller checks settled

    def _background_idle_timeout_s(self) -> float:
        """Read ``pipeline.background_idle_timeout_s`` for this session's cwd."""
        return get_typed_config("pipeline.background_idle_timeout_s", int, cwd=self._config_cwd())

    def _foreground_idle_timeout_s(self) -> float:
        """Read ``pipeline.foreground_idle_timeout_s`` for this session's cwd (174 D1)."""
        return get_positive_int_config(FOREGROUND_IDLE_TIMEOUT_KEY, cwd=self._config_cwd())

    def _config_cwd(self) -> str:
        # The CLI itself runs in the process cwd when options carry none.
        return str(self.base_options.cwd or Path.cwd())

    async def _interrupt_stalled_turn(self, turns: DispatchTurns, idle_s: float) -> NoReturn:
        """Interrupt a silent foreground turn and drain it, then raise (174 D7).

        The session stays usable when the interrupt and the drain both
        complete; otherwise it is marked unusable and later calls fail fast.
        """
        _logger.warning("dispatch: foreground turn silent for %ds; interrupting", idle_s)
        failure = await self._interrupt_and_drain(turns)
        if failure is not None:
            self.unusable_reason = f"foreground stall: interrupt did not complete ({failure})"
            _logger.error("dispatch: %s", self.unusable_reason)
        raise DispatchStalledError(idle_s, session_usable=failure is None)

    async def _interrupt_and_drain(self, turns: DispatchTurns) -> str | None:
        """Send the interrupt and read to the dispatch's own result; the failure, or None."""
        try:
            async with asyncio.timeout(INTERRUPT_DRAIN_TIMEOUT_S):
                await self.client.interrupt()
        except Exception as exc:  # noqa: BLE001
            # The SDK raises a bare Exception when the control request fails or
            # times out, and our own bound raises TimeoutError; either way the
            # interrupt did not complete, which the caller reports at ERROR.
            return f"interrupt failed: {exc!r}"
        while True:
            try:
                result = await self._read_turn(
                    turns, idle_s=INTERRUPT_DRAIN_TIMEOUT_S, accept_error=True
                )
            except _IdleTimeout:
                return f"no result within {INTERRUPT_DRAIN_TIMEOUT_S}s of the interrupt"
            if result is None:
                return "stream ended before the interrupted turn's result"
            if is_own_result(result):
                return None

    async def _stop_background(self, turns: DispatchTurns, idle_s: float) -> None:
        """Stop every tracked agent and shell after an idle timeout, best-effort (D5, D11)."""
        agent_ids = turns.ledger.active_ids()
        agent_descriptions = turns.ledger.descriptions()
        shell_ids = turns.ledger.shell_ids()
        shell_descriptions = turns.ledger.shell_descriptions()
        await self._stop_tasks(agent_ids + shell_ids)
        # Clear locally: a lost terminal signal is exactly the case here.
        turns.ledger.clear()
        self.background_tasks_stopped = len(agent_ids)
        self.background_shells_running = len(shell_ids)
        if not agent_ids and not shell_ids:
            # The CLI said it was still working (D12) but nothing in the ledger explains it.
            _logger.warning(
                "dispatch: no activity for %ds with session state %r and no tracked background "
                "work; ending the dispatch",
                idle_s,
                turns.session_state,
            )
        if agent_ids:
            _logger.warning(
                "dispatch: no activity for %ds with background agent(s) still running; stopped: %s",
                idle_s,
                agent_descriptions,
            )
        if shell_ids:
            _logger.warning(
                "dispatch ended with %d background shell(s) running: %s (no activity for %ds; stopped)",
                len(shell_ids),
                shell_descriptions,
                idle_s,
            )

    async def _stop_tasks(self, task_ids: list[str]) -> None:
        for task_id in task_ids:
            try:
                await self.client.stop_task(task_id)
            except Exception:  # noqa: BLE001
                # The SDK raises a bare Exception both when the stop control
                # request times out (60s) and when the CLI returns an error,
                # so no narrower type exists. Stopping is cleanup: log and go
                # on to the next id. A late follow-up turn is handled by D6.
                _logger.exception("dispatch: failed to stop background task %s", task_id)

    async def capture_summary(
        self,
        instructions: str,
        summary_model: str | None = None,
        restore_model: str | None = None,
    ) -> SessionReply:
        """Generate a summary of the live session without rotating.

        Switches to summary_model if provided, dispatches instructions,
        captures the response as the summary, optionally restores the
        prior model, and returns the summary text. Does NOT disconnect
        the client or create a new session.
        """
        if summary_model is not None and summary_model != self.current_model:
            await self.set_model(summary_model)
        _logger.debug("SDKExecutionSession.capture_summary: dispatching instructions")
        reply = await self.dispatch(instructions)
        if restore_model is not None and restore_model != self.current_model:
            await self.set_model(restore_model)
        return reply

    async def compact(
        self,
        instructions: str,
        summary_model: str | None = None,
        restore_model: str | None = None,
        summary: str | None = None,
    ) -> SessionReply:
        """Perform session-rotate compaction. Returns the summary and its capture's spend.

        With ``summary`` supplied nothing is captured, so the reply's telemetry is empty
        (``turns == 0``).

        Flow (when ``summary`` is None):
          1. Optionally switch to a cheap summarization model.
          2. Dispatch the compact instructions to the live session and
             capture the response as the summary via ``capture_summary``.
          3. Rotate to a fresh client whose system prompt carries the
             summary as seed (``_reconnect``). No turn is sent to it.
          4. Optionally restore the prior model.

        When ``summary`` is provided, the capture phase is skipped entirely
        and the given text is used directly for seeding. This allows callers
        that have already captured a summary (e.g. the summary action) to
        reuse it without dispatching again.

        Exceptions are allowed to propagate; the compact action wraps them.
        """
        await self._ensure_usable()
        if summary is None:
            reply = await self.capture_summary(
                instructions, summary_model=summary_model, restore_model=None
            )
        else:
            reply = SessionReply(text=summary, telemetry=RunTelemetry())

        await self._reconnect(reply.text, SeedSource.COMPACT)

        if restore_model is not None:
            await self.set_model(restore_model)

        return reply

    async def seed_context(self, text: str, source: SeedSource) -> None:
        """Replace the session with a fresh one seeded with ``text``.

        Any history since the last rotation is dropped. The caller passes
        raw text; framing happens in ``_seeded_options``. No turn is sent.
        """
        await self._ensure_usable()
        await self._reconnect(text, source)

    async def _ensure_usable(self) -> None:
        """Replace an unusable session with a fresh, unseeded one (issue 200).

        A stalled interrupt or a failed reconnect leaves the session unusable, and
        failing every later step would turn one stall into a failed run. The old
        conversation is already lost, so the replacement starts empty; that is logged
        at WARNING. If the replacement cannot connect, ``_reconnect`` records why and
        raises, and the next call tries again.
        """
        if self.unusable_reason is None:
            return
        _logger.warning(
            "SDK session unusable (%s); replacing it with a fresh session", self.unusable_reason
        )
        self.unusable_reason = None
        await self._reconnect(None, SeedSource.REPLACEMENT)

    async def _reconnect(self, seed: str | None, source: SeedSource) -> None:
        """Disconnect and connect a fresh client seeded via the system prompt."""
        await self.disconnect()
        self.client = ClaudeSDKClient(options=_seeded_options(self.base_options, seed))
        self.cost_meter = SessionCostMeter()
        self.current_model = None
        self.session_id = None
        self.seeded = seed is not None
        try:
            await self.connect()
        except Exception as exc:
            # The old client is already gone, so the session cannot be used
            # again. Record why; _require_usable() fails every later call.
            self.unusable_reason = f"reconnect failed: {exc}"
            _logger.exception("SDKExecutionSession: reconnect (source: %s) failed", source)
            raise
        _logger.info(
            "seeded fresh session via system prompt (%d chars, source: %s)",
            len(seed or ""),
            source,
        )


async def open_pipeline_session(*, seed: str | None = None) -> SDKExecutionSession:
    """Build and connect the pipeline's persistent SDK session.

    The only way to build a pipeline session. Permission mode must be set at
    session start; the SDK rejects runtime ``set_permission_mode(
    "bypassPermissions")`` calls. The Claude Code preset gives dispatches the
    full Claude Code persona rather than the Agent SDK's minimal prompt. A
    ``seed`` is appended to that preset (see ``_seeded_options``), never sent
    as a turn. Settings follow the pipeline policy (slice 932 D10/D11).
    """
    cwd = str(Path.cwd())
    settings = sdk_settings_options(
        pipeline_setting_sources(
            include_user=get_typed_config("pipeline.user_settings", bool, cwd=cwd)
        ),
        auto_memory=get_typed_config("pipeline.auto_memory", bool, cwd=cwd),
    )
    base = ClaudeAgentOptions(
        cwd=cwd,
        permission_mode="bypassPermissions",
        system_prompt={"type": "preset", "preset": "claude_code"},
        setting_sources=settings["setting_sources"],  # pyright: ignore[reportArgumentType]
        # Dispatch ends on the CLI's own idle report (slice 947 D12).
        env={**settings["env"], SESSION_STATE_ENV: "1"},
        hooks=pipeline_hooks(),  # pyright: ignore[reportArgumentType]
    )
    client = ClaudeSDKClient(options=_seeded_options(base, seed))
    session = SDKExecutionSession(client=client, base_options=base, seeded=seed is not None)
    await session.connect()
    return session
