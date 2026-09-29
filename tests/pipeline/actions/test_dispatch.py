"""Tests for DispatchAction."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.core.models import AgentConfig, Message
from squadron.pipeline.actions.dispatch import DispatchAction
from squadron.pipeline.actions.protocol import Action
from squadron.pipeline.models import ActionContext, ActionResult
from squadron.pipeline.resolver import ModelResolutionError, ResolvedModel
from squadron.providers.base import ProfileName
from squadron.providers.errors import ProviderError
from squadron.providers.profiles import ProviderProfile
from tests.pipeline.conftest import typed_config

_P = "squadron.pipeline.actions.dispatch"


@pytest.fixture
def action() -> DispatchAction:
    return DispatchAction()


def _make_context(**overrides: object) -> ActionContext:
    """Build an ActionContext with sensible defaults."""
    resolver = MagicMock()
    resolver.resolve.return_value = ("claude-sonnet-4-20250514", None)
    resolver.resolve_full.return_value = ResolvedModel("claude-sonnet-4-20250514", None)
    defaults: dict[str, object] = {
        "pipeline_name": "test-pipeline",
        "run_id": "run-12345678",
        "params": {"prompt": "Hello world"},
        "step_name": "generate",
        "step_index": 0,
        "prior_outputs": {},
        "resolver": resolver,
        "cf_client": MagicMock(),
        "cwd": "/tmp/test",
    }
    defaults.update(overrides)
    return ActionContext(**defaults)  # type: ignore[arg-type]


def _sdk_profile() -> ProviderProfile:
    return ProviderProfile(
        name=ProfileName.SDK,
        provider="sdk",
        api_key_env=None,
        description="test",
    )


def _openrouter_profile() -> ProviderProfile:
    return ProviderProfile(
        name="openrouter",
        provider="openai",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        description="test",
    )


def _make_agent_mock(
    *contents: str,
    metadata: dict[str, object] | None = None,
) -> AsyncMock:
    """Build a mock agent whose handle_message yields given contents."""

    async def _handle(_msg: object) -> AsyncIterator[Message]:
        for content in contents:
            msg = MagicMock(spec=Message)
            msg.content = content
            msg.metadata = metadata or {}
            yield msg

    mock_agent = AsyncMock()
    mock_agent.handle_message = _handle
    return mock_agent


def _make_registry(agent: AsyncMock) -> MagicMock:
    """Build a mock registry that spawns the given agent."""
    mock_registry = MagicMock()
    mock_registry.spawn = AsyncMock(return_value=agent)
    mock_registry.shutdown_agent = AsyncMock()
    return mock_registry


# --- Protocol ---


def test_action_type(action: DispatchAction) -> None:
    assert action.action_type == "dispatch"


def test_protocol_compliance(action: DispatchAction) -> None:
    assert isinstance(action, Action)


# --- validate() ---


def test_validate_always_passes(action: DispatchAction) -> None:
    """Dispatch validates at runtime — prompt resolved from prior outputs."""
    assert action.validate({}) == []
    assert action.validate({"prompt": "hello"}) == []


# --- execute() ---


@pytest.mark.asyncio
async def test_execute_happy_path(action: DispatchAction) -> None:
    """Prompt dispatched, response captured in outputs."""
    ctx = _make_context()
    mock_agent = _make_agent_mock("Hello ", "world")
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    assert result.success is True
    assert result.outputs["response"] == "Hello world"
    assert result.metadata["model"] == "claude-sonnet-4-20250514"
    assert result.metadata["profile"] == ProfileName.SDK


@pytest.mark.asyncio
async def test_execute_model_resolution(action: DispatchAction) -> None:
    """Resolver called with action_model and step_model from params."""
    ctx = _make_context(
        params={"prompt": "test", "model": "opus", "step_model": "sonnet"},
    )
    mock_agent = _make_agent_mock("ok")
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        await action.execute(ctx)

    # resolve is called once for the guard check (no session path) and once
    # inside _dispatch_via_agent — both with the same args.
    ctx.resolver.resolve_full.assert_called_with("opus", "sonnet")
    assert ctx.resolver.resolve.call_count + ctx.resolver.resolve_full.call_count == 2


@pytest.mark.asyncio
async def test_execute_profile_from_alias(action: DispatchAction) -> None:
    """When resolver returns alias profile, that profile is used."""
    ctx = _make_context()
    ctx.resolver.resolve.return_value = ("model-x", "openrouter")
    ctx.resolver.resolve_full.return_value = ResolvedModel("model-x", "openrouter")
    mock_agent = _make_agent_mock("ok")
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_openrouter_profile()) as mock_get_profile,
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    mock_get_profile.assert_called_once_with("openrouter")
    assert result.metadata["profile"] == "openrouter"


@pytest.mark.asyncio
async def test_execute_profile_override(action: DispatchAction) -> None:
    """Explicit profile in params takes precedence over alias profile."""
    ctx = _make_context(params={"prompt": "test", "profile": "openai"})
    ctx.resolver.resolve.return_value = ("model-x", "openrouter")
    ctx.resolver.resolve_full.return_value = ResolvedModel("model-x", "openrouter")
    mock_agent = _make_agent_mock("ok")
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()) as mock_get_profile,
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    mock_get_profile.assert_called_once_with("openai")
    assert result.metadata["profile"] == "openai"


@pytest.mark.asyncio
async def test_execute_default_profile(action: DispatchAction) -> None:
    """When no alias profile and no explicit profile, defaults to SDK."""
    ctx = _make_context()
    ctx.resolver.resolve.return_value = ("model-x", None)
    ctx.resolver.resolve_full.return_value = ResolvedModel("model-x", None)
    mock_agent = _make_agent_mock("ok")
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()) as mock_get_profile,
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    mock_get_profile.assert_called_once_with(ProfileName.SDK)
    assert result.metadata["profile"] == ProfileName.SDK


@pytest.mark.asyncio
async def test_execute_system_prompt(action: DispatchAction) -> None:
    """System prompt passed as instructions in AgentConfig."""
    ctx = _make_context(
        params={"prompt": "test", "system_prompt": "You are helpful."},
    )
    mock_agent = _make_agent_mock("ok")
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        await action.execute(ctx)

    spawn_config = mock_registry.spawn.call_args[0][0]
    assert spawn_config.instructions == "You are helpful."


@pytest.mark.asyncio
async def test_execute_sdk_dedup(action: DispatchAction) -> None:
    """Messages with sdk_type='result' are filtered out."""
    ctx = _make_context()

    async def _responses(_msg: object) -> AsyncIterator[Message]:
        normal = MagicMock(spec=Message)
        normal.content = "real response"
        normal.metadata = {}
        yield normal

        dupe = MagicMock(spec=Message)
        dupe.content = "real response"
        dupe.metadata = {"sdk_type": "result"}
        yield dupe

    mock_agent = AsyncMock()
    mock_agent.handle_message = _responses
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    assert result.outputs["response"] == "real response"


@pytest.mark.asyncio
async def test_execute_token_metadata(action: DispatchAction) -> None:
    """Token metadata from agent responses is not propagated (unused downstream)."""
    ctx = _make_context()
    token_meta = {
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30,
    }
    mock_agent = _make_agent_mock("ok", metadata=token_meta)
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    assert result.success is True
    assert "prompt_tokens" not in result.metadata
    assert result.metadata.get("model") is not None


@pytest.mark.asyncio
async def test_execute_token_metadata_absent(action: DispatchAction) -> None:
    """When no token metadata, result still has model and profile."""
    ctx = _make_context()
    mock_agent = _make_agent_mock("ok")
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    assert "model" in result.metadata
    assert "profile" in result.metadata
    assert "prompt_tokens" not in result.metadata


@pytest.mark.asyncio
async def test_execute_agent_shutdown_always_called(
    action: DispatchAction,
) -> None:
    """Agent shutdown called even on error during handle_message."""
    ctx = _make_context()

    async def _explode(_msg: object) -> AsyncIterator[Message]:
        raise RuntimeError("boom")
        yield  # type: ignore[misc]  # make it an async generator

    mock_agent = AsyncMock()
    mock_agent.handle_message = _explode
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    assert result.success is False
    assert "boom" in (result.error or "")
    mock_registry.shutdown_agent.assert_called_once()


@pytest.mark.asyncio
async def test_execute_model_resolution_error(
    action: DispatchAction,
) -> None:
    """ModelResolutionError returns success=False."""
    ctx = _make_context()
    ctx.resolver.resolve.side_effect = ModelResolutionError("no model")

    with (
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    assert result.success is False
    assert "no model" in (result.error or "")


@pytest.mark.asyncio
async def test_execute_profile_not_found(action: DispatchAction) -> None:
    """KeyError from get_profile returns success=False."""
    ctx = _make_context()

    with patch(
        f"{_P}.get_profile",
        side_effect=KeyError("Profile 'bad' not found"),
    ):
        result = await action.execute(ctx)

    assert result.success is False
    assert "bad" in (result.error or "")


@pytest.mark.asyncio
async def test_execute_handle_message_error_still_shuts_down(
    action: DispatchAction,
) -> None:
    """Agent handle_message exception: success=False, agent still shut down."""
    ctx = _make_context()

    async def _fail(_msg: object) -> AsyncIterator[Message]:
        raise ConnectionError("API unavailable")
        yield  # type: ignore[misc]

    mock_agent = AsyncMock()
    mock_agent.handle_message = _fail
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    assert result.success is False
    mock_registry.shutdown_agent.assert_called_once()


@pytest.mark.asyncio
async def test_execute_agent_cli_error_response_returns_failure(
    action: DispatchAction,
) -> None:
    """CLI API errors surfaced as text must not be treated as successful dispatch."""
    error_text = (
        'API Error: 500 {"type":"error","error":{"type":"api_error","message":"Internal server error"}}'
    )
    mock_agent = _make_agent_mock(error_text)
    mock_registry = _make_registry(mock_agent)

    ctx = _make_context()
    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    assert result.success is False
    assert result.error == error_text
    assert result.outputs["response"] == error_text


# --- allowed_tools and cwd threading (slice 263) ---


async def _spawned_config(action: DispatchAction, ctx: ActionContext) -> object:
    """Execute *action* against *ctx* and return the AgentConfig it spawned."""
    mock_agent = _make_agent_mock("ok")
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_openrouter_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        await action.execute(ctx)

    return mock_registry.spawn.call_args[0][0]


@pytest.mark.asyncio
async def test_dispatch_passes_allowed_tools_to_agent_config(action: DispatchAction) -> None:
    ctx = _make_context(params={"prompt": "test", "allowed_tools": ["read_file", "write_file"]})
    config = await _spawned_config(action, ctx)
    assert config.allowed_tools == ["read_file", "write_file"]  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_dispatch_passes_cwd_to_agent_config(action: DispatchAction) -> None:
    ctx = _make_context(params={"prompt": "test", "allowed_tools": ["read_file"]})
    config = await _spawned_config(action, ctx)
    assert config.cwd == ctx.cwd  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_dispatch_passes_cwd_even_without_tools(action: DispatchAction) -> None:
    """D2 regression guard: cwd threads unconditionally, not only with tools."""
    ctx = _make_context(params={"prompt": "test"})
    config = await _spawned_config(action, ctx)
    assert config.cwd == ctx.cwd  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_dispatch_without_allowed_tools_leaves_field_none(action: DispatchAction) -> None:
    ctx = _make_context(params={"prompt": "test"})
    config = await _spawned_config(action, ctx)
    assert config.allowed_tools is None  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_allowed_tools_list_survives_param_resolution(action: DispatchAction) -> None:
    """The one named risk: first list-valued step config field on the param path."""
    ctx = _make_context(params={"prompt": "test", "allowed_tools": ["read_file", "write_file"]})
    config = await _spawned_config(action, ctx)
    tools_value = config.allowed_tools  # type: ignore[attr-defined]
    assert isinstance(tools_value, list)
    assert all(isinstance(name, str) for name in tools_value)  # pyright: ignore[reportUnknownVariableType]
    assert tools_value == ["read_file", "write_file"]


@pytest.mark.asyncio
async def test_malformed_allowed_tools_fails_rather_than_dropping(action: DispatchAction) -> None:
    """A non-list value must fail loudly; silently dropping tools is the bug class
    this slice exists to prevent."""
    ctx = _make_context(params={"prompt": "test", "allowed_tools": "read_file"})
    mock_agent = _make_agent_mock("ok")
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_openrouter_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    assert result.success is False
    assert "allowed_tools" in (result.error or "")
    mock_registry.spawn.assert_not_called()


# --- SDK-path guards (slice 263 review findings 1 and 2) ---


@pytest.mark.asyncio
async def test_sdk_session_path_rejects_allowed_tools(action: DispatchAction) -> None:
    """Finding 1: the session path carries no tools, so it must fail rather than
    run tool-less and return success with prose."""
    session = AsyncMock()
    resolver = MagicMock()
    resolver.resolve.return_value = ("claude-sonnet-4-20250514", ProfileName.SDK)
    resolver.resolve_full.return_value = ResolvedModel("claude-sonnet-4-20250514", ProfileName.SDK)
    ctx = _make_context(
        params={"prompt": "test", "allowed_tools": ["read_file"]},
        sdk_session=session,
        resolver=resolver,
    )

    result = await action.execute(ctx)

    assert result.success is False
    assert "allowed_tools" in (result.error or "")
    session.dispatch.assert_not_called()


@pytest.mark.asyncio
async def test_sdk_profile_one_shot_accepts_allowed_tools(action: DispatchAction) -> None:
    """Slice 267 (#75): the one-shot guard is gone — canonical names reach the config.

    Slice 265 put ``translate_tool_names`` inside ``ClaudeSDKProvider.create_agent`` for
    every config that sets ``allowed_tools``, which is what made the guard obsolete: the
    vocabulary mismatch it protected against is now handled one layer down.
    """
    ctx = _make_context(params={"prompt": "test", "allowed_tools": ["read_file"]})
    mock_registry = _make_registry(_make_agent_mock("ok"))

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    assert result.success is True
    config = mock_registry.spawn.call_args[0][0]
    assert config.allowed_tools == ["read_file"]


@pytest.mark.asyncio
async def test_sdk_provider_translates_dispatched_tool_names() -> None:
    """The other half of #75: the canonical name arrives as SDK vocabulary."""
    from squadron.providers.sdk.provider import ClaudeSDKProvider

    config = AgentConfig(
        name="dispatch-generate",
        agent_type="sdk",
        provider="sdk",
        model="claude-sonnet-4-20250514",
        allowed_tools=["read_file"],
    )
    agent = await ClaudeSDKProvider().create_agent(config)

    assert agent._options.allowed_tools == ["Read"]  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_sdk_provider_raises_on_unmapped_dispatched_tool_name() -> None:
    """An unmapped canonical name still fails loudly, just one layer lower."""
    from squadron.providers.sdk.provider import ClaudeSDKProvider

    config = AgentConfig(
        name="dispatch-generate",
        agent_type="sdk",
        provider="sdk",
        model="claude-sonnet-4-20250514",
        allowed_tools=["definitely_not_a_tool"],
    )
    with pytest.raises(ProviderError, match="definitely_not_a_tool"):
        await ClaudeSDKProvider().create_agent(config)


@pytest.mark.asyncio
async def test_sdk_one_shot_without_prompt_uses_default_system_prompt(
    action: DispatchAction,
) -> None:
    """SC7 first half (#40): an SDK step with no system_prompt gets the CLI's own."""
    ctx = _make_context(params={"prompt": "test"})
    mock_registry = _make_registry(_make_agent_mock("ok"))

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        await action.execute(ctx)

    config = mock_registry.spawn.call_args[0][0]
    assert config.use_default_system_prompt is True
    assert config.instructions is None


@pytest.mark.asyncio
async def test_sdk_one_shot_system_prompt_appends_to_preset(action: DispatchAction) -> None:
    """#155: an SDK step's system_prompt is appended to the preset, never replaces it."""
    ctx = _make_context(params={"prompt": "test", "system_prompt": "Be terse."})
    mock_registry = _make_registry(_make_agent_mock("ok"))

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        await action.execute(ctx)

    config = mock_registry.spawn.call_args[0][0]
    assert config.use_default_system_prompt is True
    assert config.instructions == "Be terse."


@pytest.mark.asyncio
async def test_non_sdk_one_shot_system_prompt_is_the_whole_prompt(action: DispatchAction) -> None:
    """Non-SDK is unchanged: a step system_prompt is sent as the system message."""
    ctx = _make_context(params={"prompt": "test", "system_prompt": "Be terse."})
    mock_registry = _make_registry(_make_agent_mock("ok"))

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_openrouter_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        await action.execute(ctx)

    config = mock_registry.spawn.call_args[0][0]
    assert config.use_default_system_prompt is False
    assert config.instructions == "Be terse."


@pytest.mark.asyncio
async def test_non_sdk_one_shot_without_prompt_sends_no_system_message(
    action: DispatchAction,
) -> None:
    """SC7 second half: no system_prompt on a non-SDK step means no system message.

    An empty string would be sent as an actual empty system message; ``None`` means the
    agent appends none at all, leaving the guidance block as the whole prompt when the
    step declares tools.
    """
    ctx = _make_context(params={"prompt": "test"})
    mock_registry = _make_registry(_make_agent_mock("ok"))

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_openrouter_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        await action.execute(ctx)

    config = mock_registry.spawn.call_args[0][0]
    assert config.instructions is None
    assert config.use_default_system_prompt is False


@pytest.mark.asyncio
async def test_sdk_profile_does_not_receive_cwd(action: DispatchAction) -> None:
    """Finding 2: the SDK provider forwards a non-None cwd into ClaudeAgentOptions
    and previously never received the key — this slice must not change that."""
    ctx = _make_context(params={"prompt": "test"})
    mock_registry = _make_registry(_make_agent_mock("ok"))

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        await action.execute(ctx)

    assert mock_registry.spawn.call_args[0][0].cwd is None


# --- feedback: review (slice 195 D8) ---


def _review_result(input_file: str | None) -> ActionResult:
    return ActionResult(
        success=True,
        action_type="review",
        outputs={"input_file": input_file} if input_file else {},
        verdict="CONCERNS",
        findings=[
            {"severity": "concern", "summary": "Plan argument is ignored", "location": "sources.py:12"}
        ],
    )


def _build_context_result(stdout: str) -> ActionResult:
    return ActionResult(
        success=True,
        action_type="cf-op",
        outputs={"operation": "build_context", "stdout": stdout},
    )


_DESIGN = "project-documents/user/slices/923-slice.isolation.md"


class TestFeedbackReview:
    def test_prompt_has_findings_and_reviewed_file(self, action: DispatchAction) -> None:
        ctx = _make_context(
            params={"feedback": "review"},
            prior_outputs={"0-review-0": _review_result(_DESIGN)},
        )

        prompt = action._resolve_prompt(ctx)

        assert "[concern] Plan argument is ignored (sources.py:12)" in prompt
        assert f"Revise `{_DESIGN}` in place; do not create a new file." in prompt

    def test_step_prompt_comes_first(self, action: DispatchAction) -> None:
        ctx = _make_context(
            params={"feedback": "review", "prompt": "Keep the API section."},
            prior_outputs={"0-review-0": _review_result(_DESIGN)},
        )

        prompt = action._resolve_prompt(ctx)

        assert prompt.startswith("Keep the API section.")
        assert "Plan argument is ignored" in prompt

    def test_build_context_output_is_not_used(self, action: DispatchAction) -> None:
        ctx = _make_context(
            params={"feedback": "review"},
            prior_outputs={
                "0-review-0": _review_result(_DESIGN),
                "1-cf-op-2": _build_context_result("Create a slice design for 923."),
            },
        )

        prompt = action._resolve_prompt(ctx)

        assert "Create a slice design" not in prompt
        assert "Plan argument is ignored" in prompt

    @pytest.mark.asyncio
    async def test_no_review_in_scope_fails(self, action: DispatchAction) -> None:
        ctx = _make_context(
            params={"feedback": "review"},
            prior_outputs={"1-cf-op-2": _build_context_result("Create a slice design.")},
        )

        result = await action.execute(ctx)

        assert result.success is False
        assert result.error == "feedback: review but no prior review in scope"


class TestDispatchStepFeedback:
    def test_feedback_passes_through_and_validates(self) -> None:
        from squadron.pipeline.models import StepConfig
        from squadron.pipeline.steps.dispatch import DispatchStepType

        step = DispatchStepType()
        good = StepConfig(step_type="dispatch", name="revise", config={"feedback": "review"})
        bad = StepConfig(step_type="dispatch", name="revise", config={"feedback": "judge"})

        assert step.validate(good) == []
        assert [e.field for e in step.validate(bad)] == ["feedback"]
        assert step.expand(good) == [("dispatch", {"feedback": "review"})]


# ---------------------------------------------------------------------------
# Settings policy on one-shot dispatch (slice 932 D10/D11)
# ---------------------------------------------------------------------------


async def _config_with_profile(
    action: DispatchAction, profile: ProviderProfile, auto_memory: bool = True
) -> AgentConfig:
    mock_registry = _make_registry(_make_agent_mock("ok"))
    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=profile),
        patch(f"{_P}.ensure_provider_loaded"),
        patch(
            f"{_P}.get_typed_config",
            typed_config({"pipeline.auto_memory": auto_memory, "pipeline.user_settings": False}),
        ),
    ):
        await action.execute(_make_context())
    return mock_registry.spawn.call_args[0][0]


