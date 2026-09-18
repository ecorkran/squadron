"""Tests for the composer's wiring (D3), title resolution (D4a), and the
section contract (D4).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.core.models import Message
from squadron.pr.assembly import PrFacts
from squadron.pr.body import CompositionError, compose_body, compose_one_shot, resolve_title
from squadron.providers.base import AgentProvider, ProviderCapabilities
from squadron.review.git_utils import CommitRecord
from squadron.review.models import Verdict

_FAKE_PROFILE = "fake-pr-body"
_FAKE_PROVIDER_TYPE = "fake-pr-body-provider"


def _make_fake_message(content: str) -> Message:
    msg = MagicMock(spec=Message)
    msg.content = content
    msg.metadata = {}
    return msg


def _make_fake_agent(messages: list[Message], *, raises: Exception | None = None) -> MagicMock:
    async def _handle(message: Message) -> AsyncIterator[Message]:
        if raises is not None:
            raise raises
        for m in messages:
            yield m

    agent = MagicMock()
    agent.handle_message = _handle
    agent.shutdown = AsyncMock()
    return agent


def _make_fake_provider(agent: MagicMock) -> AgentProvider:
    provider = MagicMock(spec=AgentProvider)
    provider.provider_type = _FAKE_PROVIDER_TYPE
    provider.capabilities = ProviderCapabilities()
    provider.create_agent = AsyncMock(return_value=agent)
    return provider


@pytest.fixture
def fake_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Register a fake profile and provider for the duration of the test."""
    from squadron.providers import loader as loader_mod
    from squadron.providers import profiles as profiles_mod
    from squadron.providers.profiles import ProviderProfile

    fake_profile = ProviderProfile(
        name=_FAKE_PROFILE,
        provider=_FAKE_PROVIDER_TYPE,
        api_key_env=None,
        description="Fake profile for unit tests",
    )

    original_get_all = profiles_mod.get_all_profiles
    monkeypatch.setattr(
        profiles_mod,
        "get_all_profiles",
        lambda: {**original_get_all(), _FAKE_PROFILE: fake_profile},
    )
    monkeypatch.setattr(loader_mod, "ensure_provider_loaded", lambda name: None)


@pytest.mark.asyncio
async def test_composer_resolves_profile_through_the_registry(
    monkeypatch: pytest.MonkeyPatch, fake_provider_env: None
) -> None:
    from squadron.providers import registry as registry_mod

    agent = _make_fake_agent([_make_fake_message("the body")])
    provider = _make_fake_provider(agent)
    registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider

    result = await compose_one_shot("write a PR body", model="model-x", profile=_FAKE_PROFILE)

    assert result == "the body"
    provider.create_agent.assert_awaited_once()
    config = provider.create_agent.await_args.args[0]
    assert config.provider == _FAKE_PROVIDER_TYPE
    assert config.model == "model-x"


@pytest.mark.asyncio
async def test_model_none_is_passed_through_not_defaulted(
    monkeypatch: pytest.MonkeyPatch, fake_provider_env: None
) -> None:
    from squadron.providers import registry as registry_mod

    agent = _make_fake_agent([_make_fake_message("the body")])
    provider = _make_fake_provider(agent)
    registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider

    await compose_one_shot("write a PR body", model=None, profile=_FAKE_PROFILE)

    config = provider.create_agent.await_args.args[0]
    assert config.model is None


@pytest.mark.asyncio
async def test_no_tools_are_requested(monkeypatch: pytest.MonkeyPatch, fake_provider_env: None) -> None:
    from squadron.providers import registry as registry_mod

    agent = _make_fake_agent([_make_fake_message("the body")])
    provider = _make_fake_provider(agent)
    registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider

    await compose_one_shot("write a PR body", model=None, profile=_FAKE_PROFILE)

    config = provider.create_agent.await_args.args[0]
    assert config.allowed_tools == []


@pytest.mark.asyncio
async def test_response_text_is_returned_unmodified(
    monkeypatch: pytest.MonkeyPatch, fake_provider_env: None
) -> None:
    from squadron.providers import registry as registry_mod

    agent = _make_fake_agent([_make_fake_message("Part A"), _make_fake_message("Part B")])
    provider = _make_fake_provider(agent)
    registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider

    result = await compose_one_shot("write a PR body", model=None, profile=_FAKE_PROFILE)

    assert result == "Part A\nPart B"


