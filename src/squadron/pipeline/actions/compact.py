"""Compact action — reduces context via the best available mechanism.

True CLI (sdk_session present): delegates to SDKExecutionSession.compact(),
which captures a summary, rotates to a fresh session, and seeds the summary back.

Prompt-only (sdk_session absent): dispatches /compact via claude_agent_sdk.query()
and awaits SystemMessage(subtype="compact_boundary") before returning.
"""

from __future__ import annotations

import asyncio
import datetime
import logging

import claude_agent_sdk
from claude_agent_sdk import SystemMessage

from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError

_logger = logging.getLogger(__name__)

_DEFAULT_COMPACT_TIMEOUT_S = 120

__all__ = ["CompactAction"]


class CompactAction:
    """Pipeline action that reduces the current session's context."""

    @property
    def action_type(self) -> str:
        return ActionType.COMPACT

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        errors: list[ValidationError] = []
        instructions = config.get("instructions")
        if instructions is not None and not isinstance(instructions, str):
            errors.append(
                ValidationError(
                    field="instructions",
                    message="'instructions' must be a string",
                    action_type=self.action_type,
                )
            )
        model = config.get("model")
        if model is not None and not isinstance(model, str):
            errors.append(
                ValidationError(
                    field="model",
                    message="'model' must be a string",
                    action_type=self.action_type,
                )
            )
        return errors

    async def execute(self, context: ActionContext) -> ActionResult:
        instructions_raw = context.params.get("instructions")
        instructions = str(instructions_raw) if instructions_raw is not None else ""

        if context.sdk_session is not None:
            return await self._execute_sdk_rotate(context, instructions)
        return await self._execute_prompt_only(context, instructions)

    async def _execute_sdk_rotate(
        self, context: ActionContext, instructions: str
    ) -> ActionResult:
        """True CLI: rotate the session via SDKExecutionSession.compact()."""
        model_raw = context.params.get("model")
        summary_model = str(model_raw) if model_raw is not None else None
        restore_model = context.sdk_session.current_model  # type: ignore[union-attr]

        try:
            await context.sdk_session.compact(  # type: ignore[union-attr]
                instructions=instructions,
                summary_model=summary_model,
                restore_model=restore_model,
            )
        except Exception as exc:
            _logger.exception(
                "CompactAction: sdk rotate failed in step %s", context.step_name
            )
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=str(exc),
            )

        return ActionResult(
            success=True,
            action_type=self.action_type,
            outputs={},
        )

    async def _execute_prompt_only(
        self, context: ActionContext, instructions: str
    ) -> ActionResult:
        """Prompt-only: dispatch /compact via query() and await compact_boundary."""
        prompt = "/compact"
        if instructions:
            prompt = f"/compact {instructions}"

        timeout_s = _DEFAULT_COMPACT_TIMEOUT_S
        timeout_raw = context.params.get("_compact_timeout_s")
        if isinstance(timeout_raw, (int, float)):
            timeout_s = float(timeout_raw)

        pre_tokens: int | None = None
        trigger: str | None = None

        try:

            async def _await_boundary() -> None:
                nonlocal pre_tokens, trigger
                async for message in claude_agent_sdk.query(
                    prompt=prompt,
                    options=claude_agent_sdk.ClaudeAgentOptions(max_turns=1),
                ):
                    if (
                        isinstance(message, SystemMessage)
                        and message.subtype == "compact_boundary"
                    ):
                        meta = message.data.get("compact_metadata", {})
                        pre_tokens = meta.get("pre_tokens")
                        trigger = meta.get("trigger")
                        _logger.debug(
                            "CompactAction: compact_boundary received "
                            "pre_tokens=%s trigger=%s",
                            pre_tokens,
                            trigger,
                        )
                        return

            await asyncio.wait_for(_await_boundary(), timeout=timeout_s)
        except TimeoutError as exc:
            raise TimeoutError(
                f"CompactAction: compact_boundary not received within {timeout_s}s"
            ) from exc
        except Exception as exc:
            _logger.exception(
                "CompactAction: prompt-only compact failed in step %s",
                context.step_name,
            )
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=str(exc),
            )

        compacted_at = datetime.datetime.now(tz=datetime.UTC).isoformat()
        return ActionResult(
            success=True,
            action_type=self.action_type,
            outputs={
                "pre_tokens": pre_tokens,
                "trigger": trigger,
                "compacted_at": compacted_at,
            },
        )


register_action(ActionType.COMPACT, CompactAction())