@pytest.mark.asyncio
@pytest.mark.parametrize("auto_memory", [True, False])
async def test_sdk_dispatch_uses_pipeline_settings(action: DispatchAction, auto_memory: bool) -> None:
    config = await _config_with_profile(action, _sdk_profile(), auto_memory=auto_memory)
    assert config.setting_sources == ["project"]
    assert config.auto_memory is auto_memory


@pytest.mark.asyncio
async def test_non_sdk_dispatch_leaves_settings_unset(action: DispatchAction) -> None:
    config = await _config_with_profile(action, _openrouter_profile())
    assert config.setting_sources is None
    assert config.auto_memory is False


@pytest.mark.asyncio
@pytest.mark.parametrize("auto_memory", [True, False])
async def test_sdk_one_shot_records_prompt_and_settings(
    action: DispatchAction, auto_memory: bool
) -> None:
    """Slice 932 D12: recorded from the config actually spawned."""
    ctx = _make_context(params={"prompt": "test", "system_prompt": "Be terse."})
    mock_registry = _make_registry(_make_agent_mock("ok"))

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
        patch(
            f"{_P}.get_typed_config",
            typed_config({"pipeline.auto_memory": auto_memory, "pipeline.user_settings": False}),
        ),
    ):
        result = await action.execute(ctx)

    assert result.metadata["system_prompt_mode"] == "preset+append"
    assert result.metadata["setting_sources"] == "project"
    assert result.metadata["auto_memory"] is auto_memory
