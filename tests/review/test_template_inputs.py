"""Tests for the template-input registry (template_inputs.py)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from squadron.review.persistence import SliceInfo
from squadron.review.template_inputs import TEMPLATE_INPUTS, resolve_template_inputs

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

SLICE_INFO: SliceInfo = SliceInfo(
    index=194,
    name="loop-step-type",
    slice_name="loop-step-type-for-multi-step-bodies",
    design_file="project-documents/user/slices/194-slice.loop-step-type-for-multi-step-bodies.md",
    task_files=["194-tasks.loop-step-type-for-multi-step-bodies.md"],
    arch_file="project-documents/user/architecture/100-arch.orchestration-v2.md",
)

CWD = "/tmp/fake-cwd"
DIFF_RANGE = "abc123...slice-194"


# ---------------------------------------------------------------------------
# Registry entries exist
# ---------------------------------------------------------------------------


def test_registry_has_all_templates() -> None:
    assert set(TEMPLATE_INPUTS.keys()) == {"slice", "tasks", "arch", "code"}


# ---------------------------------------------------------------------------
# slice template
# ---------------------------------------------------------------------------


def test_slice_template_populates_input_and_against() -> None:
    inputs: dict[str, str] = {}
    resolve_template_inputs("slice", SLICE_INFO, CWD, inputs)
    assert inputs["input"] == SLICE_INFO["design_file"]
    assert inputs["against"] == SLICE_INFO["arch_file"]


# ---------------------------------------------------------------------------
# tasks template
# ---------------------------------------------------------------------------


def test_tasks_template_populates_input_and_against() -> None:
    inputs: dict[str, str] = {}
    resolve_template_inputs("tasks", SLICE_INFO, CWD, inputs)
    assert inputs["input"] == (
        f"project-documents/user/tasks/{SLICE_INFO['task_files'][0]}"
    )
    assert inputs["against"] == SLICE_INFO["design_file"]


def test_tasks_template_no_input_when_task_files_empty() -> None:
    """source returning None must not set the key (not even to None)."""
    info: SliceInfo = {**SLICE_INFO, "task_files": []}  # type: ignore[typeddict-item]
    inputs: dict[str, str] = {}
    resolve_template_inputs("tasks", info, CWD, inputs)
    assert "input" not in inputs


# ---------------------------------------------------------------------------
# arch template
# ---------------------------------------------------------------------------


def test_arch_template_populates_input() -> None:
    inputs: dict[str, str] = {}
    resolve_template_inputs("arch", SLICE_INFO, CWD, inputs)
    assert inputs["input"] == SLICE_INFO["arch_file"]


# ---------------------------------------------------------------------------
# code template
# ---------------------------------------------------------------------------


def test_code_template_populates_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    with patch(
        "squadron.review.template_inputs.resolve_slice_diff_range",
        return_value=DIFF_RANGE,
    ) as mock_diff:
        inputs: dict[str, str] = {}
        resolve_template_inputs("code", SLICE_INFO, CWD, inputs)
        mock_diff.assert_called_once_with(SLICE_INFO["index"], CWD)
        assert inputs["diff"] == DIFF_RANGE


def test_code_template_no_diff_when_source_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with patch(
        "squadron.review.template_inputs.resolve_slice_diff_range",
        return_value=None,
    ):
        inputs: dict[str, str] = {}
        resolve_template_inputs("code", SLICE_INFO, CWD, inputs)
        assert "diff" not in inputs


# ---------------------------------------------------------------------------
# Unknown template
# ---------------------------------------------------------------------------


def test_unknown_template_leaves_inputs_unchanged() -> None:
    inputs: dict[str, str] = {"existing": "value"}
    resolve_template_inputs("nonexistent", SLICE_INFO, CWD, inputs)
    assert inputs == {"existing": "value"}


def test_unknown_template_does_not_raise() -> None:
    inputs: dict[str, str] = {}
    resolve_template_inputs("totally-unknown", SLICE_INFO, CWD, inputs)
    # No exception, no side effects
    assert inputs == {}
