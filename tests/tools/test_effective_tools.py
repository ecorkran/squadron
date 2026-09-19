"""Tests for the slice 266 capability gate.

Covers ``resolve_effective_tools`` itself (T4), the ``tool_use`` alias field
(T1/T2), and the gate at each sanctioned ``AgentConfig`` call site (T6, T10),
plus the SC1a enumeration guard that keeps a new call site from skipping it.
"""

from __future__ import annotations

import ast
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.core.models import AgentConfig, AgentState, Message, MessageType
from squadron.metrology.audit import _AUDIT_ALLOWED_TOOLS
from squadron.models.aliases import get_all_aliases, load_builtin_aliases
from squadron.pipeline.actions.dispatch import one_shot_dispatch_with_telemetry
from squadron.pipeline.summary_oneshot import capture_summary_via_profile_with_telemetry
from squadron.providers.base import ProviderCapabilities
from squadron.providers.profiles import ProviderProfile
from squadron.review.models import ReviewResult, Verdict
from squadron.review.review_client import run_review_with_profile
from squadron.review.templates import ReviewTemplate
from squadron.tools import SuppressionReason, resolve_effective_tools

DECLARED = ["read_file", "grep"]


# ---------------------------------------------------------------------------
# T4 — resolve_effective_tools truth table
# ---------------------------------------------------------------------------


def test_declared_passes_through_when_nothing_denies() -> None:
    """No denial: the declared list survives intact with no reason."""
    tools, reason = resolve_effective_tools(DECLARED, model_allows_tools=True, suppressed=False)
    assert tools == DECLARED
    assert reason is None


def test_capability_denial_empties_the_set() -> None:
    """tool_use = false empties a non-empty declared set."""
    tools, reason = resolve_effective_tools(DECLARED, model_allows_tools=False, suppressed=False)
    assert tools == []
    assert reason == SuppressionReason.MODEL_CAPABILITY.value


def test_run_suppression_empties_the_set() -> None:
    """--no-tools empties a non-empty declared set."""
    tools, reason = resolve_effective_tools(DECLARED, model_allows_tools=True, suppressed=True)
    assert tools == []
    assert reason == SuppressionReason.RUN_SUPPRESSED.value


def test_both_denials_are_recorded_together() -> None:
    """Both denials at once: neither is lost by reporting only one."""
    tools, reason = resolve_effective_tools(DECLARED, model_allows_tools=False, suppressed=True)
    assert tools == []
    assert reason == SuppressionReason.BOTH.value


def test_capability_and_suppression_reasons_are_distinguishable() -> None:
    """SC4: telemetry must tell the two denials apart, not merely flag both."""
    _, capability = resolve_effective_tools(DECLARED, model_allows_tools=False, suppressed=False)
    _, suppressed = resolve_effective_tools(DECLARED, model_allows_tools=True, suppressed=True)
    assert capability != suppressed
    assert capability is not None and suppressed is not None


def test_none_declared_is_not_a_suppression() -> None:
    """Nothing declared is not a suppression and must not be announced as one."""
    tools, reason = resolve_effective_tools(None, model_allows_tools=False, suppressed=True)
    assert tools == []
    assert reason is None


def test_empty_declared_is_not_a_suppression() -> None:
    """An already-empty declared set behaves the same as None."""
    tools, reason = resolve_effective_tools([], model_allows_tools=False, suppressed=True)
    assert tools == []
    assert reason is None


def test_result_does_not_alias_the_caller_list() -> None:
    """The returned list is a copy: a caller mutating it cannot corrupt the source."""
    declared = list(DECLARED)
    tools, _ = resolve_effective_tools(declared, model_allows_tools=True, suppressed=False)
    tools.append("bash")
    assert declared == DECLARED


# ---------------------------------------------------------------------------
# T1/T2 — the tool_use alias field
# ---------------------------------------------------------------------------


