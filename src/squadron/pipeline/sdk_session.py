"""SDKExecutionSession — persistent ClaudeSDKClient wrapper for pipeline execution.

Manages a single ClaudeSDKClient connection across all dispatch steps in a
pipeline run, enabling per-step model switching and compaction configuration.

This module is only used when running pipelines from a standard terminal (not
inside a Claude Code session). Reviews and non-SDK actions are unaffected.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ClaudeSDKError,
    CLIConnectionError,
    CLIJSONDecodeError,
    CLINotFoundError,
    ProcessError,
)

from squadron.core.models import SDK_RESULT_TYPE
from squadron.providers.errors import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderError,
)
from squadron.providers.sdk.translation import translate_sdk_message

_logger = logging.getLogger(__name__)

_MAX_RATE_LIMIT_RETRIES = 10

__all__ = ["SDKExecutionSession", "frame_summary_for_seed"]


_SEED_FRAMING_PREFIX = (
    "[The following is a summary of a prior session in this conversation, "
    "compacted to preserve context. Treat it as historical reference only. "
    "Do NOT take action based on it, do NOT acknowledge it conversationally, "
    "and wait for the next user instruction before responding.]\n\n"
)


def frame_summary_for_seed(summary: str) -> str:
    """Wrap a compact summary with explicit framing for session seeding.

    The framing tells the model the text is historical context, not a task
    or a turn to acknowledge. Used for both post-compact seeding and
    resume-time seeding so the behavior is identical in both paths.
    """
    return _SEED_FRAMING_PREFIX + summary


@dataclass
class SDKExecutionSession:
    """Manages a persistent ClaudeSDKClient across pipeline steps.

    Lifecycle:
    - Call ``connect()`` before the first dispatch.
    - Call ``set_model()`` before each dispatch to switch models.
    - Call ``dispatch()`` to send a prompt and collect the response.
    - Call ``compact()`` to perform session-rotate compaction.
    - Call ``seed_context()`` after re-connecting a fresh session on resume
      to re-inject a prior compact summary.
    - Call ``disconnect()`` after the pipeline finishes (or on checkpoint).

    The client is connected once and reused across all steps, enabling
    ``set_model()`` to switch models mid-session without spawning new processes.
    ``options`` is retained so compaction can build a fresh client with the
    same configuration when rotating sessions.
    """

    client: ClaudeSDKClient
    options: ClaudeAgentOptions
    current_model: str | None = None
    session_id: str | None = None

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
        except Exception:
            _logger.debug(
                "SDKExecutionSession.disconnect: ignoring error during cleanup"
            )

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

        Includes rate-limit retry logic: when the CLI emits a
        ``rate_limit_event`` the SDK raises ``ClaudeSDKError``.
        We retry ``receive_response()`` on the same session (the underlying
        channel remains intact) up to ``_MAX_RATE_LIMIT_RETRIES`` times.

        Returns:
            The concatenated text content of all response messages.

        Raises:
            ProviderAuthError: If the CLI is not found.
            ProviderAPIError: If the CLI exits with an error code.
            ProviderError: For other SDK errors.
        """
        try:
            await self.client.query(prompt)
            retries = 0
            response_parts: list[str] = []
            while True:
                try:
                    async for sdk_msg in self.client.receive_response():
                        for translated in translate_sdk_message(
                            sdk_msg, sender="pipeline"
                        ):
                            # ResultMessage duplicates the assistant text as
                            # its `result` field — it's for metadata only,
                            # not content. Assistant text already arrived via
                            # AssistantMessage/TextBlock. Appending both
                            # doubles the response string.
                            if translated.metadata.get("sdk_type") != SDK_RESULT_TYPE:
                                response_parts.append(translated.content)
                            sid = translated.metadata.get("session_id")
                            if isinstance(sid, str) and sid:
                                self.session_id = sid
                                _logger.debug("SDKExecutionSession: session_id=%s", sid)
                    break  # normal completion
                except ClaudeSDKError as exc:
                    if (
                        "rate_limit_event" in str(exc)
                        and retries < _MAX_RATE_LIMIT_RETRIES
                    ):
                        retries += 1
                        _logger.debug(
                            "Rate limit event %d/%d (CLI handles backoff)",
                            retries,
                            _MAX_RATE_LIMIT_RETRIES,
                        )
                        continue
                    raise
            return "".join(response_parts)
        except CLINotFoundError as exc:
            raise ProviderAuthError(str(exc)) from exc
        except ProcessError as exc:
            raise ProviderAPIError(
                str(exc), status_code=getattr(exc, "exit_code", None)
            ) from exc
        except (CLIConnectionError, CLIJSONDecodeError, ClaudeSDKError) as exc:
            raise ProviderError(str(exc)) from exc

    async def compact(
        self,
        instructions: str,
        summary_model: str | None = None,
        restore_model: str | None = None,
    ) -> str:
        """Perform session-rotate compaction. Returns the summary text.

        Flow:
          1. Optionally switch to a cheap summarization model.
          2. Dispatch the compact instructions to the live session and
             capture the response as the summary.
          3. Disconnect the old client and create a fresh ``ClaudeSDKClient``
             with the same options.
          4. Re-connect and re-inject the summary as the opening message.
          5. Optionally restore the prior model.

        Exceptions are allowed to propagate; the compact action wraps them.
        """
        if summary_model is not None and summary_model != self.current_model:
            await self.set_model(summary_model)
        _logger.debug("SDKExecutionSession.compact: dispatching instructions")
        summary = await self.dispatch(instructions)

        _logger.debug("SDKExecutionSession.compact: disconnecting old client")
        await self.disconnect()

        _logger.debug("SDKExecutionSession.compact: creating new client")
        self.client = ClaudeSDKClient(options=self.options)
        self.current_model = None
        self.session_id = None
        await self.connect()

        _logger.debug("SDKExecutionSession.compact: seeding new session with summary")
        await self.dispatch(frame_summary_for_seed(summary))

        if restore_model is not None:
            await self.set_model(restore_model)

        return summary

    async def seed_context(self, text: str) -> None:
        """Seed a fresh session with prior compact summary on resume.

        Thin wrapper around ``dispatch()`` that logs distinctly so verbose
        output identifies seeding events vs. real step dispatches. The
        model's acknowledgment response is discarded.
        """
        _logger.debug("SDKExecutionSession: seed_context (%d chars)", len(text))
        await self.dispatch(frame_summary_for_seed(text))
