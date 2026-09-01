"""One-shot summary execution for non-SDK provider profiles.

Provides `capture_summary_via_profile()` (mirrors the pattern from
`run_review_with_profile()`) used to dispatch summary actions through
non-SDK providers. Profile-routing predicates live in
`squadron.providers.profiles`.
"""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)

__all__ = ["capture_summary_via_profile"]


async def capture_summary_via_profile(
    *,
    instructions: str,
    model_id: str | None,
    profile: str,
    allowed_tools: list[str] | None = None,
    cwd: str | None = None,
) -> str:
    """Execute a one-shot summary call through the specified provider profile.

    Mirrors the shape of `run_review_with_profile()` with review-specific
    branches removed: no structured-output injection, no rules, no file
    injection, no parsing — returns the raw concatenated response string.
    """
    from squadron.core.models import SDK_RESULT_TYPE, AgentConfig, Message, MessageType
    from squadron.providers.loader import ensure_provider_loaded
    from squadron.providers.profiles import get_profile
    from squadron.providers.registry import get_provider

    provider_profile = get_profile(profile)
    ensure_provider_loaded(provider_profile.provider)
    provider = get_provider(provider_profile.provider)

    config = AgentConfig(
        name="summary-oneshot",
        agent_type=provider_profile.provider,
        provider=provider_profile.provider,
        model=model_id,
        instructions="",
        api_key=None,
        base_url=provider_profile.base_url,
        # A tool-capable agent needs a working directory to jail its tools to; both stay
        # at today's no-tools defaults when the step declares nothing (slice 265).
        cwd=cwd if allowed_tools else None,
        allowed_tools=allowed_tools if allowed_tools is not None else [],
        permission_mode="default",
        setting_sources=[],
        credentials={
            "api_key_env": provider_profile.api_key_env,
            "default_headers": provider_profile.default_headers,
            "hooks": [],
            "mode": "client",
        },
    )

    _logger.info(
        "Summary via %s (provider=%s, model=%s)",
        profile,
        provider_profile.provider,
        model_id or "(default)",
    )

    agent = await provider.create_agent(config)
    output_parts: list[str] = []
    try:
        message = Message(
            sender="summary-system",
            recipients=[config.name],
            content=instructions,
            message_type=MessageType.chat,
        )
        async for response in agent.handle_message(message):
            sdk_type = response.metadata.get("sdk_type")
            # SDK providers emit both an AssistantMessage and a ResultMessage
            # with identical content (skip the duplicate), plus separate
            # tool_use/tool_result messages narrating the agent's tool calls
            # that are not part of the summary's actual prose — non-SDK
            # providers never set sdk_type and are unaffected by this filter.
            if sdk_type in (SDK_RESULT_TYPE, "tool_use", "tool_result"):
                continue
            output_parts.append(response.content)
    finally:
        await agent.shutdown()

    return "\n".join(output_parts)
