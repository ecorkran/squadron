"""SDKExecutionSession — persistent ClaudeSDKClient wrapper for pipeline execution.

Manages a single ClaudeSDKClient connection across all dispatch steps in a
pipeline run, enabling per-step model switching and compaction configuration.

This module is only used when running pipelines from a standard terminal (not
inside a Claude Code session). Reviews and non-SDK actions are unaffected.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

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

from squadron.config.manager import get_typed_config
from squadron.pipeline.sdk_turns import DispatchTurns, is_own_result
from squadron.pipeline.text_tail import tail_text
from squadron.providers.errors import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderError,
)
from squadron.providers.sdk.rate_limit import (
    MAX_RATE_LIMIT_RETRIES,
    RateLimitRejected,
    event_blocks,
    is_throttle,
    rate_limit_backoff_s,
)
from squadron.providers.sdk.settings import (
    AUTO_MEMORY_DISABLE_ENV,
    PIPELINE_SETTING_SOURCES,
    sdk_settings_options,
)

_logger = logging.getLogger(__name__)

__all__ = ["SDKExecutionSession", "SeedSource", "frame_summary_for_seed", "open_pipeline_session"]


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
    # Whether the live client carries a seed in its system prompt.
    seeded: bool = False

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
        try:
            await self.client.disconnect()
        except Exception:  # noqa: BLE001
            # Teardown boundary: client.disconnect() closes the SDK's
            # subprocess/transport, whose failure modes are internal to the
            # SDK and not enumerable here. A cleanup failure at process exit
            # must not mask the pipeline's actual result — logged for
            # diagnosability, never re-raised.
            _logger.exception("SDKExecutionSession.disconnect: ignoring error during cleanup")

    async def set_model(self, model_id: str) -> None:
        """Switch model if different from current.

        Args:
            model_id: Resolved model ID (e.g. 'claude-haiku-4-5-20251001').
                      Skipped if identical to the currently active model.
        """
        if model_id == self.current_model:
            return
        await self.client.set_model(model_id)
        self.current_model = model_id
        _logger.debug("SDKExecutionSession: switched model to %s", model_id)

    async def dispatch(self, prompt: str) -> str:
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
        self._require_usable()
        turns = DispatchTurns()
        self.background_tasks_stopped = 0
        try:
            await self.client.query(prompt)
            return await self._collect_turns(turns)
        except CLINotFoundError as exc:
            raise ProviderAuthError(str(exc)) from exc
        except ProcessError as exc:
            raise ProviderAPIError(str(exc), status_code=getattr(exc, "exit_code", None)) from exc
        except (CLIConnectionError, CLIJSONDecodeError, ClaudeSDKError) as exc:
            raise ProviderError(str(exc)) from exc
        finally:
            self.background_tasks_waited = turns.ledger.seen_count

    async def _collect_turns(self, turns: DispatchTurns) -> str:
        """Read turns until our own result arrives with no agent running."""
        idle_s: float | None = None
        while True:
            if not turns.waiting:
                # Foreground turns get no timer (#165).
                result = await self._read_turn_with_retry(turns, idle_s=None)
            else:
                if idle_s is None:
                    idle_s = self._background_idle_timeout_s()
                try:
                    result = await self._read_turn_with_retry(turns, idle_s=idle_s)
                except TimeoutError:
                    await self._stop_background(turns, idle_s)
                    return turns.text()
            if result is None:
                # The iterator ended without a result. With nothing tracked,
                # this is today's behavior; with an agent tracked, the work
                # it owes can never arrive.
                if turns.ledger.active:
                    raise ProviderError(
                        "stream ended before the dispatch's result; "
                        f"{len(turns.ledger.active_ids())} background agent(s) still "
                        f"running: {turns.ledger.descriptions()}"
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
            if turns.own_result_seen and not turns.ledger.active:
                return turns.text()
            if turns.waiting and not turns.waiting_logged:
                turns.waiting_logged = True
                _logger.info(
                    "dispatch: turn ended with %d background agent(s) running; waiting: %s",
                    len(turns.ledger.active_ids()),
                    turns.ledger.descriptions(),
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

    async def _read_turn(self, turns: DispatchTurns, *, idle_s: float | None) -> ResultMessage | None:
        """Read one turn; return its result, or None if the stream ended first.

        With ``idle_s`` set, each wait for the next message is bounded by it
        (the timer resets on every message) and expiry raises ``TimeoutError``.
        """
        stream = aiter(self.client.receive_response())
        while True:
            try:
                async with asyncio.timeout(idle_s):
                    sdk_msg = await anext(stream)
            except StopAsyncIteration:
                return None
            # Inspect a RateLimitEvent before anything else touches it, and
            # before collect() marks progress: a rejected event is not
            # progress and must consume retry budget.
            if isinstance(sdk_msg, RateLimitEvent) and event_blocks(sdk_msg):
                raise RateLimitRejected(f"rate_limit_event status={sdk_msg.rate_limit_info.status!r}")
            # Raise before collecting any content so no partial error text
            # reaches the caller or _check_cli_error.
            if isinstance(sdk_msg, ResultMessage) and sdk_msg.is_error:
                turns.progressed = True
                raise ProviderAPIError(
                    f"SDK reported is_error=True: {sdk_msg.result or sdk_msg.subtype}"
                )
            sid = turns.collect(sdk_msg)
            if sid is not None:
                self.session_id = sid
                _logger.debug("SDKExecutionSession: session_id=%s", sid)
            if isinstance(sdk_msg, ResultMessage):
                return sdk_msg

    def _background_idle_timeout_s(self) -> float:
        """Read ``pipeline.background_idle_timeout_s`` for this session's cwd."""
        # The CLI itself runs in the process cwd when options carry none.
        cwd = str(self.base_options.cwd or Path.cwd())
        return get_typed_config("pipeline.background_idle_timeout_s", int, cwd=cwd)

    async def _stop_background(self, turns: DispatchTurns, idle_s: float) -> None:
        """Stop every tracked agent after an idle timeout, best-effort (D5)."""
        ids = turns.ledger.active_ids()
        descriptions = turns.ledger.descriptions()
        for task_id in ids:
            try:
                await self.client.stop_task(task_id)
            except Exception:  # noqa: BLE001
                # The SDK raises a bare Exception both when the stop control
                # request times out (60s) and when the CLI returns an error,
                # so no narrower type exists. Stopping is cleanup: log and go
                # on to the next id. A late follow-up turn is handled by D6.
                _logger.exception("dispatch: failed to stop background task %s", task_id)
        # Clear locally: a lost terminal signal is exactly the case here.
        turns.ledger.clear()
        self.background_tasks_stopped = len(ids)
        _logger.warning(
            "dispatch: no activity for %ds with background agent(s) still running; stopped: %s",
            idle_s,
            descriptions,
        )

    async def capture_summary(
        self,
        instructions: str,
        summary_model: str | None = None,
        restore_model: str | None = None,
    ) -> str:
        """Generate a summary of the live session without rotating.

        Switches to summary_model if provided, dispatches instructions,
        captures the response as the summary, optionally restores the
        prior model, and returns the summary text. Does NOT disconnect
        the client or create a new session.
        """
        if summary_model is not None and summary_model != self.current_model:
            await self.set_model(summary_model)
        _logger.debug("SDKExecutionSession.capture_summary: dispatching instructions")
        summary = await self.dispatch(instructions)
        if restore_model is not None and restore_model != self.current_model:
            await self.set_model(restore_model)
        return summary

    async def compact(
        self,
        instructions: str,
        summary_model: str | None = None,
        restore_model: str | None = None,
        summary: str | None = None,
    ) -> str:
        """Perform session-rotate compaction. Returns the summary text.

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
        self._require_usable()
        if summary is None:
            summary = await self.capture_summary(
                instructions, summary_model=summary_model, restore_model=None
            )

        await self._reconnect(summary, SeedSource.COMPACT)

        if restore_model is not None:
            await self.set_model(restore_model)

        return summary

    async def seed_context(self, text: str, source: SeedSource) -> None:
        """Replace the session with a fresh one seeded with ``text``.

        Any history since the last rotation is dropped. The caller passes
        raw text; framing happens in ``_seeded_options``. No turn is sent.
        """
        self._require_usable()
        await self._reconnect(text, source)

    def _require_usable(self) -> None:
        """Raise if an earlier reconnect failed and left no live client."""
        if self.unusable_reason is not None:
            raise ProviderError(f"SDK session unusable: {self.unusable_reason}")

    async def _reconnect(self, seed: str | None, source: SeedSource) -> None:
        """Disconnect and connect a fresh client seeded via the system prompt."""
        await self.disconnect()
        self.client = ClaudeSDKClient(options=_seeded_options(self.base_options, seed))
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
        PIPELINE_SETTING_SOURCES,
        auto_memory=get_typed_config("pipeline.auto_memory", bool, cwd=cwd),
    )
    base = ClaudeAgentOptions(
        cwd=cwd,
        permission_mode="bypassPermissions",
        system_prompt={"type": "preset", "preset": "claude_code"},
        setting_sources=settings["setting_sources"],  # pyright: ignore[reportArgumentType]
        env=settings["env"],
    )
    client = ClaudeSDKClient(options=_seeded_options(base, seed))
    session = SDKExecutionSession(client=client, base_options=base, seeded=seed is not None)
    await session.connect()
    return session
