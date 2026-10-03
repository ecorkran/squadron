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
