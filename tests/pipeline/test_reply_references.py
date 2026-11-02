"""Load-time checks on a dispatch step's ``reply_from`` (slice 949 D3, Criterion 6)."""

from __future__ import annotations

import pytest

import squadron.cli.commands.run  # noqa: F401  # registers step and action types
from squadron.pipeline.loader import validate_pipeline
from squadron.pipeline.models import PipelineDefinition, StepConfig

_NESTED_ERROR = "supported on top-level steps only"


def _dispatch(name: str, **config: object) -> StepConfig:
    return StepConfig(step_type="dispatch", name=name, config={"prompt": "p", **config})


def _errors(*steps: StepConfig, params: dict[str, object] | None = None) -> list[tuple[str, str]]:
    definition = PipelineDefinition(name="t", description="t", params=params or {}, steps=list(steps))
    return [(e.field, e.message) for e in validate_pipeline(definition)]


def test_reply_from_an_earlier_dispatch_step_is_valid() -> None:
    assert _errors(_dispatch("extract"), _dispatch("answer", reply_from="extract")) == []


def test_reply_from_a_placeholder_is_skipped() -> None:
    assert _errors(_dispatch("answer", reply_from="{producer}"), params={"producer": "extract"}) == []


def test_reply_from_a_later_step_fails() -> None:
    ((field, message),) = _errors(_dispatch("answer", reply_from="extract"), _dispatch("extract"))
    assert field == "steps[answer].reply_from"
    assert "not an earlier step" in message


def test_reply_from_a_missing_step_fails() -> None:
    ((field, message),) = _errors(_dispatch("answer", reply_from="nope"))
    assert field == "steps[answer].reply_from"
    assert "'nope'" in message


def test_reply_from_a_non_dispatch_step_fails() -> None:
    summary = StepConfig(step_type="summary", name="sum", config={})
    ((_, message),) = _errors(summary, _dispatch("answer", reply_from="sum"))
    assert "must be a dispatch step" in message


def _nested(container: str, inner: StepConfig) -> StepConfig:
    body = {inner.step_type: {"name": inner.name, **inner.config}}
    configs: dict[str, dict[str, object]] = {
        "loop": {"max": 2, "steps": [body]},
        "each": {"source": "cf.slices()", "as": "s", "steps": [body]},
        "fan_out": {"models": ["sonnet"], "inner": body},
    }
    return StepConfig(step_type=container, name="outer", config=configs[container])


@pytest.mark.parametrize("container", ["loop", "each", "fan_out"])
def test_reply_from_inside_a_container_body_fails(container: str) -> None:
    outer = _nested(container, _dispatch("inner", reply_from="extract"))
    errors = _errors(_dispatch("extract"), outer)
    assert ("steps[inner].reply_from", f"'reply_from' is {_NESTED_ERROR}") in errors


@pytest.mark.parametrize("container", ["loop", "each", "fan_out"])
def test_a_container_body_without_reply_from_is_unaffected(container: str) -> None:
    outer = _nested(container, _dispatch("inner"))
    assert not [e for e in _errors(_dispatch("extract"), outer) if _NESTED_ERROR in e[1]]
