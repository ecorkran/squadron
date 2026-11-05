"""Tests for _render_dispatch profile-aware branching."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from squadron.core.models import Effort
from squadron.pipeline.prompt_renderer import _render_dispatch
from squadron.pipeline.resolver import ModelPoolNotImplemented, ModelResolver, ResolvedModel


def _mock_resolver(model_id: str, profile: str | None, effort: Effort | None = None):
    resolver = MagicMock()
    resolver.resolve_full.return_value = ResolvedModel(model_id, profile, effort=effort)
    return resolver


# ---------------------------------------------------------------------------
# SDK profile path
# ---------------------------------------------------------------------------


def test_render_dispatch_sdk_profile_emits_in_session_instruction() -> None:
    """SDK profile: model_switch set, command is None."""
    config: dict[str, object] = {"model": "claude-opus-4"}
    params: dict[str, object] = {}
    resolver = _mock_resolver("claude-opus-4-7", "sdk")

    result = _render_dispatch(config, params, resolver)

    assert result.model_switch == "/model claude-opus-4"
    assert result.command is None
    assert result.model == "claude-opus-4-7"


def test_render_dispatch_sdk_none_profile_emits_in_session_instruction() -> None:
    """None profile (default SDK): model_switch set, command is None."""
    config: dict[str, object] = {"model": "claude-opus-4"}
    params: dict[str, object] = {}
    resolver = _mock_resolver("claude-opus-4-7", None)

    result = _render_dispatch(config, params, resolver)

    assert result.model_switch is not None
    assert result.command is None


# ---------------------------------------------------------------------------
# Non-SDK profile path
# ---------------------------------------------------------------------------


def test_render_dispatch_non_sdk_profile_emits_command() -> None:
    """Non-SDK profile: command starts with sq _dispatch-run, model_switch is None."""
    config: dict[str, object] = {"model": "minimax"}
    params: dict[str, object] = {}
    resolver = _mock_resolver("minimax-text-01", "openrouter")

    result = _render_dispatch(config, params, resolver)

    assert result.command is not None
    assert result.command.startswith("sq _dispatch-run")
    assert result.model_switch is None


def test_render_dispatch_command_contains_prompt_file_placeholder() -> None:
    """Non-SDK command includes the {tmp_path} placeholder."""
    config: dict[str, object] = {"model": "minimax"}
    params: dict[str, object] = {}
    resolver = _mock_resolver("minimax-text-01", "openrouter")

    result = _render_dispatch(config, params, resolver)

    assert result.command is not None
    assert "--prompt-file {tmp_path}" in result.command


def test_render_dispatch_command_contains_model_and_profile() -> None:
    """Non-SDK command includes --model and --profile flags."""
    config: dict[str, object] = {"model": "minimax"}
    params: dict[str, object] = {}
    resolver = _mock_resolver("minimax-text-01", "openrouter")

    result = _render_dispatch(config, params, resolver)

    assert result.command is not None
    assert "--model minimax-text-01" in result.command
    assert "--profile openrouter" in result.command


def test_render_dispatch_extra_params_forwarded() -> None:
    """Non-internal params forwarded as --param flags."""
    config: dict[str, object] = {"model": "minimax"}
    params: dict[str, object] = {"step": "183", "model": "minimax"}
    resolver = _mock_resolver("minimax-text-01", "openrouter")

    result = _render_dispatch(config, params, resolver)

    assert result.command is not None
    assert "--param" in result.command
    assert "step=183" in result.command
    # internal 'model' key excluded
    model_param_count = result.command.count("--param")
    assert model_param_count == 1  # only step=183, not model=minimax


def test_render_dispatch_internal_params_excluded() -> None:
    """Internal keys never appear as --param entries."""
    config: dict[str, object] = {"model": "minimax"}
    internal_keys = [
        "_fan_out_branch_index",
        "prompt",
        "system_prompt",
        "model",
        "step_model",
        "profile",
    ]
    params: dict[str, object] = {k: "val" for k in internal_keys}
    resolver = _mock_resolver("minimax-text-01", "openrouter")

    result = _render_dispatch(config, params, resolver)

    assert result.command is not None
    assert "--param" not in result.command


# ---------------------------------------------------------------------------
# No model param
# ---------------------------------------------------------------------------


def test_render_dispatch_no_model_param() -> None:
    """No model in config: no model_switch, no command, SDK in-session instruction."""
    config: dict[str, object] = {}
    params: dict[str, object] = {}
    resolver = _mock_resolver("claude-opus-4-7", "sdk")

    result = _render_dispatch(config, params, resolver)

    assert result.model_switch is None
    assert result.command is None
    resolver.resolve_full.assert_not_called()


# ---------------------------------------------------------------------------
# Effort (slice 420 D4)
# ---------------------------------------------------------------------------


def test_render_dispatch_command_carries_the_alias_effort() -> None:
    import shlex

    resolver = _mock_resolver("minimax-text-01", "openrouter", Effort.low)

    result = _render_dispatch({"model": "minimax-low"}, {}, resolver)

    assert result.command is not None
    parsed = shlex.split(result.command)
    assert parsed[parsed.index("--effort") + 1] == "low"


def test_render_dispatch_command_has_no_effort_when_the_alias_sets_none() -> None:
    resolver = _mock_resolver("minimax-text-01", "openrouter")

    result = _render_dispatch({"model": "minimax"}, {}, resolver)

    assert result.command is not None
    assert "--effort" not in result.command


def test_render_dispatch_sdk_alias_with_effort_emits_no_command() -> None:
    resolver = _mock_resolver("claude-opus-4-7", "sdk", Effort.high)

    result = _render_dispatch({"model": "claude-opus-4"}, {}, resolver)

    assert result.command is None


# ---------------------------------------------------------------------------
# Mutual exclusion invariant
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model,profile",
    [
        ("claude-opus-4", "sdk"),
        ("claude-opus-4", None),
        ("minimax", "openrouter"),
    ],
)
def test_render_dispatch_never_emits_both_command_and_model_switch(
    model: str, profile: str | None
) -> None:
    """command and model_switch are never both set."""
    config: dict[str, object] = {"model": model}
    params: dict[str, object] = {}
    resolver = _mock_resolver(f"{model}-resolved", profile)

    result = _render_dispatch(config, params, resolver)

    assert not (result.command is not None and result.model_switch is not None)


# ---------------------------------------------------------------------------
# Unresolvable model — resolver failure must propagate, not be swallowed
# ---------------------------------------------------------------------------


def test_render_dispatch_unresolvable_pool_propagates() -> None:
    """A misconfigured pool: reference must raise, not silently dispatch to
    the literal ``pool:...`` string as if it were a model id.

    Regression guard for the BLE001 fix at prompt_renderer.py:158 — the
    resolver failure used to be caught by a bare ``except Exception`` and
    replaced with ``model_id = action_model, profile = None``, which fed
    the raw ``pool:review`` string into is_sdk_profile() as though it were
    a real model. ModelResolver has no pool backend configured here, so
    resolving a ``pool:`` reference must raise ModelPoolNotImplemented.
    """
    config: dict[str, object] = {"model": "pool:review"}
    params: dict[str, object] = {}
    resolver = ModelResolver()  # no pool_backend configured

    with pytest.raises(ModelPoolNotImplemented):
        _render_dispatch(config, params, resolver)
