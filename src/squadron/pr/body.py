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
from dataclasses import dataclass
from pathlib import Path

from squadron.pr.assembly import PrFacts
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


# --- The section contract (D4) ----------------------------------------------

#: The no-input line shared by "how it was verified" and "known gaps" —
#: both derive from the task file (D4).
_NO_TASK_RECORDS = "No task records for this branch."

#: The no-input line for "review provenance" (D4).
_NO_REVIEW = "No squadron review covers this branch's commits."


@dataclass(frozen=True)
class _Section:
    """One heading in the fixed, ordered section contract (D4).

    ``has_input`` and ``deterministic_block`` are functions of the facts
    alone — no section is ever asked for prose when its own no-input line
    applies, and the deterministic block is what a reader checks prose
    against, so it must never be generated by the model.
    """

    heading: str
    no_input_line: str
    has_input: Callable[[PrFacts], bool]
    deterministic_block: Callable[[PrFacts], str]
    prompt: Callable[[PrFacts], str]


def _what_changed_block(facts: PrFacts) -> str:
    lines = [f"- {commit.sha[:12]} {commit.subject}" for commit in facts.commits]
    return "\n".join(lines)


def _why_block(facts: PrFacts) -> str:
    return f"Slice design: {facts.slice_design_file}" if facts.slice_design_file else ""


#: A bound on how much of the design document reaches the prompt. The model
#: gets facts only (D3's traceability rule) — the full document, not a
#: guess at its content, but capped so one large design doesn't dominate
#: the one-shot budget the way an unbounded read would.
_DESIGN_EXCERPT_MAX_CHARS = 6000


def _read_design_excerpt(facts: PrFacts) -> str:
    """The design document's own text, or "" when absent or unreadable.

    Without this, a prompt that only *names* the design's path gives the
    model nothing to read — it has no tools (D3) and no way to open the
    file itself, so a path-only prompt reliably produces a refusal
    ("I don't have access to your files") instead of prose about the
    change. The model must be handed the content directly.
    """
    if facts.slice_design_file is None:
        return ""
    try:
        text = Path(facts.slice_design_file).read_text(encoding="utf-8")
    except OSError:
        _logger.warning(
            "sq pr create: could not read slice design %s for composition", facts.slice_design_file
        )
        return ""
    return text[:_DESIGN_EXCERPT_MAX_CHARS]


def _verified_block(facts: PrFacts) -> str:
    return "\n".join(f"- [x] {item}" for item in facts.checked_items)


def _gaps_block(facts: PrFacts) -> str:
    return "\n".join(f"- [ ] {item}" for item in facts.unchecked_items)


def _provenance_block(facts: PrFacts) -> str:
    return f"Review: {facts.review_path} (verdict: {facts.review_verdict}, sha: {facts.reviewed_sha})"


def _what_changed_prompt(facts: PrFacts) -> str:
    prompt = "Summarize what changed in this PR, in a short paragraph, given these commits:\n\n"
    prompt += "\n".join(f"- {c.subject}" for c in facts.commits)
    excerpt = _read_design_excerpt(facts)
    if excerpt:
        prompt += f"\n\nSlice design document:\n\n{excerpt}"
    return prompt


def _why_prompt(facts: PrFacts) -> str:
    excerpt = _read_design_excerpt(facts)
    if excerpt:
        return f"Explain why this change was made, given this slice design document:\n\n{excerpt}"
    subjects = "\n".join(f"- {c.subject}" for c in facts.commits)
    return f"Explain why this change was made, given only these commit subjects:\n\n{subjects}"


