"""One-shot summary execution for non-SDK provider profiles.

Provides `capture_summary_via_profile()` (mirrors the pattern from
`run_review_with_profile()`) used to dispatch summary actions through
non-SDK providers. Profile-routing predicates live in
`squadron.providers.profiles`.
"""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)

__all__ = ["capture_summary_via_profile", "capture_summary_via_profile_with_telemetry"]


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

    Callers that also need tool-use telemetry use
    :func:`capture_summary_via_profile_with_telemetry`; this signature is unchanged for
    the `sq summary` CLI path, which has nowhere to put the extra value.
    """
    text, _ = await capture_summary_via_profile_with_telemetry(
        instructions=instructions,
        model_id=model_id,
        profile=profile,
        allowed_tools=allowed_tools,
        cwd=cwd,
    )
    return text


async def capture_summary_via_profile_with_telemetry(
    *,
    instructions: str,
    model_id: str | None,
    profile: str,
    allowed_tools: list[str] | None = None,
    cwd: str | None = None,
) -> tuple[str, dict[str, object]]:
    """Run the one-shot summary and return its text alongside tool-use telemetry.

    The telemetry dict is empty when the run had no tools, so a caller can splat it into
    ``ActionResult.metadata`` without inventing keys (design D5).
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
    telemetry: dict[str, object] = {}
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
            # Read before the filter below: the message carrying telemetry can be one this
            # loop skips for prose.
            given = response.metadata.get("tools_given")
            if given is not None:
                telemetry["tools_given"] = given
                telemetry["tool_calls_made"] = response.metadata.get("tool_calls_made", 0)
            if sdk_type in (SDK_RESULT_TYPE, "tool_use", "tool_result"):
                continue
            output_parts.append(response.content)
    finally:
        await agent.shutdown()

    return "\n".join(output_parts), telemetry
