"""Tests for _render_dispatch profile-aware branching."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from squadron.pipeline.prompt_renderer import _render_dispatch


def _mock_resolver(model_id: str, profile: str | None):
    resolver = MagicMock()
    resolver.resolve.return_value = (model_id, profile)
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
    resolver.resolve.assert_not_called()


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
