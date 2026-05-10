"""Tests for inner_steps() on container step types (T3, T4, T5)."""

from __future__ import annotations

from squadron.pipeline.models import StepConfig
from squadron.pipeline.steps.collection import EachStepType
from squadron.pipeline.steps.fan_out import FanOutStepType
from squadron.pipeline.steps.loop import LoopStepType


def _each_step(steps: object) -> StepConfig:
    cfg: dict[str, object] = {"source": "items.list()", "as": "item"}
    if steps is not _MISSING:
        cfg["steps"] = steps
    return StepConfig(step_type="each", name="each-0", config=cfg)


def _loop_step(steps: object) -> StepConfig:
    cfg: dict[str, object] = {"max": 3}
    if steps is not _MISSING:
        cfg["steps"] = steps
    return StepConfig(step_type="loop", name="loop-0", config=cfg)


def _fan_out_step(models: object) -> StepConfig:
    return StepConfig(step_type="fan_out", name="fan-0", config={"models": models})


_MISSING = object()


class TestEachInnerSteps:
    def setup_method(self) -> None:
        self.step_type = EachStepType()

    def test_each_inner_steps_returns_step_configs(self) -> None:
        step = StepConfig(
            step_type="each",
            name="each-0",
            config={
                "source": "items.list()",
                "as": "item",
                "steps": [{"dispatch": {"model": "sonnet"}}],
            },
        )
        result = self.step_type.inner_steps(step)
        assert len(result) == 1
        assert result[0].step_type == "dispatch"

    def test_each_inner_steps_empty_if_no_steps_key(self) -> None:
        step = StepConfig(
            step_type="each",
            name="each-0",
            config={"source": "items.list()", "as": "item"},
        )
        assert self.step_type.inner_steps(step) == []

    def test_each_inner_steps_empty_if_steps_not_list(self) -> None:
        step = StepConfig(
            step_type="each",
            name="each-0",
            config={"source": "items.list()", "as": "item", "steps": "bad"},
        )
        assert self.step_type.inner_steps(step) == []


class TestLoopInnerSteps:
    def setup_method(self) -> None:
        self.step_type = LoopStepType()

    def test_loop_inner_steps_returns_step_configs(self) -> None:
        step = StepConfig(
            step_type="loop",
            name="loop-0",
            config={"max": 3, "steps": [{"dispatch": {"model": "sonnet"}}]},
        )
        result = self.step_type.inner_steps(step)
        assert len(result) == 1
        assert result[0].step_type == "dispatch"

    def test_loop_inner_steps_empty_if_no_steps_key(self) -> None:
        step = StepConfig(step_type="loop", name="loop-0", config={"max": 3})
        assert self.step_type.inner_steps(step) == []


class TestFanOutInnerSteps:
    def setup_method(self) -> None:
        self.step_type = FanOutStepType()

    def test_fan_out_inner_steps_returns_sentinel(self) -> None:
        step = StepConfig(
            step_type="fan_out",
            name="fan-0",
            config={"models": ["a", "b"]},
        )
        result = self.step_type.inner_steps(step)
        assert len(result) == 1
        assert result[0].step_type == "_fan_out_aggregate"
        assert result[0].config["models"] == ["a", "b"]

    def test_fan_out_inner_steps_pool_ref_preserved(self) -> None:
        step = StepConfig(
            step_type="fan_out",
            name="fan-0",
            config={"models": "pool:review"},
        )
        result = self.step_type.inner_steps(step)
        assert len(result) == 1
        assert result[0].config["models"] == "pool:review"
