"""Unit tests for validate_allowed_tools (slice 263, task 2)."""

from __future__ import annotations

from squadron import tools
from squadron.pipeline.models import StepConfig
from squadron.pipeline.steps.utils import validate_allowed_tools


def _step(config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type="dispatch", name="test-dispatch", config=config)


def test_absent_field_returns_no_errors() -> None:
    assert validate_allowed_tools(_step({"prompt": "hi"}), "dispatch") == []


def test_valid_tool_names_return_no_errors() -> None:
    step = _step({"allowed_tools": ["read_file", "write_file"]})
    assert validate_allowed_tools(step, "dispatch") == []


def test_non_list_value_returns_type_error() -> None:
    # `allowed_tools: read_file` without brackets is the common YAML mistake.
    errors = validate_allowed_tools(_step({"allowed_tools": "read_file"}), "dispatch")
    assert len(errors) == 1
    assert errors[0].field == "allowed_tools"
    assert "list" in errors[0].message


def test_list_with_non_string_returns_type_error() -> None:
    errors = validate_allowed_tools(_step({"allowed_tools": ["read_file", 42]}), "dispatch")
    assert len(errors) == 1
    assert errors[0].field == "allowed_tools"
    assert "42" in errors[0].message


def test_unknown_tool_name_returns_error() -> None:
    errors = validate_allowed_tools(_step({"allowed_tools": ["read_fil"]}), "dispatch")
    assert len(errors) == 1
    assert "read_fil" in errors[0].message
    # The message must also point at what is available.
    for registered in tools.list_tools():
        assert registered in errors[0].message


def test_two_unknown_names_return_two_errors() -> None:
    step = _step({"allowed_tools": ["read_fil", "writ_file"]})
    errors = validate_allowed_tools(step, "dispatch")
    assert len(errors) == 2
    assert "read_fil" in errors[0].message
    assert "writ_file" in errors[1].message


def test_error_carries_action_type() -> None:
    errors = validate_allowed_tools(_step({"allowed_tools": ["nope"]}), "design")
    assert errors[0].action_type == "design"


def test_non_string_and_unknown_names_accumulate() -> None:
    """Review finding 4: a bad element must not hide the errors after it."""
    step = _step({"allowed_tools": [42, "read_fil", "read_file"]})
    errors = validate_allowed_tools(step, "dispatch")
    assert len(errors) == 2
    assert "42" in errors[0].message
    assert "read_fil" in errors[1].message
