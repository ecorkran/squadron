"""Integration tests — load and validate all built-in pipeline definitions."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.data import data_dir
from squadron.pipeline.loader import load_pipeline, pipeline_identity, validate_pipeline
from squadron.pipeline.models import PipelineDefinition

# Every shipped pipeline, discovered from the directory rather than listed by hand, so a
# rename needs no test edit and a new pipeline can't skip load/validate coverage (#147).
_BUILTIN_NAMES = sorted(pipeline_identity(p) for p in (data_dir() / "pipelines").glob("*.yaml"))

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
        real_errors = [e for e in errors if not (e.field == "step_type" and "Unknown" in e.message)]
        assert real_errors == [], f"Unexpected errors for {name}: {real_errors}"


class TestBuiltInPipelineStructure:
    """Verify specific structure of built-in pipelines."""

    def test_slice_lifecycle_steps(self) -> None:
        defn = load_pipeline(
            "P456",
            project_dir=_NONEXISTENT,
            user_dir=_NONEXISTENT,
        )
        step_types = [s.step_type for s in defn.steps]
        assert step_types == [
            "design",
            "loop",
            "tasks",
            "loop",
            "summary",
            "compact",
            "summary",
            "branch",
            "implement",
            "loop",
            "devlog",
            "branch",
        ]

    def test_review_only_steps(self) -> None:
        defn = load_pipeline(
            "review",
            project_dir=_NONEXISTENT,
            user_dir=_NONEXISTENT,
        )
        assert len(defn.steps) == 1
        assert defn.steps[0].step_type == "review"

    @pytest.mark.parametrize(
        ("name", "source", "phase_step"),
        [
            ("slices-plan", 'cf.undesigned_slices("{plan}")', "design"),
            ("tasks-plan", 'cf.slices_needing_tasks("{plan}", "{accept-threshold}")', "tasks"),
        ],
    )
    def test_plan_batch_shape(self, name: str, source: str, phase_step: str) -> None:
        defn = load_pipeline(name, project_dir=_NONEXISTENT, user_dir=_NONEXISTENT)
        assert validate_pipeline(defn) == []
        assert len(defn.steps) == 1
        each = defn.steps[0]
        # The step name names the report file: {run_id}.slices.report.md.
        assert (each.step_type, each.name) == ("each", "slices")
        assert each.config["source"] == source
        assert each.config["on_item_failure"] == "continue"
        body = [next(iter(s)) for s in each.config["steps"]]
        assert body == ["summary", phase_step, "loop"]
        # Each item starts in a fresh SDK session; first so a failed item can't leak (#148).
        reset = each.config["steps"][0]["summary"]
        assert reset == {"template": "item-reset", "model": "{model}", "emit": ["rotate"]}

    def test_judge_cycle_shape(self) -> None:
        defn = load_pipeline(
            "judge-cycle",
            project_dir=_NONEXISTENT,
            user_dir=_NONEXISTENT,
        )
        # The judge runs first so the fix step has findings to work from.
        assert len(defn.steps) == 2
        assert defn.steps[0].step_type == "review"
        assert defn.steps[0].config["template"] == "judge.slice-vs-arch"
        loop_step = defn.steps[1]
        assert loop_step.step_type == "loop"
        assert loop_step.config["max"] == "{max-revisions}"
        assert defn.params["max-revisions"] == "2"
        assert loop_step.config["until"] == "review.pass"
        assert loop_step.config["on_exhaust"] == "checkpoint"

        body = loop_step.config["steps"]
        assert len(body) == 2
        assert next(iter(body[0])) == "dispatch"
        assert body[0]["dispatch"]["feedback"] == "review"
        assert next(iter(body[1])) == "review"
        assert body[1]["review"]["template"] == "judge.slice-vs-arch"
