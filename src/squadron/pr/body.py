"""The one-shot composer and body assembly for ``sq pr create`` (D3, D4, D5).

Prompt in, text out, through a profile. The composer is small because it
does one thing: it is not shaped like ``summary_oneshot`` (pipeline-shaped
parameters) or ``run_review_with_profile`` (review-shaped template and
result parsing) — PR composition wants neither.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from pathlib import Path

from squadron.review.git_utils import CommitRecord

_logger = logging.getLogger(__name__)

#: The design document's own heading: ``# Slice Design: {name}``. Only this
#: exact shape yields a title (D4a); anything else falls through to the
#: model rather than emitting a malformed title.
_DESIGN_H1_RE = re.compile(r"^#\s+Slice Design:\s*(.+?)\s*$", re.MULTILINE)

#: The bound on a model-composed title — the project's own commit-summary
#: convention, applied to the same kind of object (D4a).
_TITLE_MAX_CHARS = 72

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


async def resolve_title(
    *,
    title_flag: str | None,
    slice_design_file: str | None,
    commits: tuple[CommitRecord, ...],
    compose: Composer,
) -> str:
    """Resolve the PR title per D4a's three-term table.

    1. ``--title`` given: use it verbatim.
    2. A resolved slice branch whose design carries a matching H1: the
       design's own human name, minus the ``Slice Design: `` prefix. Makes
       no model call — the slice is already named.
    3. Otherwise: the model composes one line under 72 characters from the
       commit subjects alone. A response that is empty, multi-line, or over
       the bound falls back to the first commit's subject — always present,
       always truthful, and the slice's one deliberate degradation.
    """
    if title_flag is not None:
        return title_flag

    if slice_design_file is not None:
        human_name = _read_design_h1(slice_design_file)
        if human_name is not None:
            return human_name

    return await _compose_title(commits, compose)


def _read_design_h1(design_file: str) -> str | None:
    """The design's ``# Slice Design: {name}`` heading, or None if absent/mismatched."""
    try:
        text = Path(design_file).read_text(encoding="utf-8")
    except OSError:
        return None
    match = _DESIGN_H1_RE.search(text)
    if match is None:
        return None
    name = match.group(1).strip()
    return name or None


async def _compose_title(commits: tuple[CommitRecord, ...], compose: Composer) -> str:
    """The model-composed title, falling back to the first commit's subject."""
    fallback = commits[0].subject if commits else ""
    subjects = "\n".join(f"- {commit.subject}" for commit in commits)
    prompt = (
        "Write one pull-request title, under 72 characters, for a PR whose "
        f"commits are:\n\n{subjects}\n\nRespond with only the title line."
    )
    response = await compose(prompt)
    candidate = response.strip()
    if not candidate or "\n" in candidate or len(candidate) > _TITLE_MAX_CHARS:
        return fallback
    return candidate
