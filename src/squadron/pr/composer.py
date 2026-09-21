"""The one-shot composer for ``sq pr create`` (D3).

Prompt in, text out, through a profile. The composer is small because it
does one thing: it is not shaped like ``summary_oneshot`` (pipeline-shaped
parameters) or ``run_review_with_profile`` (review-shaped template and
result parsing) — PR composition wants neither.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from squadron.core.models import SDK_RESULT_TYPE

_logger = logging.getLogger(__name__)

#: ``sdk_type`` values whose messages are not response prose: the SDK's
#: duplicate ResultMessage and its tool-call narration. The same set
#: ``run_review_with_profile`` and ``summary_oneshot`` skip.
_NON_PROSE_SDK_TYPES = (SDK_RESULT_TYPE, "tool_use", "tool_result")

Composer = Callable[[str], Awaitable[str]]

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
    from squadron.tools import resolve_effective_tools

    try:
        provider_profile = get_profile(profile)
        ensure_provider_loaded(provider_profile.provider)
        provider = get_provider(provider_profile.provider)

        # Declares no tools, so the gate always answers ([], None) here — but
        # every AgentConfig site with an allowed_tools keyword must route
        # through it regardless, per the project's tool-passing enforcement
        # (tests/tools/test_effective_tools.py, SC1a): a raw list bypasses the
        # model's tool_use capability check on any other path that changes.
        effective_tools, tools_suppressed_reason = resolve_effective_tools(
            _NO_TOOLS, model_allows_tools=True, suppressed=False
        )

        config = AgentConfig(
            name="pr-create-body",
            agent_type=provider_profile.provider,
            provider=provider_profile.provider,
            model=model,
            instructions="",
            api_key=None,
            base_url=provider_profile.base_url,
            cwd=None,
            allowed_tools=effective_tools,
            tools_suppressed_reason=tools_suppressed_reason,
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
                # SDK providers emit both an AssistantMessage and a
                # ResultMessage with identical content (skip the duplicate),
                # plus tool_use/tool_result narration that is not prose —
                # non-SDK providers never set sdk_type and are unaffected.
                if response.metadata.get("sdk_type") in _NON_PROSE_SDK_TYPES:
                    continue
                output_parts.append(response.content)
        finally:
            await agent.shutdown()
    except Exception as exc:
        _logger.exception("sq pr create: composition failed via profile %r", profile)
        raise CompositionError(f"Failed to compose the PR body via profile {profile!r}: {exc}") from exc

    return "\n".join(output_parts)
