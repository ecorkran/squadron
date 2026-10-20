"""``sq runs wait --json`` outcome document (#244, Amoeba S10)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

import squadron.pipeline.steps.loop  # noqa: F401 — trigger LoopStepType registration
from squadron.cli.app import app
from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.failure_kind import FAILURE_KIND_KEY, FailureKind
from squadron.pipeline.models import ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.run_outcome import run_outcome
from squadron.pipeline.run_wait import WaitOutcome
from squadron.pipeline.state import StateManager
from squadron.pipeline.steps import register_step_type

runner = CliRunner()


def _register(name: str, action_type: str) -> None:
    step_type = MagicMock()
    step_type.expand.return_value = [(action_type, {})]
    register_step_type(name, step_type)


def _review(verdict: str) -> ActionResult:
    return ActionResult(
        success=True,
        action_type="review",
        outputs={"review_file": "project-documents/user/reviews/105-review.code.stub.md"},
        verdict=verdict,
    )


def _action(results: list[ActionResult]) -> MagicMock:
    action = MagicMock()
    action.execute = AsyncMock(side_effect=results)
    return action


def _loop_definition() -> PipelineDefinition:
    _register("_ro_review", "review")
    loop = StepConfig(
        step_type="loop",
        name="revise-code",
        config={
            "max": "{max-revisions}",
            "until": "review.pass",
            "on_exhaust": "checkpoint",
            "steps": [{"_ro_review": {}}],
        },
    )
    return PipelineDefinition(
        name="outcome", description="t", params={"max-revisions": "2"}, steps=[loop]
    )


def _single(name: str, action_type: str) -> PipelineDefinition:
    _register(f"_ro_{name}", action_type)
    step = StepConfig(step_type=f"_ro_{name}", name=name, config={})
    return PipelineDefinition(name="outcome", description="t", params={}, steps=[step])


async def _run(
    tmp_path: Path, definition: PipelineDefinition, registry: dict[str, object]
) -> tuple[StateManager, str]:
    sm = StateManager(runs_dir=tmp_path / "runs")
    run_id = sm.init_run("outcome", {})
    result = await execute_pipeline(
        definition,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        run_id=run_id,
        observer=sm.observer(run_id),
        _action_registry=registry,
    )
    sm.finalize(run_id, result)
    return sm, run_id


@pytest.mark.asyncio
async def test_exhausted_loop_reports_kind_round_limit_and_review_file(tmp_path: Path) -> None:
    definition = _loop_definition()
    sm, run_id = await _run(tmp_path, definition, {"review": _action([_review("FAIL")] * 2)})

    doc = run_outcome(run_id, WaitOutcome.PAUSED, sm.load(run_id), lambda _: definition)

    assert doc["outcome"] == "paused" and doc["status"] == "paused"
    assert doc["failure"] is None
    checkpoint = doc["checkpoint"]
    assert isinstance(checkpoint, dict)
    assert checkpoint["kind"] == "loop_exhausted"
    assert (checkpoint["step"], checkpoint["is_loop"]) == ("revise-code", True)
    assert (checkpoint["round"], checkpoint["max_rounds"]) == (2, 2)
    assert checkpoint["verdict"] == "FAIL"
    assert checkpoint["review_file"] == "project-documents/user/reviews/105-review.code.stub.md"
    assert checkpoint["paused_at"] is not None


@pytest.mark.asyncio
async def test_an_unloadable_pipeline_leaves_max_rounds_unknown(tmp_path: Path) -> None:
    definition = _loop_definition()
    sm, run_id = await _run(tmp_path, definition, {"review": _action([_review("FAIL")] * 2)})

    def missing(_: str) -> PipelineDefinition:
        raise FileNotFoundError("gone")

    checkpoint = run_outcome(run_id, WaitOutcome.PAUSED, sm.load(run_id), missing)["checkpoint"]

    assert isinstance(checkpoint, dict) and checkpoint["max_rounds"] is None


@pytest.mark.asyncio
async def test_a_hand_off_pause_is_awaits_human(tmp_path: Path) -> None:
    blocked = ActionResult(
        success=False, action_type="work", outputs={}, error="BLOCKED: needs a key", awaits_human=True
    )
    sm, run_id = await _run(tmp_path, _single("implement", "work"), {"work": _action([blocked])})

    checkpoint = run_outcome(run_id, WaitOutcome.PAUSED, sm.load(run_id))["checkpoint"]

    assert isinstance(checkpoint, dict)
    assert (checkpoint["kind"], checkpoint["is_loop"], checkpoint["round"]) == (
        "awaits_human",
        False,
        None,
    )


@pytest.mark.asyncio
async def test_a_failed_run_reports_kind_step_and_message(tmp_path: Path) -> None:
    capped = ActionResult(
        success=False,
        action_type="work",
        outputs={},
        error="cost cap crossed",
        metadata={FAILURE_KIND_KEY: FailureKind.COST_CAP.value},
    )
    sm, run_id = await _run(tmp_path, _single("implement", "work"), {"work": _action([capped])})

    doc = run_outcome(run_id, WaitOutcome.FAILED, sm.load(run_id))

    assert doc["status"] == ExecutionStatus.FAILED.value and doc["checkpoint"] is None
    assert doc["failure"] == {"kind": "cost_cap", "step": "implement", "message": "cost cap crossed"}


def test_an_unreadable_run_carries_only_its_id_and_outcome() -> None:
    assert run_outcome("run-x", WaitOutcome.NOT_FOUND, None) == {
        "run_id": "run-x",
        "outcome": "not_found",
    }


def test_cli_json_with_zero_timeout_on_a_running_run(tmp_path: Path) -> None:
    sm = StateManager(runs_dir=tmp_path / "runs")
    run_id = sm.init_run("outcome", {})

    with patch("squadron.cli.commands.runs.StateManager", return_value=sm):
        result = runner.invoke(app, ["runs", "wait", run_id, "--timeout", "0", "--json"])

    assert result.exit_code == 4
    doc = json.loads(result.stdout)
    assert (doc["run_id"], doc["outcome"], doc["status"]) == (run_id, "timed_out", "running")
    assert doc["checkpoint"] is None and doc["failure"] is None


@pytest.mark.asyncio
async def test_a_checkpoint_prompt_that_exits_is_interactive_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SQUADRON_NO_INTERACTIVE", "1")
    paused = ActionResult(
        success=True, action_type="checkpoint", outputs={"checkpoint": "paused"}, verdict="CONCERNS"
    )
    sm, run_id = await _run(
        tmp_path, _single("design", "checkpoint"), {"checkpoint": _action([paused])}
    )

    checkpoint = run_outcome(run_id, WaitOutcome.PAUSED, sm.load(run_id))["checkpoint"]

    assert isinstance(checkpoint, dict)
    assert (checkpoint["kind"], checkpoint["verdict"]) == ("interactive_checkpoint", "CONCERNS")
