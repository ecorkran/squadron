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
        cwd=None,
        allowed_tools=[],
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
    raw_output = ""
    try:
        message = Message(
            sender="summary-system",
            recipients=[config.name],
            content=instructions,
            message_type=MessageType.chat,
        )
        async for response in agent.handle_message(message):
            if response.metadata.get("sdk_type") == SDK_RESULT_TYPE:
                continue
            raw_output += response.content
    finally:
        await agent.shutdown()

    return raw_output
