"""Tests for GateAction: validation, execute, and policy handling."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from squadron.pipeline.actions.gate import DEFAULT_GATE_POLICY, GateAction
from squadron.pipeline.actions.judge import Provenance
from squadron.pipeline.actions.protocol import Action
from squadron.pipeline.models import ActionContext, ActionResult


def _make_gate_context(
    step_outputs: dict[str, ActionResult] | None = None,
    params: dict[str, object] | None = None,
) -> ActionContext:
    """Build an ActionContext with configurable step_outputs and params."""
    return ActionContext(
        pipeline_name="test-pipeline",
        run_id="run-12345678",
        params=params or {},
        step_name="compose-gate",
        step_index=2,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        cwd="/tmp/test",
        step_outputs=step_outputs or {},
    )


def _named_result(
    verdict: str | None,
    score: float | None = None,
    criteria: dict[str, float] | None = None,
) -> ActionResult:
    return ActionResult(
        success=True,
        action_type="review",
        outputs={},
        verdict=verdict,
        score=score,
        criteria=criteria,
    )


class TestGateActionBasics:
    def test_action_type(self) -> None:
        assert GateAction().action_type == "gate"

    def test_protocol_compliance(self) -> None:
        assert isinstance(GateAction(), Action)


class TestGateActionValidation:
    def test_valid_config(self) -> None:
        errors = GateAction().validate({"judge_from": "judge-slice", "review_from": "review-slice"})
        assert errors == []

    def test_missing_judge_from(self) -> None:
        errors = GateAction().validate({"review_from": "review-slice"})
        assert len(errors) == 1
        assert errors[0].field == "judge_from"

    def test_missing_review_from(self) -> None:
        errors = GateAction().validate({"judge_from": "judge-slice"})
        assert len(errors) == 1
        assert errors[0].field == "review_from"

    def test_missing_both(self) -> None:
        errors = GateAction().validate({})
        assert {e.field for e in errors} == {"judge_from", "review_from"}


class TestGateActionExecute:
    @pytest.mark.asyncio
    async def test_judge_pass_review_concerns_reduces_to_concerns(self) -> None:
        ctx = _make_gate_context(
            step_outputs={
                "judge-slice": _named_result("PASS", score=90.0),
                "review-slice": _named_result("CONCERNS"),
            },
            params={"judge_from": "judge-slice", "review_from": "review-slice"},
        )
        result = await GateAction().execute(ctx)
        assert result.verdict == "CONCERNS"
        assert result.provenance == Provenance.COMPOSED
        assert result.metadata["judge_verdict"] == "PASS"
        assert result.metadata["review_verdict"] == "CONCERNS"

    @pytest.mark.asyncio
    async def test_judge_unknown_review_pass_reduces_to_unknown(self) -> None:
        """No-silent-pass under a broken judge leg."""
        ctx = _make_gate_context(
            step_outputs={
                "judge-slice": _named_result("UNKNOWN"),
                "review-slice": _named_result("PASS"),
            },
            params={"judge_from": "judge-slice", "review_from": "review-slice"},
        )
        result = await GateAction().execute(ctx)
        assert result.verdict == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_none_leg_verdict_reduces_to_unknown_and_warns(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        ctx = _make_gate_context(
            step_outputs={
                "judge-slice": _named_result(None),
                "review-slice": _named_result("PASS"),
            },
            params={"judge_from": "judge-slice", "review_from": "review-slice"},
        )
        with caplog.at_level(logging.WARNING):
            result = await GateAction().execute(ctx)
        assert result.verdict == "UNKNOWN"
        assert any(r.levelno >= logging.WARNING for r in caplog.records)

    @pytest.mark.asyncio
    async def test_unresolvable_judge_from_yields_unknown_and_warns(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        ctx = _make_gate_context(
            step_outputs={"review-slice": _named_result("PASS")},
            params={"judge_from": "does-not-exist", "review_from": "review-slice"},
        )
        with caplog.at_level(logging.WARNING):
            result = await GateAction().execute(ctx)
        assert result.verdict == "UNKNOWN"
        assert any(r.levelno >= logging.WARNING for r in caplog.records)

    @pytest.mark.asyncio
    async def test_both_pass_reduces_to_pass(self) -> None:
        ctx = _make_gate_context(
            step_outputs={
                "judge-slice": _named_result("PASS"),
                "review-slice": _named_result("PASS"),
            },
            params={"judge_from": "judge-slice", "review_from": "review-slice"},
        )
        result = await GateAction().execute(ctx)
        assert result.verdict == "PASS"

    @pytest.mark.asyncio
    async def test_success_is_true(self) -> None:
        ctx = _make_gate_context(
            step_outputs={
                "judge-slice": _named_result("PASS"),
                "review-slice": _named_result("PASS"),
            },
            params={"judge_from": "judge-slice", "review_from": "review-slice"},
        )
        result = await GateAction().execute(ctx)
        assert result.success is True


class TestGateActionPolicy:
    """F001 fix: policy is actually read and recorded, not silently dropped."""

    @pytest.mark.asyncio
    async def test_default_policy_recorded_in_metadata(self) -> None:
        ctx = _make_gate_context(
            step_outputs={
                "judge-slice": _named_result("PASS"),
                "review-slice": _named_result("PASS"),
            },
            params={"judge_from": "judge-slice", "review_from": "review-slice"},
        )
        result = await GateAction().execute(ctx)
        assert result.metadata["policy"] == DEFAULT_GATE_POLICY

    @pytest.mark.asyncio
    async def test_explicit_valid_policy_recorded_in_metadata(self) -> None:
        ctx = _make_gate_context(
            step_outputs={
                "judge-slice": _named_result("PASS"),
                "review-slice": _named_result("PASS"),
            },
            params={
                "judge_from": "judge-slice",
                "review_from": "review-slice",
                "policy": "most-severe",
            },
        )
        result = await GateAction().execute(ctx)
        assert result.metadata["policy"] == "most-severe"

    @pytest.mark.asyncio
    async def test_unknown_policy_falls_back_and_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        ctx = _make_gate_context(
            step_outputs={
                "judge-slice": _named_result("PASS"),
                "review-slice": _named_result("PASS"),
            },
            params={
                "judge_from": "judge-slice",
                "review_from": "review-slice",
                "policy": "bogus",
            },
        )
        with caplog.at_level(logging.WARNING):
            result = await GateAction().execute(ctx)
        assert result.metadata["policy"] == DEFAULT_GATE_POLICY
        assert result.verdict == "PASS"
        assert any(r.levelno >= logging.WARNING for r in caplog.records)
