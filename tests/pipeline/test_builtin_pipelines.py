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
    }
    (each,) = definition.steps
    assert (each.step_type, each.name) == ("each", "slices")
    assert each.config["source"] == 'cf.slices_ready_to_implement("{plan}", "{accept-threshold}")'
    assert each.config["on_item_failure"] == "continue"
    body = [next(iter(s)) for s in each.config["steps"]]  # type: ignore[union-attr]
    assert body == ["summary", "branch", "implement", "loop", "devlog", "branch"]


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
