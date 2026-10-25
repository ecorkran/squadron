"""Every built-in pipeline loads, validates, and classifies without --model.

``sq run`` classifies a pipeline before any step runs; a built-in that only
passes with a CLI model override fails for every user who omits it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import squadron.cli.commands.run  # noqa: F401  # registers step and action types
from squadron.data import data_dir
from squadron.pipeline.classification import classify_pipeline
from squadron.pipeline.intelligence.pools.backend import DefaultPoolBackend
from squadron.pipeline.loader import load_pipeline, validate_pipeline
from squadron.pipeline.resolver import ModelResolver

_BUILTIN_PIPELINES = sorted(p.stem for p in (data_dir() / "pipelines").glob("*.yaml"))


def test_builtin_pipelines_found() -> None:
    assert _BUILTIN_PIPELINES, f"no pipelines under {Path(data_dir()) / 'pipelines'}"


@pytest.mark.parametrize("name", _BUILTIN_PIPELINES)
def test_builtin_pipeline_validates_and_classifies(name: str) -> None:
    definition = load_pipeline(name)
    assert validate_pipeline(definition) == []

    pool_backend = DefaultPoolBackend()
    resolver = ModelResolver(pipeline_model=definition.model, pool_backend=pool_backend)
    classify_pipeline(definition, resolver, pool_backend)


def test_implement_plan_params_and_shape() -> None:
    """slice 197 D1."""
    definition = load_pipeline("implement-plan")
    assert definition.params == {
        "plan": "required",
        "model": "sonnet",
        "review-model": "minimax",
        "max-revisions": "2",
        "pass-threshold": "review.pass",
        "accept-threshold": "review.concerns_or_better",
        "merge": "true",
    }
    (each,) = definition.steps
    assert (each.step_type, each.name) == ("each", "slices")
    assert each.config["source"] == 'cf.slices_ready_to_implement("{plan}", "{accept-threshold}")'
    assert each.config["on_item_failure"] == "continue"
    body = [next(iter(s)) for s in each.config["steps"]]  # type: ignore[union-attr]
    assert body == ["summary", "branch", "implement", "dispatch", "loop", "devlog", "branch"]


# ---------------------------------------------------------------------------
# Drift: single-slice code pipelines run the implement-plan body (slice 197 D10)
# ---------------------------------------------------------------------------

_SINGLE_SLICE_CODE_PIPELINES = ("P6", "implement", "P56", "P456")
# Keys that legitimately differ: the batch names its plan and item, a single-slice
# run uses the run's {slice}; and the batch flags on exhaust where a single run pauses.
_NORMALIZED_KEYS = frozenset({"slice", "plan", "on_exhaust"})


def _raw_steps(name: str) -> list[dict[str, object]]:
    import yaml

    text = (data_dir() / "pipelines" / f"{name}.yaml").read_text()
    return yaml.safe_load(text)["steps"]


def _normalize(value: object) -> object:
    if value == {"devlog": "auto"}:  # scalar shorthand for {mode: auto}
        return {"devlog": {"mode": "auto"}}
    if isinstance(value, dict):
        return {
            k: _normalize(v)
            for k, v in value.items()  # type: ignore[union-attr]
            if k not in _NORMALIZED_KEYS
        }
    if isinstance(value, list):
        return [_normalize(v) for v in value]  # type: ignore[union-attr]
    return value


def _enter_through_merge(steps: list[dict[str, object]]) -> list[dict[str, object]]:
    def op(step: dict[str, object]) -> object:
        branch = step.get("branch")
        return branch.get("op") if isinstance(branch, dict) else None  # type: ignore[union-attr]

    start = next(i for i, s in enumerate(steps) if op(s) == "enter")
    end = next(i for i, s in enumerate(steps) if op(s) == "merge")
    return steps[start : end + 1]


def _batch_body() -> list[dict[str, object]]:
    (each,) = _raw_steps("implement-plan")
    return each["each"]["steps"]  # type: ignore[index]


@pytest.mark.parametrize("name", _SINGLE_SLICE_CODE_PIPELINES)
def test_single_slice_code_pipelines_match_the_batch_body(name: str) -> None:
    assert _normalize(_enter_through_merge(_raw_steps(name))) == _normalize(
        _enter_through_merge(_batch_body())
    )


# ---------------------------------------------------------------------------
# Squash placement (slice 948 D6)
# ---------------------------------------------------------------------------

# (pipeline, [(index of the planning loop in the step list, squash subject)]); for the
# batch pipelines the indices are inside the each body.
_SQUASH_PLACEMENT: list[tuple[str, list[tuple[int, str]]]] = [
    ("P4", [(1, "design")]),
    ("P5", [(1, "tasks")]),
    ("P45", [(1, "design"), (4, "tasks")]),
    ("P456", [(1, "design"), (4, "tasks")]),
    ("P56", [(1, "tasks")]),
    ("slices-plan", [(2, "design")]),
    ("tasks-plan", [(2, "tasks")]),
]


def _steps(name: str) -> list[tuple[str, dict[str, object]]]:
    """The pipeline's top-level steps, or its each body, as (type, config) pairs."""
    definition = load_pipeline(name)
    if definition.steps[0].step_type == "each":
        body: list[dict[str, dict[str, object]]] = definition.steps[0].config["steps"]  # type: ignore[assignment]
        return [next(iter(step.items())) for step in body]
    return [(step.step_type, step.config) for step in definition.steps]


@pytest.mark.parametrize(("name", "placements"), _SQUASH_PLACEMENT)
def test_squash_follows_each_planning_loop(name: str, placements: list[tuple[int, str]]) -> None:
    steps = _steps(name)
    for loop_index, subject in placements:
        assert steps[loop_index][0] == "loop"
        squash_type, squash_config = steps[loop_index + 1]
        assert squash_type == "squash"
        assert squash_config["subject"] == subject
    assert sum(1 for step_type, _ in steps if step_type == "squash") == len(placements)


def _is_code_review_loop(step_type: str, config: dict[str, object]) -> bool:
    body = config.get("steps") if step_type == "loop" else None
    if not isinstance(body, list):
        return False
    return any(
        isinstance(review := step.get("review"), dict) and review.get("template") == "code"  # type: ignore[union-attr]
        for step in body  # type: ignore[union-attr]
    )


@pytest.mark.parametrize("name", ["P456", "P56", "P6"])
def test_no_squash_follows_a_code_review_loop(name: str) -> None:
    steps = _steps(name)
    code_loops = [i for i, (t, c) in enumerate(steps) if _is_code_review_loop(t, c)]
    assert code_loops, f"{name} has no code-review loop to check"
    for index in code_loops:
        following = steps[index + 1][0] if index + 1 < len(steps) else None
        assert following != "squash"