def test_alias_tool_use_false_reads_back(tmp_path: Path) -> None:
    """T1: an alias with tool_use = false reads back False."""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text('[aliases]\ngated = { profile = "openai", model = "m", tool_use = false }\n')

    with patch("squadron.models.aliases.models_toml_path", return_value=toml_file):
        aliases = get_all_aliases()

    assert aliases["gated"]["tool_use"] is False


def test_alias_without_tool_use_has_no_key(tmp_path: Path) -> None:
    """T1: absence stays distinguishable from an explicit true (SC2)."""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text('[aliases]\nplain = { profile = "openai", model = "m" }\n')

    with patch("squadron.models.aliases.models_toml_path", return_value=toml_file):
        aliases = get_all_aliases()

    assert "tool_use" not in aliases["plain"]


def test_non_bool_tool_use_is_ignored(tmp_path: Path) -> None:
    """A non-bool value is not accepted, matching the private field's guard."""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text('[aliases]\nodd = { profile = "openai", model = "m", tool_use = "false" }\n')

    with patch("squadron.models.aliases.models_toml_path", return_value=toml_file):
        aliases = get_all_aliases()

    assert "tool_use" not in aliases["odd"]


def test_no_shipped_alias_sets_tool_use() -> None:
    """T2/SC2: default-true preserves current behavior for every existing user."""
    for name, alias in load_builtin_aliases().items():
        assert "tool_use" not in alias, f"shipped alias {name} must not set tool_use"


# ---------------------------------------------------------------------------
# T6 — the gate on the review-client path (SC1, SC2, SC4)
#
# This task owns the review-client case. T10 below covers the other three
# sanctioned sites and must not restate it.
# ---------------------------------------------------------------------------

_P = "squadron.review.review_client"

_SAMPLE_REVIEW_OUTPUT = """\
**Verdict:** PASS

## Findings

### [PASS] — Looks fine

Nothing to report.
"""


def _make_template(allowed_tools: list[str] | None) -> ReviewTemplate:
    return ReviewTemplate(
        name="test",
        description="Test template",
        system_prompt="You are a reviewer.",
        allowed_tools=allowed_tools,
        permission_mode="bypassPermissions",
        setting_sources=None,
        required_inputs=[],
        optional_inputs=[],
        prompt_template="Review: {input}",
        profile=None,
        model=None,
    )


def _capture_provider(captured: dict[str, AgentConfig]) -> MagicMock:
    """A mock provider recording the AgentConfig its agent was built from."""
    agent = MagicMock()
    agent.state = AgentState.idle
    agent.shutdown = AsyncMock()

    async def _handle(message: Message) -> AsyncIterator[Message]:
        yield Message(
            sender="mock-agent",
            recipients=[],
            content=_SAMPLE_REVIEW_OUTPUT,
            message_type=MessageType.chat,
        )

    agent.handle_message = _handle

    async def _create_agent(config: AgentConfig) -> MagicMock:
        captured["config"] = config
        return agent

    provider = MagicMock()
    provider.capabilities = ProviderCapabilities(can_read_files=False)
    provider.create_agent = _create_agent
    return provider


async def _run_review(
    tmp_path: Path,
    *,
    allowed_tools: list[str] | None,
    model: str | None,
    aliases_toml: str,
    no_tools: bool = False,
) -> tuple[AgentConfig, ReviewResult]:
    target = tmp_path / "design.md"
    target.write_text("SENTINEL FILE BODY")
    toml_file = tmp_path / "models.toml"
    toml_file.write_text(aliases_toml)

    captured: dict[str, AgentConfig] = {}
    provider = _capture_provider(captured)
    profile = ProviderProfile(name="openai", provider="openai", api_key_env="OPENAI_API_KEY")

    with (
        patch(f"{_P}.get_profile", return_value=profile),
        patch(f"{_P}.get_provider", return_value=provider),
        patch(f"{_P}.ensure_provider_loaded"),
        patch("squadron.models.aliases.models_toml_path", return_value=toml_file),
    ):
        result = await run_review_with_profile(
            _make_template(allowed_tools),
            {"input": str(target), "cwd": str(tmp_path)},
            profile=profile.name,
            model=model,
            no_tools=no_tools,
        )
    return captured["config"], result


