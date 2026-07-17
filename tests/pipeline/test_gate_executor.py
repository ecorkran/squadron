"""Tests for the gate's executor integration: the step_outputs read surface,
end-to-end checkpoint-driving behavior, and the escalation-to-140 boundary.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from squadron.pipeline.actions.gate import reduce_verdicts
from squadron.pipeline.models import ActionContext, ActionResult, PipelineDefinition, StepConfig

# ---------------------------------------------------------------------------
# T3/T4 — Executor step-keyed read surface (ActionContext.step_outputs)
# ---------------------------------------------------------------------------


def _make_step_config(step_type: str, name: str, config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type=step_type, name=name, config=config)


def _make_pipeline(steps: list[StepConfig]) -> PipelineDefinition:
    return PipelineDefinition(name="test-pipeline", description="test", params={}, steps=steps)


class TestStepOutputsReadSurface:
    """Prove step_outputs recovers both source results by step name, bypassing
    the review-0 collision in the lossy action-keyed prior_outputs."""

    @pytest.mark.asyncio
    async def test_later_step_sees_both_named_review_results(self) -> None:
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        captured_contexts: list[ActionContext] = []

        async def review_execute(ctx: ActionContext) -> ActionResult:
            verdict = "PASS" if ctx.step_name == "judge-slice" else "CONCERNS"
            return ActionResult(success=True, action_type="review", outputs={}, verdict=verdict)

        async def gate_execute(ctx: ActionContext) -> ActionResult:
            captured_contexts.append(ctx)
            return ActionResult(success=True, action_type="gate", outputs={})

        review_action = MagicMock()
        review_action.execute = review_execute
        gate_action = MagicMock()
        gate_action.execute = gate_execute

        review_step = MagicMock()
        review_step.expand.return_value = [("review", {})]
        gate_step = MagicMock()
        gate_step.expand.return_value = [("gate", {})]

        register_step_type("_test_step_outputs_review", review_step)
        register_step_type("_test_step_outputs_gate", gate_step)

        pipeline = _make_pipeline(
            [
                _make_step_config("_test_step_outputs_review", "judge-slice", {}),
                _make_step_config("_test_step_outputs_review", "review-slice", {}),
                _make_step_config("_test_step_outputs_gate", "compose-gate", {}),
            ]
        )
        action_registry: dict[str, object] = {"review": review_action, "gate": gate_action}

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry=action_registry,
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert len(captured_contexts) == 1
        ctx = captured_contexts[0]

        # Both source results are recoverable by step name, despite both
        # having written the same "review-0" key in prior_outputs.
        assert ctx.step_outputs["judge-slice"].verdict == "PASS"
        assert ctx.step_outputs["review-slice"].verdict == "CONCERNS"


class TestStepOutputsRegression:
    """The read surface is purely additive: prior_outputs and
    _find_review_verdict behavior are unchanged."""

    @pytest.mark.asyncio
    async def test_prior_outputs_collision_unchanged(self) -> None:
        """Two review steps still collide under 'review-0' in prior_outputs —
        step_outputs does not alter this existing (lossy) behavior."""
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        captured_contexts: list[ActionContext] = []

        async def review_execute(ctx: ActionContext) -> ActionResult:
            verdict = "PASS" if ctx.step_name == "judge-slice" else "CONCERNS"
            return ActionResult(success=True, action_type="review", outputs={}, verdict=verdict)

        async def checkpoint_execute(ctx: ActionContext) -> ActionResult:
            captured_contexts.append(ctx)
            return ActionResult(success=True, action_type="checkpoint", outputs={})

        review_action = MagicMock()
        review_action.execute = review_execute
        checkpoint_action = MagicMock()
        checkpoint_action.execute = checkpoint_execute

        review_step = MagicMock()
        review_step.expand.return_value = [("review", {})]
        checkpoint_step = MagicMock()
        checkpoint_step.expand.return_value = [("checkpoint", {})]

        register_step_type("_test_regression_review", review_step)
        register_step_type("_test_regression_checkpoint", checkpoint_step)

        pipeline = _make_pipeline(
            [
                _make_step_config("_test_regression_review", "judge-slice", {}),
                _make_step_config("_test_regression_review", "review-slice", {}),
                _make_step_config("_test_regression_checkpoint", "gate-check", {}),
            ]
        )
        action_registry: dict[str, object] = {
            "review": review_action,
            "checkpoint": checkpoint_action,
        }

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry=action_registry,
        )

        assert result.status == ExecutionStatus.COMPLETED
        ctx = captured_contexts[0]

        # Only one "review-0" key survives — the second review step's result
        # overwrote the first's, exactly as before this slice.
        assert list(ctx.prior_outputs.keys()).count("review-0") == 1
        assert ctx.prior_outputs["review-0"].verdict == "CONCERNS"


# ---------------------------------------------------------------------------
# T10 — drives-checkpoint end behavior: the REDUCED verdict, not either raw
# leg, determines whether the same-step checkpoint fires.
# ---------------------------------------------------------------------------


def _pipeline_with_gate_and_checkpoint(checkpoint_trigger: str = "on-concerns") -> PipelineDefinition:
    """Two named review steps + a gate step expanding to [gate, checkpoint].

    Uses the real, registered ReviewStepType/GateStepType (via
    bootstrap_step_types) — only the "review" action is mocked so the test
    drives real expand()/gate/checkpoint logic end-to-end.
    """
    return PipelineDefinition(
        name="test-pipeline",
        description="test",
        params={},
        steps=[
            StepConfig(step_type="review", name="judge-slice", config={"template": "code"}),
            StepConfig(step_type="review", name="review-slice", config={"template": "code"}),
            StepConfig(
                step_type="gate",
                name="compose-gate",
                config={
                    "judge_from": "judge-slice",
                    "review_from": "review-slice",
                    "checkpoint": checkpoint_trigger,
                },
            ),
        ],
    )


async def _run_drives_checkpoint(
    judge_verdict: str | None,
    review_verdict: str | None,
) -> ActionResult:
    """Run the compose-gate pipeline end-to-end and return the checkpoint's result."""
    from squadron.pipeline.actions.checkpoint import CheckpointAction
    from squadron.pipeline.actions.gate import GateAction
    from squadron.pipeline.executor import execute_pipeline
    from squadron.pipeline.steps import bootstrap_step_types

    bootstrap_step_types()  # registers the real ReviewStepType/GateStepType

    async def review_execute(ctx: ActionContext) -> ActionResult:
        verdict = judge_verdict if ctx.step_name == "judge-slice" else review_verdict
        return ActionResult(success=True, action_type="review", outputs={}, verdict=verdict)

    review_action = MagicMock()
    review_action.execute = review_execute

    action_registry: dict[str, object] = {
        "review": review_action,
        "gate": GateAction(),
        "checkpoint": CheckpointAction(),
    }

    result = await execute_pipeline(
        _pipeline_with_gate_and_checkpoint(),
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        _action_registry=action_registry,
    )

    gate_step_result = result.step_results[-1]
    return gate_step_result.action_results[-1]


