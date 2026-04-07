"""Tests for CheckpointAction."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from squadron.pipeline.actions.checkpoint import CheckpointAction, CheckpointTrigger
from squadron.pipeline.actions.protocol import Action
from squadron.pipeline.models import ActionContext, ActionResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(
    prior_outputs: dict[str, ActionResult] | None = None,
    params: dict[str, object] | None = None,
) -> ActionContext:
    """Build an ActionContext with configurable prior outputs and params."""
    return ActionContext(
        pipeline_name="test-pipeline",
        run_id="run-12345678",
        params=params or {},
        step_name="quality-gate",
        step_index=1,
        prior_outputs=prior_outputs or {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        cwd="/tmp/test",
    )


def _review_result(verdict: str) -> ActionResult:
    """Build a minimal ActionResult with a verdict."""
    return ActionResult(
        success=True,
        action_type="review",
        outputs={"response": "review text"},
        verdict=verdict,
    )


# ---------------------------------------------------------------------------
# Basic properties and protocol
# ---------------------------------------------------------------------------


class TestCheckpointActionBasics:
    def test_action_type(self) -> None:
        action = CheckpointAction()
        assert action.action_type == "checkpoint"

    def test_protocol_compliance(self) -> None:
        assert isinstance(CheckpointAction(), Action)


class TestCheckpointTriggerEnum:
    def test_all_values(self) -> None:
        assert CheckpointTrigger.ALWAYS == "always"
        assert CheckpointTrigger.ON_CONCERNS == "on-concerns"
        assert CheckpointTrigger.ON_FAIL == "on-fail"
        assert CheckpointTrigger.NEVER == "never"

    def test_has_four_members(self) -> None:
        assert len(CheckpointTrigger) == 4


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestCheckpointValidation:
    def test_empty_config(self) -> None:
        errors = CheckpointAction().validate({})
        assert errors == []

    def test_valid_trigger(self) -> None:
        errors = CheckpointAction().validate({"trigger": "on-concerns"})
        assert errors == []

    def test_invalid_trigger(self) -> None:
        errors = CheckpointAction().validate({"trigger": "bogus"})
        assert len(errors) == 1
        assert errors[0].field == "trigger"
        assert "bogus" in errors[0].message


# ---------------------------------------------------------------------------
# Execute — trigger × verdict matrix
# ---------------------------------------------------------------------------


class TestCheckpointExecute:
    @pytest.mark.asyncio
    async def test_never_skips(self) -> None:
        ctx = _make_context(
            prior_outputs={"review": _review_result("FAIL")},
            params={"trigger": "never"},
        )
        result = await CheckpointAction().execute(ctx)
        assert result.outputs["checkpoint"] == "skipped"

    @pytest.mark.asyncio
    async def test_always_fires(self) -> None:
        ctx = _make_context(
            prior_outputs={"review": _review_result("PASS")},
            params={"trigger": "always"},
        )
        result = await CheckpointAction().execute(ctx)
        assert result.outputs["checkpoint"] == "paused"

    @pytest.mark.asyncio
    async def test_always_fires_no_prior_verdict(self) -> None:
        ctx = _make_context(params={"trigger": "always"})
        result = await CheckpointAction().execute(ctx)
        assert result.outputs["checkpoint"] == "paused"

    @pytest.mark.asyncio
    async def test_on_concerns_pass_skips(self) -> None:
        ctx = _make_context(
            prior_outputs={"review": _review_result("PASS")},
            params={"trigger": "on-concerns"},
        )
        result = await CheckpointAction().execute(ctx)
        assert result.outputs["checkpoint"] == "skipped"

    @pytest.mark.asyncio
    async def test_on_concerns_concerns_fires(self) -> None:
        ctx = _make_context(
            prior_outputs={"review": _review_result("CONCERNS")},
            params={"trigger": "on-concerns"},
        )
        result = await CheckpointAction().execute(ctx)
        assert result.outputs["checkpoint"] == "paused"

    @pytest.mark.asyncio
    async def test_on_concerns_fail_fires(self) -> None:
        ctx = _make_context(
            prior_outputs={"review": _review_result("FAIL")},
            params={"trigger": "on-concerns"},
        )
        result = await CheckpointAction().execute(ctx)
        assert result.outputs["checkpoint"] == "paused"

    @pytest.mark.asyncio
    async def test_on_fail_pass_skips(self) -> None:
        ctx = _make_context(
            prior_outputs={"review": _review_result("PASS")},
            params={"trigger": "on-fail"},
        )
        result = await CheckpointAction().execute(ctx)
        assert result.outputs["checkpoint"] == "skipped"

    @pytest.mark.asyncio
    async def test_on_fail_concerns_skips(self) -> None:
        ctx = _make_context(
            prior_outputs={"review": _review_result("CONCERNS")},
            params={"trigger": "on-fail"},
        )
        result = await CheckpointAction().execute(ctx)
        assert result.outputs["checkpoint"] == "skipped"

    @pytest.mark.asyncio
    async def test_on_fail_fail_fires(self) -> None:
        ctx = _make_context(
            prior_outputs={"review": _review_result("FAIL")},
            params={"trigger": "on-fail"},
        )
        result = await CheckpointAction().execute(ctx)
        assert result.outputs["checkpoint"] == "paused"

    @pytest.mark.asyncio
    async def test_no_prior_verdict_on_concerns_skips(self) -> None:
        ctx = _make_context(params={"trigger": "on-concerns"})
        result = await CheckpointAction().execute(ctx)
        assert result.outputs["checkpoint"] == "skipped"

    @pytest.mark.asyncio
    async def test_default_trigger_is_on_concerns(self) -> None:
        ctx = _make_context(
            prior_outputs={"review": _review_result("CONCERNS")},
        )
        result = await CheckpointAction().execute(ctx)
        assert result.outputs["checkpoint"] == "paused"

    @pytest.mark.asyncio
    async def test_fired_result_has_human_options(self) -> None:
        ctx = _make_context(
            prior_outputs={"review": _review_result("FAIL")},
            params={"trigger": "always"},
        )
        result = await CheckpointAction().execute(ctx)
        assert result.outputs["human_options"] == [
            "approve",
            "revise",
            "skip",
            "abort",
        ]
        assert "Review verdict:" in str(result.outputs["reason"])
        assert result.verdict == "FAIL"

    @pytest.mark.asyncio
    async def test_fired_result_metadata(self) -> None:
        ctx = _make_context(
            prior_outputs={"review": _review_result("FAIL")},
            params={"trigger": "always"},
        )
        result = await CheckpointAction().execute(ctx)
        assert result.metadata["step"] == "quality-gate"
        assert result.metadata["pipeline"] == "test-pipeline"

    @pytest.mark.asyncio
    async def test_success_is_always_true(self) -> None:
        """Both fired and skipped results are success=True."""
        ctx_fire = _make_context(params={"trigger": "always"})
        ctx_skip = _make_context(params={"trigger": "never"})
        assert (await CheckpointAction().execute(ctx_fire)).success is True
        assert (await CheckpointAction().execute(ctx_skip)).success is True

    @pytest.mark.asyncio
    async def test_invalid_trigger_returns_failure(self) -> None:
        """Invalid trigger value returns ActionResult(success=False)."""
        ctx = _make_context(params={"trigger": "concerns"})
        result = await CheckpointAction().execute(ctx)
        assert result.success is False
        assert "concerns" in result.outputs["error"]
        assert "on-concerns" in result.outputs["error"]
