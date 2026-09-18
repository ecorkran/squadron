"""The one-shot composer and body assembly for ``sq pr create`` (D3, D4, D5).

Prompt in, text out, through a profile. The composer is small because it
does one thing: it is not shaped like ``summary_oneshot`` (pipeline-shaped
parameters) or ``run_review_with_profile`` (review-shaped template and
result parsing) — PR composition wants neither.
"""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)

#: The model is given facts only, per initiative 360's traceability rule: a
#: description-writer with tools could assert things no input supports.
_NO_TOOLS: list[str] = []


class CompositionError(Exception):
    """The one-shot model call failed.

    Not a ``CodeHostError`` — the composer is its own I/O path, not a
    host call, and its failures are enumerated separately (D8's sixth path).
    """


async def compose_one_shot(prompt: str, *, model: str | None, profile: str) -> str:
    """Run one prompt through *profile* and return the response text.

    Performs the same sequence ``run_review_with_profile`` uses —
    ``get_profile`` → ``ensure_provider_loaded`` → ``get_provider`` → an
    ``AgentConfig`` → ``create_agent`` → ``handle_message`` — without any of
    that function's review-shaped parameters, and without
    ``summary_oneshot``'s pipeline-shaped ones (D3).

    Every failure — an unreachable or unauthenticated provider, a mid-stream
    timeout, or any exception from ``handle_message`` — is caught at this
    boundary, logged at ERROR, and re-raised as ``CompositionError``: the
    sixth I/O path D8 enumerates, distinct from the five ``CodeHostError``
    paths. This is a process-boundary handler in the project's exception
    rules' sense, which is what permits catching broadly here.
    """
    from squadron.core.models import AgentConfig, Message, MessageType
    from squadron.providers.loader import ensure_provider_loaded
    from squadron.providers.profiles import get_profile
    from squadron.providers.registry import get_provider

    try:
        provider_profile = get_profile(profile)
        ensure_provider_loaded(provider_profile.provider)
        provider = get_provider(provider_profile.provider)

        config = AgentConfig(
            name="pr-create-body",
            agent_type=provider_profile.provider,
            provider=provider_profile.provider,
            model=model,
            instructions="",
            api_key=None,
            base_url=provider_profile.base_url,
            cwd=None,
            allowed_tools=_NO_TOOLS,
            permission_mode="default",
            setting_sources=[],
            credentials={
                "api_key_env": provider_profile.api_key_env,
                "default_headers": provider_profile.default_headers,
                "hooks": [],
                "mode": "client",
            },
        )

        agent = await provider.create_agent(config)
        output_parts: list[str] = []
        try:
            message = Message(
                sender="pr-create-system",
                recipients=[config.name],
                content=prompt,
                message_type=MessageType.chat,
            )
            async for response in agent.handle_message(message):
                output_parts.append(response.content)
        finally:
            await agent.shutdown()
    except Exception as exc:
        _logger.exception("sq pr create: composition failed via profile %r", profile)
        raise CompositionError(f"Failed to compose the PR body via profile {profile!r}: {exc}") from exc

    return "\n".join(output_parts)
