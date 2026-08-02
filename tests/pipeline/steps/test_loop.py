"""Unit tests for LoopStepType — validation, expand, and registration."""

from __future__ import annotations

from squadron.pipeline.models import StepConfig
from squadron.pipeline.steps import bootstrap_step_types, get_step_type
from squadron.pipeline.steps.loop import LoopStepType

bootstrap_step_types()  # registers all step types, including "loop"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _step(config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type="loop", name="test-loop", config=config)


def _make() -> LoopStepType:
    return LoopStepType()


def _fields(errors: list) -> list[str]:
    return [e.field for e in errors]


def _messages(errors: list) -> list[str]:
    return [e.message for e in errors]


# ---------------------------------------------------------------------------
# Task 5 — Validation rules
# ---------------------------------------------------------------------------


def test_missing_max_produces_error() -> None:
    errors = _make().validate(_step({"steps": [{"review": {}}]}))
    assert "max" in _fields(errors)


def test_max_not_int_produces_error() -> None:
    errors = _make().validate(_step({"max": "3", "steps": [{"review": {}}]}))
    assert "max" in _fields(errors)


def test_max_zero_produces_error() -> None:
    errors = _make().validate(_step({"max": 0, "steps": [{"review": {}}]}))
    assert "max" in _fields(errors)


def test_max_negative_produces_error() -> None:
    errors = _make().validate(_step({"max": -1, "steps": [{"review": {}}]}))
    assert "max" in _fields(errors)


def test_invalid_until_value_produces_error() -> None:
    errors = _make().validate(_step({"max": 3, "until": "never", "steps": [{"review": {}}]}))
    assert "until" in _fields(errors)
    assert any("never" in m for m in _messages(errors))


def test_invalid_on_exhaust_value_produces_error() -> None:
    errors = _make().validate(_step({"max": 3, "on_exhaust": "retry", "steps": [{"review": {}}]}))
    assert "on_exhaust" in _fields(errors)


def test_strategy_not_string_produces_error() -> None:
    errors = _make().validate(_step({"max": 3, "strategy": 42, "steps": [{"review": {}}]}))
    assert "strategy" in _fields(errors)


def test_missing_steps_produces_error() -> None:
    errors = _make().validate(_step({"max": 3}))
    assert "steps" in _fields(errors)


def test_steps_not_list_produces_error() -> None:
    errors = _make().validate(_step({"max": 3, "steps": "bad"}))
    assert "steps" in _fields(errors)


def test_steps_empty_list_produces_error() -> None:
    errors = _make().validate(_step({"max": 3, "steps": []}))
    assert "steps" in _fields(errors)


def test_inner_step_with_loop_subfield_produces_nested_loop_error() -> None:
    """Ban (a): inner step config carries a loop: sub-field."""
    errors = _make().validate(
        _step(
            {
                "max": 3,
                "steps": [{"review": {"loop": {"max": 2}}}],
            }
        )
    )
    assert "steps" in _fields(errors)
    assert any("loop:" in m and "sub-field" in m for m in _messages(errors))


def test_inner_step_with_loop_type_produces_nested_loop_error() -> None:
    """Ban (b): inner step type is loop."""
    errors = _make().validate(
        _step(
            {
                "max": 3,
                "steps": [{"loop": {"max": 2, "steps": [{"review": {}}]}}],
            }
        )
    )
    assert "steps" in _fields(errors)
    assert any("type 'loop'" in m for m in _messages(errors))


def test_valid_config_no_errors() -> None:
    """Minimal valid config — max, steps, no optional fields."""
    errors = _make().validate(_step({"max": 3, "steps": [{"review": {}}]}))
    assert errors == []


def test_valid_config_with_all_options_no_errors() -> None:
    """All optional fields with valid values produce zero errors."""
    errors = _make().validate(
        _step(
            {
                "max": 5,
                "until": "review.pass",
                "on_exhaust": "checkpoint",
                "strategy": "weighted-decay",
                "steps": [{"dispatch": {}}, {"review": {}}],
            }
        )
    )
    assert errors == []


# ---------------------------------------------------------------------------
# Task 6 — expand() and registration
# ---------------------------------------------------------------------------


