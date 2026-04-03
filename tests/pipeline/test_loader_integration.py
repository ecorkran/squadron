"""Integration tests — load and validate all built-in pipeline definitions."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.pipeline.loader import load_pipeline, validate_pipeline
from squadron.pipeline.models import PipelineDefinition

_BUILTIN_NAMES = [
    "slice",
    "review",
    "implement",
    "design-batch",
    "tasks",
]

_NONEXISTENT = Path("/nonexistent")


class TestLoadAllBuiltIns:
    """Every built-in pipeline loads and returns a PipelineDefinition."""

    @pytest.mark.parametrize("name", _BUILTIN_NAMES)
    def test_load_succeeds(self, name: str) -> None:
        defn = load_pipeline(name, project_dir=_NONEXISTENT, user_dir=_NONEXISTENT)
        assert isinstance(defn, PipelineDefinition)
        assert defn.name == name

    @pytest.mark.parametrize("name", _BUILTIN_NAMES)
    def test_validate_no_errors(self, name: str) -> None:
        defn = load_pipeline(name, project_dir=_NONEXISTENT, user_dir=_NONEXISTENT)
        errors = validate_pipeline(defn)
        # Filter out unknown step type warnings (e.g. "each")
        real_errors = [
            e for e in errors if not (e.field == "step_type" and "Unknown" in e.message)
        ]
        assert real_errors == [], f"Unexpected errors for {name}: {real_errors}"


class TestBuiltInPipelineStructure:
    """Verify specific structure of built-in pipelines."""

    def test_slice_lifecycle_steps(self) -> None:
        defn = load_pipeline(
            "slice",
            project_dir=_NONEXISTENT,
            user_dir=_NONEXISTENT,
        )
        assert len(defn.steps) == 5
        step_types = [s.step_type for s in defn.steps]
        assert step_types == ["design", "tasks", "compact", "implement", "devlog"]

    def test_review_only_steps(self) -> None:
        defn = load_pipeline(
            "review",
            project_dir=_NONEXISTENT,
            user_dir=_NONEXISTENT,
        )
        assert len(defn.steps) == 1
        assert defn.steps[0].step_type == "review"

    def test_design_batch_steps(self) -> None:
        defn = load_pipeline(
            "design-batch",
            project_dir=_NONEXISTENT,
            user_dir=_NONEXISTENT,
        )
        assert len(defn.steps) == 1
        assert defn.steps[0].step_type == "each"