_GATED_TOML = '[aliases]\ngated = { profile = "openai", model = "m", tool_use = false }\n'
_PLAIN_TOML = '[aliases]\nplain = { profile = "openai", model = "m" }\n'


@pytest.mark.asyncio
async def test_review_gate_empties_tools_for_denied_model(tmp_path: Path) -> None:
    """SC1: a tool_use = false model gets no tools even though the template declares them."""
    config, result = await _run_review(
        tmp_path,
        allowed_tools=["read_file", "grep"],
        model="gated",
        aliases_toml=_GATED_TOML,
    )
    assert config.allowed_tools == []
    assert config.tools_suppressed_reason == SuppressionReason.MODEL_CAPABILITY.value
    assert result.tools_suppressed_reason == SuppressionReason.MODEL_CAPABILITY.value


@pytest.mark.asyncio
async def test_review_gate_passes_tools_when_field_absent(tmp_path: Path) -> None:
    """SC2: an alias without tool_use is unaffected — the default-allow case."""
    config, result = await _run_review(
        tmp_path,
        allowed_tools=["read_file", "grep"],
        model="plain",
        aliases_toml=_PLAIN_TOML,
    )
    assert config.allowed_tools == ["read_file", "grep"]
    assert config.tools_suppressed_reason is None
    assert result.tools_suppressed_reason is None