_SECTIONS: tuple[_Section, ...] = (
    _Section(
        heading="What changed",
        no_input_line="",  # never — commits always exist
        has_input=lambda facts: True,
        deterministic_block=_what_changed_block,
        prompt=_what_changed_prompt,
    ),
    _Section(
        heading="Why",
        no_input_line="",  # never — falls back to commits
        has_input=lambda facts: True,
        deterministic_block=_why_block,
        prompt=_why_prompt,
    ),
    _Section(
        heading="How it was verified",
        no_input_line=_NO_TASK_RECORDS,
        has_input=lambda facts: bool(facts.checked_items),
        deterministic_block=_verified_block,
        prompt=lambda facts: (
            "Summarize how this change was verified, given these completed task items:\n\n"
            + "\n".join(f"- {item}" for item in facts.checked_items)
        ),
    ),
    _Section(
        heading="Known gaps",
        no_input_line=_NO_TASK_RECORDS,
        has_input=lambda facts: bool(facts.unchecked_items),
        deterministic_block=_gaps_block,
        prompt=lambda facts: (
            "Summarize the known gaps in this change, given these unfinished task items:\n\n"
            + "\n".join(f"- {item}" for item in facts.unchecked_items)
        ),
    ),
    _Section(
        heading="Review provenance",
        no_input_line=_NO_REVIEW,
        has_input=lambda facts: facts.review_path is not None,
        deterministic_block=_provenance_block,
        prompt=lambda facts: (
            f"Summarize the review at {facts.review_path}, which reached verdict "
            f"{facts.review_verdict} against sha {facts.reviewed_sha}."
        ),
    ),
)


def _strip_model_headings(prose: str) -> str:
    """Discard any markdown heading line the model's own prose might contain.

    Squadron's headings are the only ones that reach the body (D4) — a model
    that echoes ``## What changed`` into its own response must not duplicate
    or displace the heading squadron already emitted for that section.
    """
    lines = [line for line in prose.splitlines() if not line.lstrip().startswith("#")]
    return "\n".join(lines).strip()


async def compose_body(facts: PrFacts, *, compose: Composer) -> str:
    """Assemble the five-section body: squadron's headings, the model's prose.

    Each section is either filled — the model's prose plus squadron's own
    deterministic facts directly beneath it — or carries its no-input line
    verbatim, with no model call for that section. Any heading the model's
    own response might contain is discarded: squadron's headings are the
    only ones that reach the body (D4).
    """
    parts: list[str] = []
    for section in _SECTIONS:
        parts.append(f"## {section.heading}")
        if not section.has_input(facts):
            parts.append(section.no_input_line)
            parts.append("")
            continue
        raw_prose = await compose(section.prompt(facts))
        prose = _strip_model_headings(raw_prose)
        if prose:
            parts.append(prose)
        block = section.deterministic_block(facts)
        if block:
            parts.append(block)
        parts.append("")
    return "\n\n".join(parts).strip() + "\n"


# --- The presence-and-filled check (D5) -------------------------------------


class BodyIncompleteError(Exception):
    """The assembled body fails the presence-and-filled check.

    Raised rather than retried — a retry loop would make the command's
    token cost unbounded, and the operator can rerun having seen why (D5).
    """


def check_body_complete(body: str, facts: PrFacts) -> None:
    """Raise unless all five headings are present, in order, and filled.

    Runs on the **assembled** body — after squadron's own headings and
    deterministic facts are inserted — so it validates what would be
    posted, not the model's raw response. "Filled" is structural: content
    non-empty after stripping the squadron-written deterministic block and
    whitespace, and not solely a restatement of the heading. It does not
    judge prose quality, which is not checkable (D5).
    """
    sections = _split_sections(body)
    expected = [section.heading for section in _SECTIONS]

    found_headings = [heading for heading, _ in sections]
    if found_headings != expected:
        raise BodyIncompleteError(
            f"PR body sections are missing or out of order: expected {expected}, found {found_headings}"
        )

    for section, (heading, content) in zip(_SECTIONS, sections, strict=True):
        if not _section_is_filled(section, content, facts):
            raise BodyIncompleteError(f"PR body section {heading!r} is empty or unfilled")


def _split_sections(body: str) -> list[tuple[str, str]]:
    """Split *body* into ``(heading, content)`` pairs at each ``## `` marker."""
    pattern = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(body))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        heading = match.group(1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections.append((heading, body[start:end].strip()))
    return sections


def _section_is_filled(section: _Section, content: str, facts: PrFacts) -> bool:
    """Whether *content* counts as filled for *section*, per D5's structural test."""
    if not section.has_input(facts):
        return content.strip() == section.no_input_line

    block = section.deterministic_block(facts)
    remainder = content
    if block and block in remainder:
        remainder = remainder.replace(block, "", 1)
    remainder = remainder.strip()

    if not remainder:
        return False
    if remainder.strip().lower() == section.heading.strip().lower():
        return False
    return True
