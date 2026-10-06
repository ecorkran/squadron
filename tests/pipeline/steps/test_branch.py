"""Tests for BranchStepType (slice 196 D4)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.pipeline.models import ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.steps.branch import BranchOp, BranchStepType


def _config(config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type="branch", name="branch-0", config=config)


def test_step_type() -> None:
    assert BranchStepType().step_type == "branch"


@pytest.mark.parametrize("op", ["enter", "merge"])
def test_valid_ops_pass_validation(op: str) -> None:
    assert BranchStepType().validate(_config({"op": op})) == []


def test_slice_is_accepted() -> None:
    assert BranchStepType().validate(_config({"op": "enter", "slice": "{slice.index}"})) == []


def test_missing_op_is_an_error() -> None:
    errors = BranchStepType().validate(_config({}))
    assert [e.field for e in errors] == ["op"]
    assert "'op' is required" in errors[0].message


def test_bad_op_value_is_an_error() -> None:
    errors = BranchStepType().validate(_config({"op": "rebase"}))
    assert [e.field for e in errors] == ["op"]
    assert "'rebase' is not a valid branch op" in errors[0].message


def test_unknown_keys_are_rejected() -> None:
    errors = BranchStepType().validate(_config({"op": "enter", "force": True, "mode": "x"}))
    assert [e.field for e in errors] == ["force", "mode"]


@pytest.mark.parametrize(
    ("config", "expected_slice"),
    [({"op": "enter"}, "{slice}"), ({"op": "merge", "slice": "{slice.index}"}, "{slice.index}")],
)
def test_expands_to_one_branch_action(config: dict[str, object], expected_slice: str) -> None:
    actions = BranchStepType().expand(_config(config))
    assert actions == [("branch", {"op": BranchOp(str(config["op"])), "slice": expected_slice})]


# ---------------------------------------------------------------------------
# plan: (slice 197 D6)
# ---------------------------------------------------------------------------


def test_plan_is_accepted_on_enter() -> None:
    assert BranchStepType().validate(_config({"op": "enter", "plan": "{plan}"})) == []


def test_plan_is_rejected_on_merge() -> None:
    errors = BranchStepType().validate(_config({"op": "merge", "plan": "180"}))
    assert [e.field for e in errors] == ["plan"]
    assert "applies to enter only" in errors[0].message


def test_plan_expands_to_set_arch_before_the_branch_action() -> None:
    actions = BranchStepType().expand(_config({"op": "enter", "plan": "180", "slice": "7"}))
    assert actions == [
        ("cf-op", {"operation": "set_arch", "plan": "180"}),
        ("branch", {"op": BranchOp.ENTER, "slice": "7"}),
    ]


def test_without_plan_there_is_no_cf_op() -> None:
    actions = BranchStepType().expand(_config({"op": "enter"}))
    assert [name for name, _ in actions] == ["branch"]


@pytest.mark.asyncio
async def test_a_failed_set_arch_fails_the_item_before_the_branch_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from squadron.pipeline.batch_report import ItemOutcome
    from squadron.pipeline.executor import execute_pipeline
    from squadron.pipeline.sources import SOURCE_REGISTRY

    async def source(*_: object) -> list[dict[str, object]]:
        return [{"index": "7", "name": "Seven"}]

    monkeypatch.setitem(SOURCE_REGISTRY, ("test", "slices"), source)
    cf_op = MagicMock()
    cf_op.execute = AsyncMock(
        return_value=ActionResult(success=False, action_type="cf-op", outputs={}, error="no arch 999")
    )
    branch = MagicMock()
    branch.execute = AsyncMock()
    definition = PipelineDefinition(
        name="p",
        description="test",
        params={},
        steps=[
            StepConfig(
                step_type="each",
                name="slices",
                config={
                    "source": "test.slices()",
                    "as": "slice",
                    "on_item_failure": "continue",
                    "steps": [{"branch": {"op": "enter", "plan": "999", "slice": "{slice.index}"}}],
                },
            )
        ],
    )

    result = await execute_pipeline(
        definition,
        {"_project": "test"},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        cwd=str(tmp_path),
        runs_dir=tmp_path / "runs",
        _action_registry={"cf-op": cf_op, "branch": branch},
    )

    report = result.step_results[0].batch_report
    assert report is not None
    assert report.records[0].outcome is ItemOutcome.FLAGGED
    assert "no arch 999" in (report.records[0].reason or "")
    branch.execute.assert_not_called()