@pytest.mark.asyncio
async def test_sdk_profile_resolves_and_dispatches_without_a_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The design's D3 claim, checked rather than asserted.

    ``ensure_provider_loaded`` is patched to a no-op: unpatched, it imports
    the real SDK provider module, which re-registers the genuine provider
    over the fake this test installs.
    """
    from squadron.providers import registry as registry_mod

    agent = _make_fake_agent([_make_fake_message("the body")])
    provider = MagicMock(spec=AgentProvider)
    provider.provider_type = "sdk"
    provider.capabilities = ProviderCapabilities()
    provider.create_agent = AsyncMock(return_value=agent)

    from squadron.providers import loader as loader_mod

    monkeypatch.setattr(loader_mod, "ensure_provider_loaded", lambda name: None)
    original = registry_mod._REGISTRY.get("sdk")
    registry_mod._REGISTRY["sdk"] = provider
    try:
        result = await compose_one_shot("write a PR body", model=None, profile="sdk")
    finally:
        if original is not None:
            registry_mod._REGISTRY["sdk"] = original
        else:
            registry_mod._REGISTRY.pop("sdk", None)

    assert result == "the body"
    provider.create_agent.assert_awaited_once()


@pytest.mark.asyncio
async def test_provider_raising_exits_via_composition_error(
    monkeypatch: pytest.MonkeyPatch, fake_provider_env: None
) -> None:
    from squadron.providers import registry as registry_mod

    agent = _make_fake_agent([], raises=RuntimeError("provider exploded"))
    provider = _make_fake_provider(agent)
    registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider

    with pytest.raises(CompositionError):
        await compose_one_shot("write a PR body", model=None, profile=_FAKE_PROFILE)

    agent.shutdown.assert_called_once()


# --- resolve_title (D4a) ----------------------------------------------------

TITLE_COMMITS = (
    CommitRecord(sha="def456", subject="feat: second commit"),
    CommitRecord(sha="abc123", subject="feat: first commit"),
)


class _FailIfCalledComposer:
    """A composer that fails the test if the model is ever asked."""

    async def __call__(self, prompt: str) -> str:
        raise AssertionError("the model must not be called")


def _fixed_composer(response: str):
    async def _compose(prompt: str) -> str:
        return response

    return _compose


@pytest.mark.asyncio
async def test_title_flag_wins_over_both_other_terms(tmp_path: Path) -> None:
    design = tmp_path / "design.md"
    design.write_text("# Slice Design: Some Slice\n")

    title = await resolve_title(
        title_flag="Custom Title",
        slice_design_file=str(design),
        commits=TITLE_COMMITS,
        compose=_FailIfCalledComposer(),
    )

    assert title == "Custom Title"


@pytest.mark.asyncio
async def test_resolved_slice_branch_uses_h1_and_never_calls_the_composer(tmp_path: Path) -> None:
    design = tmp_path / "design.md"
    design.write_text("# Slice Design: Create a PR with a Good Message\n\nBody text.\n")

    title = await resolve_title(
        title_flag=None,
        slice_design_file=str(design),
        commits=TITLE_COMMITS,
        compose=_FailIfCalledComposer(),
    )

    assert title == "Create a PR with a Good Message"


@pytest.mark.asyncio
async def test_design_with_non_matching_h1_falls_through_to_the_model(tmp_path: Path) -> None:
    design = tmp_path / "design.md"
    design.write_text("# Something Else Entirely\n")

    title = await resolve_title(
        title_flag=None,
        slice_design_file=str(design),
        commits=TITLE_COMMITS,
        compose=_fixed_composer("A composed title"),
    )

    assert title == "A composed title"


@pytest.mark.asyncio
async def test_non_slice_branch_composes() -> None:
    title = await resolve_title(
        title_flag=None,
        slice_design_file=None,
        commits=TITLE_COMMITS,
        compose=_fixed_composer("A composed title"),
    )

    assert title == "A composed title"


@pytest.mark.asyncio
async def test_empty_model_response_falls_back_to_first_commit_subject() -> None:
    title = await resolve_title(
        title_flag=None,
        slice_design_file=None,
        commits=TITLE_COMMITS,
        compose=_fixed_composer("   "),
    )

    assert title == TITLE_COMMITS[0].subject


@pytest.mark.asyncio
async def test_multiline_response_falls_back() -> None:
    title = await resolve_title(
        title_flag=None,
        slice_design_file=None,
        commits=TITLE_COMMITS,
        compose=_fixed_composer("line one\nline two"),
    )

    assert title == TITLE_COMMITS[0].subject


@pytest.mark.asyncio
async def test_response_over_72_characters_falls_back() -> None:
    long_response = "x" * 100
    title = await resolve_title(
        title_flag=None,
        slice_design_file=None,
        commits=TITLE_COMMITS,
        compose=_fixed_composer(long_response),
    )

    assert title == TITLE_COMMITS[0].subject


@pytest.mark.asyncio
async def test_valid_60_character_response_is_used() -> None:
    valid_response = "y" * 60
    title = await resolve_title(
        title_flag=None,
        slice_design_file=None,
        commits=TITLE_COMMITS,
        compose=_fixed_composer(valid_response),
    )

    assert title == valid_response


# --- compose_body / the section contract (D4) -------------------------------

BODY_COMMITS = (CommitRecord(sha="abc123def456", subject="feat: do the thing"),)


def _full_facts() -> PrFacts:
    return PrFacts(
        commits=BODY_COMMITS,
        slice_design_file="project-documents/user/slices/385-slice.foo.md",
        checked_items=("did a thing",),
        unchecked_items=("gap remains",),
        review_path="project-documents/user/reviews/385-review.slice.foo.md",
        review_verdict=Verdict.PASS,
        reviewed_sha="deadbeef",
    )


def _no_slice_facts() -> PrFacts:
    return PrFacts(
        commits=BODY_COMMITS,
        slice_design_file=None,
        checked_items=(),
        unchecked_items=(),
        review_path=None,
        review_verdict=None,
        reviewed_sha=None,
    )


SECTION_HEADINGS = ("What changed", "Why", "How it was verified", "Known gaps", "Review provenance")


@pytest.mark.asyncio
async def test_full_inputs_produce_five_sections_no_no_input_lines() -> None:
    facts = _full_facts()

    body = await compose_body(facts, compose=_fixed_composer("Some prose."))

    for heading in SECTION_HEADINGS:
        assert f"## {heading}" in body
    assert "No task records for this branch." not in body
    assert "No squadron review covers this branch's commits." not in body


@pytest.mark.asyncio
async def test_no_slice_the_two_task_sections_carry_the_no_input_line() -> None:
    facts = _no_slice_facts()

    body = await compose_body(facts, compose=_fixed_composer("Some prose."))

    assert body.count("No task records for this branch.") == 2


@pytest.mark.asyncio
async def test_no_review_provenance_carries_its_no_input_line() -> None:
    facts = _no_slice_facts()

    body = await compose_body(facts, compose=_fixed_composer("Some prose."))

    assert "No squadron review covers this branch's commits." in body


@pytest.mark.asyncio
async def test_unplanned_repository_has_five_sections_three_no_input_lines() -> None:
    facts = _no_slice_facts()

    body = await compose_body(facts, compose=_fixed_composer("Some prose."))

    for heading in SECTION_HEADINGS:
        assert f"## {heading}" in body
    assert body.count("No task records for this branch.") == 2
    assert body.count("No squadron review covers this branch's commits.") == 1


@pytest.mark.asyncio
async def test_deterministic_facts_appear_verbatim() -> None:
    facts = _full_facts()

    body = await compose_body(facts, compose=_fixed_composer("Some prose."))

    assert facts.commits[0].sha[:12] in body
    assert facts.slice_design_file is not None
    assert facts.slice_design_file in body
    assert facts.reviewed_sha is not None
    assert facts.reviewed_sha in body


@pytest.mark.asyncio
async def test_model_headings_do_not_duplicate_or_reorder_sections() -> None:
    facts = _full_facts()
    model_response_with_headings = "## What changed\nBogus model heading.\n## Why\nMore bogus text."

    body = await compose_body(facts, compose=_fixed_composer(model_response_with_headings))

    for heading in SECTION_HEADINGS:
        assert body.count(f"## {heading}") == 1