def test_expand_returns_empty_list() -> None:
    result = _make().expand(_step({"max": 3, "steps": [{"review": {}}]}))
    assert result == []


def test_get_step_type_returns_loop_step_type_instance() -> None:
    impl = get_step_type("loop")
    assert isinstance(impl, LoopStepType)


# ---------------------------------------------------------------------------
# Multi-verdict validation — ambiguous until: gating (#43)
# ---------------------------------------------------------------------------


def test_two_review_steps_with_until_produces_error() -> None:
    errors = _make().validate(
        _step(
            {
                "max": 3,
                "until": "review.pass",
                "steps": [
                    {"review": {"template": "design"}},
                    {"review": {"template": "tasks"}},
                ],
            }
        )
    )
    assert "steps" in _fields(errors)
    assert any("verdict-bearing" in m for m in _messages(errors))


def test_phase_with_inline_review_then_bare_review_with_until_produces_error() -> None:
    """Proves the check inspects expanded actions, not step-type names."""
    errors = _make().validate(
        _step(
            {
                "max": 3,
                "until": "review.pass",
                "steps": [
                    {"design": {"phase": 4, "review": "slice"}},
                    {"review": {"template": "tasks"}},
                ],
            }
        )
    )
    assert "steps" in _fields(errors)
    assert any("verdict-bearing" in m for m in _messages(errors))


def test_two_verdict_steps_without_until_no_error() -> None:
    errors = _make().validate(
        _step(
            {
                "max": 3,
                "steps": [{"review": {}}, {"review": {}}],
            }
        )
    )
    assert errors == []


def test_one_verdict_step_with_until_no_error() -> None:
    errors = _make().validate(
        _step(
            {
                "max": 3,
                "until": "review.pass",
                "steps": [{"dispatch": {}}, {"review": {}}],
            }
        )
    )
    assert errors == []


# ---------------------------------------------------------------------------
# commit_each_iteration validation (slice 911 Part A2)
# ---------------------------------------------------------------------------


def test_commit_each_iteration_not_bool_produces_error() -> None:
    errors = _make().validate(
        _step({"max": 3, "commit_each_iteration": "yes", "steps": [{"review": {}}]})
    )
    assert "commit_each_iteration" in _fields(errors)


def test_commit_each_iteration_rejects_int_zero_or_one() -> None:
    """bool is a subclass of int, but a bare 0/1 literal must still be rejected."""
    errors = _make().validate(_step({"max": 3, "commit_each_iteration": 1, "steps": [{"review": {}}]}))
    assert "commit_each_iteration" in _fields(errors)


def test_commit_each_iteration_true_with_phase_step_produces_error() -> None:
    errors = _make().validate(
        _step(
            {
                "max": 3,
                "commit_each_iteration": True,
                "steps": [{"design": {"phase": 4, "model": "opus"}}],
            }
        )
    )
    assert "commit_each_iteration" in _fields(errors)
    assert any("already commits" in m and "design" in m for m in _messages(errors))


def test_commit_each_iteration_true_with_dispatch_review_body_no_error() -> None:
    errors = _make().validate(
        _step(
            {
                "max": 3,
                "commit_each_iteration": True,
                "steps": [{"dispatch": {}}, {"review": {}}],
            }
        )
    )
    assert errors == []


def test_commit_each_iteration_absent_no_error() -> None:
    """Default false — existing loop pipelines are unaffected."""
    errors = _make().validate(_step({"max": 3, "steps": [{"design": {"phase": 4, "model": "opus"}}]}))
    assert errors == []


def test_commit_each_iteration_true_skips_malformed_inner_step() -> None:
    """Regression guard: an inner step with an incomplete config (failing its
    own validate()) must not crash the commit-detection walk via expand()'s
    KeyError on 'phase' (see LoopStepType._walk_valid_inner_action_types)."""
    errors = _make().validate(
        _step(
            {
                "max": 3,
                "commit_each_iteration": True,
                "steps": [{"design": {}}],  # missing required "phase"
            }
        )
    )
    assert "commit_each_iteration" not in _fields(errors)
