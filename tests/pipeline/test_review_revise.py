"""Tests for the review-revise composition (slice 941 D1, D2, D4)."""

from __future__ import annotations

import copy
from functools import partial
from pathlib import Path

import pytest

import squadron.pipeline.review_revise as review_revise
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import PipelineDefinition, StepConfig
from squadron.pipeline.review_revise import (
    REVISE_PIPELINE_BY_KIND,
    build_review_revise_definition,
)
from squadron.pipeline.steps import StepTypeName
from squadron.review.templates import BuiltinReviewTemplate

_NONEXISTENT = Path("/nonexistent-941")

# The shipped pipelines, not any project or user override on this machine.
_shipped = partial(load_pipeline, project_dir=_NONEXISTENT, user_dir=_NONEXISTENT)


@pytest.fixture(autouse=True)
def shipped_pipelines(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(review_revise, "load_pipeline", _shipped)


def _serve(monkeypatch: pytest.MonkeyPatch, definition: PipelineDefinition) -> None:
    monkeypatch.setattr(review_revise, "load_pipeline", lambda name: definition)


def _p4() -> PipelineDefinition:
    return _shipped("P4")


def _loop(definition: PipelineDefinition) -> StepConfig:
    return next(s for s in definition.steps if s.step_type == StepTypeName.LOOP)


@pytest.mark.parametrize("kind", list(REVISE_PIPELINE_BY_KIND))
def test_builds_review_then_loop_for_each_kind(kind: BuiltinReviewTemplate) -> None:
    definition = build_review_revise_definition(kind)
    review, loop = definition.steps

    assert [review.step_type, loop.step_type] == [StepTypeName.REVIEW, StepTypeName.LOOP]
    assert review.config["template"] == kind.value
    assert loop.config["on_exhaust"] == "fail"
    assert loop.config["skip_if_met"] is True
    assert definition.params == _shipped(REVISE_PIPELINE_BY_KIND[kind]).params


def test_review_step_copies_the_loop_bodys_review_config() -> None:
    review = build_review_revise_definition(BuiltinReviewTemplate.SLICE).steps[0]

    assert review.config == {
        "template": "slice",
        "model": "{review-model}",
        "slice": "{slice}",
    }


@pytest.mark.parametrize("kind", [BuiltinReviewTemplate.SLICE, BuiltinReviewTemplate.TASKS])
def test_revise_dispatch_keeps_its_artifact(kind: BuiltinReviewTemplate) -> None:
    """The artifact key turns on revision and usage stamping, so the copy keeps it (#236)."""
    shipped = [
        s["dispatch"]
        for s in _loop(_shipped(REVISE_PIPELINE_BY_KIND[kind])).config["steps"]
        if "dispatch" in s
    ]
    assert shipped and all("artifact" in d for d in shipped)

    loop = _loop(build_review_revise_definition(kind))
    dispatches = [s["dispatch"] for s in loop.config["steps"] if "dispatch" in s]
    assert dispatches == shipped


def test_code_kind_uses_the_named_loop_of_p6() -> None:
    loop = build_review_revise_definition(BuiltinReviewTemplate.CODE).steps[1]

    assert loop.name == "revise-code"


def test_loaded_pipeline_is_unchanged_after_building(monkeypatch: pytest.MonkeyPatch) -> None:
    loaded = _p4()
    before = copy.deepcopy(loaded)
    _serve(monkeypatch, loaded)

    definition = build_review_revise_definition(BuiltinReviewTemplate.SLICE)
    definition.steps[1].config["max"] = "changed"
    definition.steps[0].config["template"] = "changed"
    definition.params["slice"] = "changed"

    assert loaded == before
    assert _loop(before).config["on_exhaust"] == "checkpoint"


def test_project_override_of_the_pipeline_is_picked_up(monkeypatch: pytest.MonkeyPatch) -> None:
    override = _p4()
    _loop(override).config["accept_if"] = "review.pass"
    _serve(monkeypatch, override)

    loop = build_review_revise_definition(BuiltinReviewTemplate.SLICE).steps[1]

    assert loop.config["accept_if"] == "review.pass"


def test_unmapped_kind_raises() -> None:
    with pytest.raises(ValueError, match="arch"):
        build_review_revise_definition(BuiltinReviewTemplate.ARCH)


def test_zero_loops_raises_naming_the_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    definition = _p4()
    definition.steps = [s for s in definition.steps if s.step_type != StepTypeName.LOOP]
    _serve(monkeypatch, definition)

    with pytest.raises(ValueError, match=r"'P4'.*exactly one loop.*found 0"):
        build_review_revise_definition(BuiltinReviewTemplate.SLICE)


def test_two_loops_raises_naming_the_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    definition = _p4()
    definition.steps.append(copy.deepcopy(_loop(definition)))
    _serve(monkeypatch, definition)

    with pytest.raises(ValueError, match=r"'P4'.*exactly one loop.*found 2"):
        build_review_revise_definition(BuiltinReviewTemplate.SLICE)


def test_loop_body_without_a_review_step_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    definition = _p4()
    body = _loop(definition).config["steps"]
    assert isinstance(body, list)
    body[:] = [s for s in body if "review" not in s]
    _serve(monkeypatch, definition)

    with pytest.raises(ValueError, match=r"'P4'.*exactly one review step.*found 0"):
        build_review_revise_definition(BuiltinReviewTemplate.SLICE)


def test_loop_body_with_two_review_steps_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    definition = _p4()
    body = _loop(definition).config["steps"]
    assert isinstance(body, list)
    body.append(copy.deepcopy(next(s for s in body if "review" in s)))
    _serve(monkeypatch, definition)

    with pytest.raises(ValueError, match=r"'P4'.*exactly one review step.*found 2"):
        build_review_revise_definition(BuiltinReviewTemplate.SLICE)


def test_loop_without_until_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    definition = _p4()
    del _loop(definition).config["until"]
    _serve(monkeypatch, definition)

    with pytest.raises(ValueError, match=r"'P4'.*'until'"):
        build_review_revise_definition(BuiltinReviewTemplate.SLICE)


def test_loop_without_skip_if_met_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    definition = _p4()
    del _loop(definition).config["skip_if_met"]
    _serve(monkeypatch, definition)

    with pytest.raises(ValueError, match=r"'P4'.*skip_if_met"):
        build_review_revise_definition(BuiltinReviewTemplate.SLICE)


def test_loop_without_commit_each_iteration_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    definition = _p4()
    del _loop(definition).config["commit_each_iteration"]
    _serve(monkeypatch, definition)

    with pytest.raises(ValueError, match=r"'P4'.*commit_each_iteration"):
        build_review_revise_definition(BuiltinReviewTemplate.SLICE)
