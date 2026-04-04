"""SDKExecutionSession — persistent ClaudeSDKClient wrapper for pipeline execution.

Manages a single ClaudeSDKClient connection across all dispatch steps in a
pipeline run, enabling per-step model switching and compaction configuration.

This module is only used when running pipelines from a standard terminal (not
inside a Claude Code session). Reviews and non-SDK actions are unaffected.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeSDKError,
    CLIConnectionError,
    CLIJSONDecodeError,
    CLINotFoundError,
    ProcessError,
)

from squadron.providers.errors import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderError,
)
from squadron.providers.sdk.translation import translate_sdk_message

_logger = logging.getLogger(__name__)

_MAX_RATE_LIMIT_RETRIES = 10

__all__ = ["SDKExecutionSession"]


@dataclass
class SDKExecutionSession:
    """Manages a persistent ClaudeSDKClient across pipeline steps.

    Lifecycle:
    - Call ``connect()`` before the first dispatch.
    - Call ``set_model()`` before each dispatch to switch models.
    - Call ``dispatch()`` to send a prompt and collect the response.
    - Call ``configure_compaction()`` before a compact step to set up
      server-side compaction on the next query.
    - Call ``disconnect()`` after the pipeline finishes (or on checkpoint).

    The client is connected once and reused across all steps, enabling
    ``set_model()`` to switch models mid-session without spawning new processes.
    """

    client: ClaudeSDKClient
    current_model: str | None = None
    _compaction_config: dict[str, object] | None = field(default=None, repr=False)

    async def connect(self) -> None:
        """Connect the underlying SDK client."""
        await self.client.connect()

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
                            response_parts.append(translated.content)
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

    def configure_compaction(
        self,
        instructions: str,
        trigger_tokens: int,
        pause_after: bool,
    ) -> None:
        """Store compaction config to be applied on the next dispatch.

        The config is stored and consumed by the compact action pathway.
        Actual compaction occurs at the API level when the next query fires.

        Args:
            instructions: Rendered compaction instructions from the compact template.
            trigger_tokens: Token threshold that triggers compaction.
            pause_after: Whether to pause after compaction for state injection.
        """
        self._compaction_config = {
            "instructions": instructions,
            "trigger_tokens": trigger_tokens,
            "pause_after": pause_after,
        }
        _logger.debug(
            "SDKExecutionSession: compaction configured (trigger=%d, pause=%s)",
            trigger_tokens,
            pause_after,
        )
