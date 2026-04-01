"""Dispatch action — send assembled context to a model via agent registry."""

from __future__ import annotations

import logging

from squadron.core.agent_registry import get_registry
from squadron.core.models import AgentConfig, Message, MessageType
from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError
from squadron.pipeline.resolver import ModelPoolNotImplemented, ModelResolutionError
from squadron.providers.base import ProfileName
from squadron.providers.loader import ensure_provider_loaded
from squadron.providers.profiles import get_profile

_logger = logging.getLogger(__name__)


class DispatchAction:
    """Pipeline action that dispatches a prompt to a language model.

    Resolves model alias via 5-level cascade, creates a one-shot agent,
    sends the prompt, captures the response with metadata.
    """

    @property
    def action_type(self) -> str:
        return ActionType.DISPATCH

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        if "prompt" not in config:
            return [
                ValidationError(
                    field="prompt",
                    message="'prompt' is required for dispatch action",
                    action_type=ActionType.DISPATCH,
                )
            ]
        return []

    async def execute(self, context: ActionContext) -> ActionResult:
        try:
            return await self._dispatch(context)
        except (
            ModelResolutionError,
            ModelPoolNotImplemented,
            KeyError,
            Exception,
        ) as exc:
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=str(exc),
            )

    async def _dispatch(self, context: ActionContext) -> ActionResult:
        # Model resolution
        action_model = (
            str(context.params["model"]) if "model" in context.params else None
        )
        step_model = (
            str(context.params["step_model"])
            if "step_model" in context.params
            else None
        )
        model_id, alias_profile = context.resolver.resolve(action_model, step_model)

        # Profile resolution
        profile_name = (
            str(context.params["profile"])
            if "profile" in context.params
            else alias_profile or ProfileName.SDK
        )

        # Build agent config
        profile = get_profile(profile_name)
        ensure_provider_loaded(profile.provider)

        config = AgentConfig(
            name=f"dispatch-{context.step_name}-{context.run_id[:8]}",
            agent_type=profile.provider,
            provider=profile.provider,
            model=model_id,
            instructions=str(context.params.get("system_prompt", "")),
            base_url=profile.base_url,
            cwd=context.cwd,
            credentials={
                "api_key_env": profile.api_key_env,
                "default_headers": profile.default_headers,
            },
        )

        # Spawn agent, dispatch, and collect response
        registry = get_registry()
        agent = await registry.spawn(config)
        try:
            message = Message(
                sender="pipeline",
                recipients=[config.name],
                content=str(context.params["prompt"]),
                message_type=MessageType.chat,
            )
            response_parts: list[str] = []
            token_metadata: dict[str, object] = {}
            async for response in agent.handle_message(message):
                if response.metadata.get("sdk_type") == "result":
                    continue
                response_parts.append(response.content)
                for key in (
                    "prompt_tokens",
                    "completion_tokens",
                    "total_tokens",
                ):
                    if key in response.metadata:
                        token_metadata[key] = response.metadata[key]
        finally:
            await registry.shutdown_agent(config.name)

        response_text = "".join(response_parts)
        return ActionResult(
            success=True,
            action_type=self.action_type,
            outputs={"response": response_text},
            metadata={
                "model": model_id,
                "profile": profile_name,
                **token_metadata,
            },
        )


register_action(ActionType.DISPATCH, DispatchAction())