@pytest.mark.asyncio
async def test_review_gate_logs_on_suppression(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """SC4: suppression is announced at INFO."""
    with caplog.at_level(logging.INFO, logger="squadron.review.review_client"):
        await _run_review(
            tmp_path,
            allowed_tools=["read_file"],
            model="gated",
            aliases_toml=_GATED_TOML,
        )
    assert any("suppressed" in record.message.lower() for record in caplog.records)


@pytest.mark.asyncio
async def test_review_gate_silent_when_nothing_declared(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A template declaring no tools is not a suppression and must not be announced."""
    with caplog.at_level(logging.INFO, logger="squadron.review.review_client"):
        config, result = await _run_review(
            tmp_path,
            allowed_tools=None,
            model="gated",
            aliases_toml=_GATED_TOML,
        )
    assert config.tools_suppressed_reason is None
    assert result.tools_suppressed_reason is None
    assert not any("suppressed" in record.message.lower() for record in caplog.records)


# ---------------------------------------------------------------------------
# T10 — the remaining three call sites, plus the SC1a enumeration guard
#
# T6 above owns the review-client case; these cover dispatch, the summary
# one-shot, and the metrology audit.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_gate_empties_tools_for_denied_model(tmp_path: Path) -> None:
    """SC1, dispatch: a denied model gets no schemas even when the step declares them."""
    captured: dict[str, AgentConfig] = {}

    async def _spawn(config: AgentConfig) -> MagicMock:
        captured["config"] = config
        agent = MagicMock()

        async def _handle(_message: Message) -> AsyncIterator[Message]:
            yield Message(sender="a", recipients=[], content="done", message_type=MessageType.chat)

        agent.handle_message = _handle
        return agent

    registry = MagicMock()
    registry.spawn = _spawn
    registry.shutdown_agent = AsyncMock()
    profile = ProviderProfile(name="openai", provider="openai", api_key_env="OPENAI_API_KEY")

    with (
        patch("squadron.pipeline.actions.dispatch.get_registry", return_value=registry),
        patch("squadron.pipeline.actions.dispatch.get_profile", return_value=profile),
        patch("squadron.pipeline.actions.dispatch.ensure_provider_loaded"),
    ):
        await one_shot_dispatch_with_telemetry(
            prompt="hi",
            model_id="m",
            profile_name="openai",
            allowed_tools=["read_file"],
            model_allows_tools=False,
            cwd=str(tmp_path),
        )

    assert captured["config"].allowed_tools == []
    assert captured["config"].tools_suppressed_reason == SuppressionReason.MODEL_CAPABILITY.value


@pytest.mark.asyncio
async def test_summary_gate_drops_cwd_with_the_tools(tmp_path: Path) -> None:
    """SC1, summary: the cwd/allowed_tools pairing must stay consistent when gated."""
    captured: dict[str, AgentConfig] = {}
    agent = MagicMock()
    agent.shutdown = AsyncMock()

    async def _handle(_message: Message) -> AsyncIterator[Message]:
        yield Message(sender="a", recipients=[], content="sum", message_type=MessageType.chat)

    agent.handle_message = _handle

    async def _create_agent(config: AgentConfig) -> MagicMock:
        captured["config"] = config
        return agent

    provider = MagicMock()
    provider.create_agent = _create_agent
    profile = ProviderProfile(name="openai", provider="openai", api_key_env="OPENAI_API_KEY")

    with (
        patch("squadron.providers.profiles.get_profile", return_value=profile),
        patch("squadron.providers.registry.get_provider", return_value=provider),
        patch("squadron.providers.loader.ensure_provider_loaded"),
    ):
        await capture_summary_via_profile_with_telemetry(
            instructions="summarize",
            model_id="m",
            profile="openai",
            allowed_tools=["read_file"],
            model_allows_tools=False,
            cwd=str(tmp_path),
        )

    config = captured["config"]
    assert config.allowed_tools == []
    assert config.tools_suppressed_reason == SuppressionReason.MODEL_CAPABILITY.value
    # The coupling the task calls out: no tools means no working directory.
    assert config.cwd is None


def test_audit_gate_applies_to_the_fixed_tool_constant() -> None:
    """SC1, audit: the capability describes the model, not the caller (D1).

    The audit's tool list is a module constant, so the gate is what varies — feeding it
    a denied model must still empty the set.
    """
    gated, reason = resolve_effective_tools(
        list(_AUDIT_ALLOWED_TOOLS), model_allows_tools=False, suppressed=False
    )
    assert gated == []
    assert reason == SuppressionReason.MODEL_CAPABILITY.value
    # And the constant itself is untouched by the gate.
    assert len(_AUDIT_ALLOWED_TOOLS) > 0


# ---------------------------------------------------------------------------
# SC1a — the enumeration guard
# ---------------------------------------------------------------------------

# Every AgentConfig construction in src/ that sets allowed_tools. Each one must route
# its list through resolve_effective_tools first, or a model's tool_use = false is
# silently ignored on that path.
_SANCTIONED_TOOL_PASSING_SITES = {
    "review/review_client.py",
    "pipeline/actions/dispatch.py",
    "pipeline/summary_oneshot.py",
    "metrology/audit.py",
    "pr/composer.py",
}

_SC1A_FAILURE_HELP = """
{path} constructs AgentConfig with allowed_tools but is not a sanctioned gate site.

Every such call site must first route its declared tools through
squadron.tools.resolve_effective_tools, which applies the model's tool_use
capability and any run-level suppression. Passing a raw list here means a model
configured with tool_use = false is silently handed tool schemas anyway.

Fix the call site, then add it to _SANCTIONED_TOOL_PASSING_SITES in this test.
"""


def _agent_config_tool_sites() -> set[str]:
    """Return src-relative paths constructing AgentConfig with allowed_tools.

    Uses the AST rather than a regex over source text: a textual search cannot tell an
    AgentConfig call from the string "AgentConfig" in a docstring, and would be exactly
    the fragile pattern-matching the project rules warn against.
    """
    src_root = Path(__file__).resolve().parents[2] / "src" / "squadron"
    found: set[str] = set()
    for py_file in src_root.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name != "AgentConfig":
                continue
            # Key on the keyword, not on AgentConfig alone: the sites that pass no
            # allowed_tools at all are legitimately un-gated and must not be flagged.
            if any(kw.arg == "allowed_tools" for kw in node.keywords):
                found.add(py_file.relative_to(src_root).as_posix())
    return found


def test_every_tool_passing_agent_config_site_is_sanctioned() -> None:
    """SC1a: a new tool-passing call site fails until it routes through the gate."""
    found = _agent_config_tool_sites()
    unsanctioned = found - _SANCTIONED_TOOL_PASSING_SITES
    assert not unsanctioned, "".join(
        _SC1A_FAILURE_HELP.format(path=path) for path in sorted(unsanctioned)
    )


def test_sanctioned_site_list_has_no_stale_entries() -> None:
    """A sanctioned site that stopped passing tools should be removed from the list."""
    assert _SANCTIONED_TOOL_PASSING_SITES - _agent_config_tool_sites() == set()


def test_untooled_agent_config_sites_are_not_flagged() -> None:
    """The three no-tools sites are legitimately un-gated, not violations."""
    found = _agent_config_tool_sites()
    for untooled in ("providers/auth.py", "server/routes/agents.py"):
        assert untooled not in found


# ---------------------------------------------------------------------------
# T11/T12 — the --no-tools review flag, end to end through the CLI
# ---------------------------------------------------------------------------


def _invoke_review(
    tmp_path: Path, *, args: list[str], aliases_toml: str
) -> tuple[object, dict[str, object]]:
    """Invoke `sq review` with run_review_with_profile mocked, returning its kwargs."""
    target = tmp_path / "design.md"
    target.write_text("body")
    toml_file = tmp_path / "models.toml"
    toml_file.write_text(aliases_toml)

    captured: dict[str, object] = {}

    async def _fake_run(*_args: object, **kwargs: object) -> ReviewResult:
        captured.update(kwargs)
        return ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="## Summary\nPASS\n",
            template_name="code",
            input_files={"cwd": str(tmp_path)},
        )

    with (
        patch("squadron.cli.commands.review.run_review_with_profile", new=_fake_run),
        patch("squadron.models.aliases.models_toml_path", return_value=toml_file),
    ):
        result = CliRunner().invoke(app, args)
    return result, captured


def test_no_tools_flag_reaches_the_review_client(tmp_path: Path) -> None:
    """T12: the flag threads to the helper's suppressed argument."""
    _, captured = _invoke_review(
        tmp_path,
        args=["review", "code", "--files", "**/*", "--cwd", str(tmp_path), "--no-tools"],
        aliases_toml=_PLAIN_TOML,
    )
    assert captured["no_tools"] is True


def test_omitting_the_flag_changes_nothing(tmp_path: Path) -> None:
    """The default path is unchanged: no suppression, capability still allowed."""
    _, captured = _invoke_review(
        tmp_path,
        args=["review", "code", "--files", "**/*", "--cwd", str(tmp_path)],
        aliases_toml=_PLAIN_TOML,
    )
    assert captured["no_tools"] is False
    assert captured["model_allows_tools"] is True


def test_cli_reads_capability_before_alias_resolution(tmp_path: Path) -> None:
    """The CLI resolves the alias to a model id; the capability must be read first.

    Regression guard: reading tool_use after resolve_model_alias would look up a
    model id in a table keyed by alias name, silently never match, and leave every
    gated model un-gated.
    """
    _, captured = _invoke_review(
        tmp_path,
        args=[
            "review",
            "code",
            "--files",
            "**/*",
            "--cwd",
            str(tmp_path),
            "--model",
            "gated",
        ],
        aliases_toml=_GATED_TOML,
    )
    assert captured["model_allows_tools"] is False
    # And the alias really was resolved away, which is what makes this a trap.
    assert captured["model"] == "m"
