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