class TestDrivesCheckpoint:
    @pytest.mark.asyncio
    async def test_pass_and_concerns_fires_on_concerns(self) -> None:
        checkpoint_result = await _run_drives_checkpoint("PASS", "CONCERNS")
        assert checkpoint_result.outputs["checkpoint"] == "paused"

    @pytest.mark.asyncio
    async def test_both_pass_does_not_fire(self) -> None:
        checkpoint_result = await _run_drives_checkpoint("PASS", "PASS")
        assert checkpoint_result.outputs["checkpoint"] == "skipped"

    @pytest.mark.asyncio
    async def test_judge_unknown_review_pass_fires(self) -> None:
        """No-silent-pass under a broken judge leg."""
        checkpoint_result = await _run_drives_checkpoint("UNKNOWN", "PASS")
        assert checkpoint_result.outputs["checkpoint"] == "paused"

    @pytest.mark.asyncio
    async def test_none_leg_normalizes_and_fires_with_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """F003: a None-verdict leg fires the same-step checkpoint end-to-end
        (normalize -> reduce -> checkpoint fires), not just at the action level."""
        with caplog.at_level(logging.WARNING):
            checkpoint_result = await _run_drives_checkpoint(None, "PASS")
        assert checkpoint_result.outputs["checkpoint"] == "paused"
        assert any(r.levelno >= logging.WARNING for r in caplog.records)


# ---------------------------------------------------------------------------
# T11 — Escalation-to-140 boundary: a policy needing the checkpoint to branch
# on WHICH leg produced the severity is not expressible via the single
# reduced gate. This is escalation-boundary condition (3) — a 140 concern
# (Future Work 3), not silently absorbed here.
# ---------------------------------------------------------------------------


class TestBoundaryRequires140:
    def test_boundary_requires_140(self) -> None:
        """A policy that must distinguish WHICH leg (judge vs. review) caused
        a non-passing verdict cannot be expressed through the gate's single
        reduced verdict — the checkpoint's read path (_find_review_verdict)
        only ever sees ``ActionResult.verdict``, never ``ActionResult.metadata``.

        Concretely: suppose a required policy is "pause on judge FAIL, but
        auto-advance on review-only FAIL" (i.e. the checkpoint must react
        differently depending on which raw leg produced the severity). The
        gate's reduced verdict for (judge=FAIL, review=PASS) and
        (judge=PASS, review=FAIL) is identical ("FAIL" in both cases) —
        the two raw verdicts are preserved on metadata for auditability,
        but the checkpoint's trigger evaluation never reads metadata, only
        ``ActionResult.verdict``. A single-verdict checkpoint cannot express
        "fire only when the judge leg specifically is FAIL."

        This is escalation-boundary condition (3) (slice design, 300-slice
        gate-composition): the reduction cannot be a pure function of the two
        verdicts alone once the checkpoint itself needs to branch on which leg
        produced the severity. That requires extending the checkpoint to see
        multiple verdicts distinctly — option (b), a 140 concern (Future Work
        3) — and is explicitly NOT implemented in this slice.
        """
        judge_fail = ActionResult(
            success=True,
            action_type="gate",
            outputs={},
            verdict=reduce_verdicts("FAIL", "PASS"),
            metadata={"judge_verdict": "FAIL", "review_verdict": "PASS"},
        )
        review_fail = ActionResult(
            success=True,
            action_type="gate",
            outputs={},
            verdict=reduce_verdicts("PASS", "FAIL"),
            metadata={"judge_verdict": "PASS", "review_verdict": "FAIL"},
        )

        # The reduced verdict is identical in both cases — a checkpoint
        # reading only .verdict (as _find_review_verdict does) cannot tell
        # these two scenarios apart, even though metadata distinguishes them.
        assert judge_fail.verdict == review_fail.verdict == "FAIL"
        assert judge_fail.metadata != review_fail.metadata

        # The distinguishing information exists only on metadata, which the
        # checkpoint's read path never consults — proving a "branch on which
        # leg failed" policy is not expressible via the single reduced gate
        # and requires the 140 checkpoint extension (option b) instead.
        from squadron.pipeline.actions.checkpoint import _find_review_verdict

        verdict_only = _find_review_verdict({"gate-0": judge_fail})
        assert verdict_only == "FAIL"
        # No information about *which* leg failed survives this read path.
