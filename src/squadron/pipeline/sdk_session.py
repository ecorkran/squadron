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

from squadron.core.models import (
    RATE_LIMIT_EVENT_TYPE,
    SDK_RESULT_TYPE,
    TOOL_RESULT_TYPE,
    TOOL_USE_TYPE,
)
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
from squadron.providers.sdk.translation import translate_sdk_message

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

        Includes rate-limit retry logic: a ``rejected`` ``RateLimitEvent``
        raises ``RateLimitRejected`` inline in the loop below (this path has
        no ``_skip_unparseable`` wrapper, unlike ``agent.py``). We retry
        ``receive_response()`` on the same session (the underlying channel
        remains intact) up to ``MAX_RATE_LIMIT_RETRIES`` times.

        Returns:
            The concatenated text content of all response messages.

        Raises:
            ProviderAuthError: If the CLI is not found.
            ProviderAPIError: If the CLI exits with an error code.
            ProviderError: For other SDK errors, or if the session is unusable.
        """
        self._require_usable()
        try:
            await self.client.query(prompt)
            retries = 0
            response_parts: list[str] = []
            while True:
                progressed = False
                try:
                    async for sdk_msg in self.client.receive_response():
                        # No _skip_unparseable wrapper on this path (unlike
                        # agent.py), so a RateLimitEvent must be inspected
                        # here, inline, before anything else touches it —
                        # and before `progressed` is set, so a rejected
                        # event as the very first message correctly
                        # consumes retry budget instead of resetting it
                        # (a rejected event is not progress).
                        if isinstance(sdk_msg, RateLimitEvent) and event_blocks(sdk_msg):
                            raise RateLimitRejected(
                                f"rate_limit_event status={sdk_msg.rate_limit_info.status!r}"
                            )
                        progressed = True
                        # Raise before appending any content so no partial
                        # error text reaches the caller or _check_cli_error.
                        if isinstance(sdk_msg, ResultMessage) and sdk_msg.is_error:
                            raise ProviderAPIError(
                                f"SDK reported is_error=True: {sdk_msg.result or sdk_msg.subtype}"
                            )
                        for translated in translate_sdk_message(sdk_msg, sender="pipeline"):
                            sdk_type = translated.metadata.get("sdk_type")
                            # ResultMessage duplicates the assistant text as
                            # its `result` field — it's for metadata only,
                            # not content. Assistant text already arrived via
                            # AssistantMessage/TextBlock. Appending both
                            # doubles the response string. tool_use/tool_result
                            # messages narrate the agent's tool calls (e.g.
                            # "Using tool: Bash", command stdout) and are not
                            # part of the response's actual prose — mixing
                            # them in with no separator produced an
                            # unreadable, unparseable run-on line (issue #23,
                            # same class of bug as #22/#20). An informational
                            # RateLimitEvent is now observable (translation.py)
                            # rather than silently dropped, but it is a
                            # usage-meter notice, not response prose, so it
                            # is excluded here the same way.
                            if sdk_type not in (
                                SDK_RESULT_TYPE,
                                TOOL_USE_TYPE,
                                TOOL_RESULT_TYPE,
                                RATE_LIMIT_EVENT_TYPE,
                            ):
                                response_parts.append(translated.content)
                            sid = translated.metadata.get("session_id")
                            if isinstance(sid, str) and sid:
                                self.session_id = sid
                                _logger.debug("SDKExecutionSession: session_id=%s", sid)
                    break  # normal completion
                except ClaudeSDKError as exc:
                    # A RateLimitEvent with status='rejected' raises
                    # RateLimitRejected above; a genuine 429 can also
                    # surface as a plain ClaudeSDKError. is_throttle
                    # classifies both. Informational events are not
                    # exceptions at all — they are yielded through the
                    # `async for` like any other message and never reach
                    # this handler.
                    #
                    # A throttle after work came
                    # through is a fresh event, so the budget bounds
                    # consecutive failures rather than throttles-per-run.
                    if progressed:
                        retries = 0
                    if is_throttle(exc) and retries < MAX_RATE_LIMIT_RETRIES:
                        retries += 1
                        delay = rate_limit_backoff_s(retries)
                        _logger.warning(
                            "Rate limited (attempt %d/%d); waiting %.0fs before retry.",
                            retries,
                            MAX_RATE_LIMIT_RETRIES,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise
            return "\n".join(response_parts)
        except CLINotFoundError as exc:
            raise ProviderAuthError(str(exc)) from exc
        except ProcessError as exc:
            raise ProviderAPIError(str(exc), status_code=getattr(exc, "exit_code", None)) from exc
        except (CLIConnectionError, CLIJSONDecodeError, ClaudeSDKError) as exc:
            raise ProviderError(str(exc)) from exc

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
    as a turn.
    """
    base = ClaudeAgentOptions(
        cwd=str(Path.cwd()),
        permission_mode="bypassPermissions",
        system_prompt={"type": "preset", "preset": "claude_code"},
    )
    client = ClaudeSDKClient(options=_seeded_options(base, seed))
    session = SDKExecutionSession(client=client, base_options=base)
    await session.connect()
    return session
