"""Unit tests for squadron.pipeline.state.

Tests cover: Pydantic models, StateManager init, atomic writes, init_run,
make_step_callback/_append_step, finalize, load, load_prior_outputs,
first_unfinished_step, list_runs, find_matching_run, prune.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadron.pipeline.executor import ExecutionStatus, PipelineResult, StepResult
from squadron.pipeline.models import ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.state import (
    CheckpointState,
    RunState,
    SchemaVersionError,
    StateManager,
    StepState,
)

# ---------------------------------------------------------------------------
# T3: Pydantic model tests
# ---------------------------------------------------------------------------


class TestPydanticModels:
    def test_run_state_round_trip(self) -> None:
        now = datetime.now(UTC)
        original = RunState(
            run_id="run-20260403-test-abc12345",
            pipeline="test-pipeline",
            params={"slice": "191"},
            started_at=now,
            updated_at=now,
            status="running",
        )
        dumped = original.model_dump(mode="json")
        restored = RunState.model_validate(dumped)
        assert restored.run_id == original.run_id
        assert restored.pipeline == original.pipeline
        assert restored.params == original.params
        assert restored.status == original.status

    def test_step_state_defaults(self) -> None:
        now = datetime.now(UTC)
        step = StepState(
            step_name="design",
            step_type="phase",
            status="completed",
            completed_at=now,
        )
        assert step.verdict is None
        assert step.outputs == {}
        assert step.action_results == []

    def test_checkpoint_state_round_trip(self) -> None:
        now = datetime.now(UTC)
        cp = CheckpointState(
            reason="on_concerns",
            step="implement",
            verdict="CONCERNS",
            paused_at=now,
        )
        restored = CheckpointState.model_validate(cp.model_dump(mode="json"))
        assert restored.reason == cp.reason
        assert restored.step == cp.step
        assert restored.verdict == cp.verdict

    def test_schema_version_error_is_exception(self) -> None:
        err = SchemaVersionError(99)
        assert isinstance(err, Exception)
        with pytest.raises(SchemaVersionError):
            raise err


# ---------------------------------------------------------------------------
# T4a: Atomic write tests
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    def test_creates_target_with_correct_content(self, tmp_path: Path) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        target = tmp_path / "state.json"
        mgr._write_atomic(target, '{"hello": "world"}')
        assert target.exists()
        assert json.loads(target.read_text()) == {"hello": "world"}

    def test_overwrites_stale_tmp_file(self, tmp_path: Path) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        target = tmp_path / "state.json"
        stale_tmp = tmp_path / "state.tmp"
        stale_tmp.write_text("stale garbage", encoding="utf-8")
        mgr._write_atomic(target, '{"fresh": true}')
        assert json.loads(target.read_text()) == {"fresh": True}
        assert not stale_tmp.exists()

    def test_second_write_replaces_first(self, tmp_path: Path) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        target = tmp_path / "state.json"
        mgr._write_atomic(target, '{"v": 1}')
        mgr._write_atomic(target, '{"v": 2}')
        assert json.loads(target.read_text()) == {"v": 2}

    def test_no_tmp_files_left_after_write(self, tmp_path: Path) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        target = tmp_path / "state.json"
        mgr._write_atomic(target, '{"clean": true}')
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == []


# ---------------------------------------------------------------------------
# T6: init_run tests
# ---------------------------------------------------------------------------


class TestInitRun:
    def test_creates_json_file(
        self, state_manager: StateManager, tmp_path: Path
    ) -> None:
        run_id = state_manager.init_run("my-pipeline", {"slice": "1"})
        assert (tmp_path / f"{run_id}.json").exists()

    def test_file_deserializes_to_valid_run_state(
        self, state_manager: StateManager
    ) -> None:
        run_id = state_manager.init_run("my-pipeline", {"slice": "1"})
        state = state_manager.load(run_id)
        assert state.status == "running"
        assert state.pipeline == "my-pipeline"
        assert state.params == {"slice": "1"}
        assert state.completed_steps == []

    def test_caller_supplied_run_id_used_verbatim(
        self, state_manager: StateManager
    ) -> None:
        custom_id = "run-custom-id"
        returned = state_manager.init_run("pipeline", {}, run_id=custom_id)
        assert returned == custom_id
        state = state_manager.load(custom_id)
        assert state.run_id == custom_id

    def test_generated_run_id_format(self, state_manager: StateManager) -> None:
        run_id = state_manager.init_run("slice-lifecycle", {"slice": "191"})
        assert run_id.startswith("run-")
        assert "slice-lifecycle" in run_id


# ---------------------------------------------------------------------------
# T8: make_step_callback / _append_step tests
# ---------------------------------------------------------------------------


def _make_step_result(
    step_name: str = "design",
    step_type: str = "phase",
    status: ExecutionStatus = ExecutionStatus.COMPLETED,
    verdicts: list[str | None] | None = None,
    error: str | None = None,
) -> StepResult:
    if verdicts is None:
        verdicts = [None, "PASS"]
    action_results = [
        ActionResult(
            success=True,
            action_type="cf-op",
            outputs={"file": f"{step_name}.md"},
            verdict=v,
        )
        for v in verdicts
    ]
    return StepResult(
        step_name=step_name,
        step_type=step_type,
        status=status,
        action_results=action_results,
        error=error,
    )


class TestStepCallback:
    def test_verdict_from_last_non_none(self, state_manager: StateManager) -> None:
        run_id = state_manager.init_run("pipe", {})
        cb = state_manager.make_step_callback(run_id)
        cb(_make_step_result(verdicts=[None, "PASS"]))
        state = state_manager.load(run_id)
        assert state.completed_steps[0].verdict == "PASS"

    def test_outputs_from_last_action(self, state_manager: StateManager) -> None:
        run_id = state_manager.init_run("pipe", {})
        cb = state_manager.make_step_callback(run_id)
        ar = ActionResult(
            success=True,
            action_type="cf-op",
            outputs={"key": "value"},
            verdict=None,
        )
        step = StepResult(
            step_name="design",
            step_type="phase",
            status=ExecutionStatus.COMPLETED,
            action_results=[ar],
        )
        cb(step)
        state = state_manager.load(run_id)
        assert state.completed_steps[0].outputs == {"key": "value"}

    def test_two_callbacks_produce_two_entries(
        self, state_manager: StateManager
    ) -> None:
        run_id = state_manager.init_run("pipe", {})
        cb = state_manager.make_step_callback(run_id)
        cb(_make_step_result(step_name="design"))
        cb(_make_step_result(step_name="tasks"))
        state = state_manager.load(run_id)
        assert len(state.completed_steps) == 2

    def test_paused_step_sets_status_and_checkpoint(
        self, state_manager: StateManager
    ) -> None:
        run_id = state_manager.init_run("pipe", {})
        cb = state_manager.make_step_callback(run_id)
        paused_step = _make_step_result(
            step_name="implement",
            status=ExecutionStatus.PAUSED,
            error="on_concerns",
        )
        cb(paused_step)
        state = state_manager.load(run_id)
        assert state.status == "paused"
        assert state.checkpoint is not None
        assert state.checkpoint.step == "implement"
        assert state.checkpoint.reason == "on_concerns"

    def test_action_results_stored_as_dicts(self, state_manager: StateManager) -> None:
        run_id = state_manager.init_run("pipe", {})
        cb = state_manager.make_step_callback(run_id)
        cb(_make_step_result())
        state = state_manager.load(run_id)
        ar_list = state.completed_steps[0].action_results
        assert isinstance(ar_list, list)
        assert all(isinstance(ar, dict) for ar in ar_list)


# ---------------------------------------------------------------------------
# T10: finalize tests
# ---------------------------------------------------------------------------


class TestFinalize:
    def test_completed_sets_status_and_clears_step(
        self, state_manager: StateManager, completed_pipeline_result: PipelineResult
    ) -> None:
        run_id = state_manager.init_run("pipe", {})
        state_manager.finalize(run_id, completed_pipeline_result)
        state = state_manager.load(run_id)
        assert state.status == "completed"
        assert state.current_step is None

    def test_failed_sets_status(self, state_manager: StateManager) -> None:
        run_id = state_manager.init_run("pipe", {})
        failed_result = PipelineResult(
            pipeline_name="pipe",
            status=ExecutionStatus.FAILED,
            step_results=[],
        )
        state_manager.finalize(run_id, failed_result)
        state = state_manager.load(run_id)
        assert state.status == "failed"


# ---------------------------------------------------------------------------
# T12: load + SchemaVersionError tests
# ---------------------------------------------------------------------------


class TestLoad:
    def test_load_after_init_run_has_correct_fields(
        self, state_manager: StateManager
    ) -> None:
        run_id = state_manager.init_run("my-pipe", {"k": "v"})
        state = state_manager.load(run_id)
        assert state.pipeline == "my-pipe"
        assert state.params == {"k": "v"}

    def test_load_nonexistent_raises_file_not_found(
        self, state_manager: StateManager
    ) -> None:
        with pytest.raises(FileNotFoundError):
            state_manager.load("run-does-not-exist")

    def test_load_schema_version_99_raises(
        self, state_manager: StateManager, tmp_path: Path
    ) -> None:
        bad = tmp_path / "run-bad.json"
        bad.write_text(
            json.dumps({"schema_version": 99, "run_id": "run-bad"}), encoding="utf-8"
        )
        with pytest.raises(SchemaVersionError):
            state_manager.load("run-bad")

    def test_load_schema_version_0_raises(
        self, state_manager: StateManager, tmp_path: Path
    ) -> None:
        bad = tmp_path / "run-zero.json"
        bad.write_text(
            json.dumps({"schema_version": 0, "run_id": "run-zero"}), encoding="utf-8"
        )
        with pytest.raises(SchemaVersionError):
            state_manager.load("run-zero")


# ---------------------------------------------------------------------------
# T14: load_prior_outputs tests
# ---------------------------------------------------------------------------


def _write_run_with_action_results(
    state_manager: StateManager,
    pipeline: str = "pipe",
    num_action_results: int = 2,
) -> str:
    """Helper: create a run with completed steps that have stored action_results."""
    run_id = state_manager.init_run(pipeline, {})
    cb = state_manager.make_step_callback(run_id)
    verdicts = ["PASS"] * num_action_results
    step = StepResult(
        step_name="design",
        step_type="phase",
        status=ExecutionStatus.COMPLETED,
        action_results=[
            ActionResult(
                success=True,
                action_type="cf-op",
                outputs={"file": f"f{i}.md"},
                verdict=v,
            )
            for i, v in enumerate(verdicts)
        ],
    )
    cb(step)
    return run_id


class TestLoadPriorOutputs:
    def test_returns_populated_dict(self, state_manager: StateManager) -> None:
        run_id = _write_run_with_action_results(state_manager, num_action_results=2)
        prior = state_manager.load_prior_outputs(run_id)
        assert len(prior) == 2
        assert all(isinstance(v, ActionResult) for v in prior.values())

    def test_returns_empty_for_run_with_no_action_results(
        self, state_manager: StateManager
    ) -> None:
        run_id = state_manager.init_run("pipe", {})
        # Manually write a completed step with no action_results
        state = state_manager.load(run_id)
        now = datetime.now(UTC)
        state.completed_steps.append(
            StepState(
                step_name="design",
                step_type="phase",
                status="completed",
                completed_at=now,
                action_results=[],
            )
        )
        state_manager._write_atomic(
            state_manager._state_path(run_id),
            json.dumps(state.model_dump(mode="json"), indent=2),
        )
        prior = state_manager.load_prior_outputs(run_id)
        assert prior == {}

    def test_unknown_fields_in_stored_dict_dont_crash(
        self, state_manager: StateManager
    ) -> None:
        run_id = state_manager.init_run("pipe", {})
        state = state_manager.load(run_id)
        now = datetime.now(UTC)
        # Include an unknown field "bogus_field"
        state.completed_steps.append(
            StepState(
                step_name="design",
                step_type="phase",
                status="completed",
                completed_at=now,
                action_results=[
                    {
                        "action_type": "cf-op",
                        "success": True,
                        "outputs": {},
                        "bogus_field": "should be ignored",
                    }
                ],
            )
        )
        state_manager._write_atomic(
            state_manager._state_path(run_id),
            json.dumps(state.model_dump(mode="json"), indent=2),
        )
        prior = state_manager.load_prior_outputs(run_id)
        assert "cf-op-0" in prior


# ---------------------------------------------------------------------------
# T16: first_unfinished_step tests
# ---------------------------------------------------------------------------


def _make_definition(step_names: list[str]) -> PipelineDefinition:
    return PipelineDefinition(
        name="test-pipe",
        description="",
        params={},
        steps=[
            StepConfig(step_type="phase", name=name, config={}) for name in step_names
        ],
    )


class TestFirstUnfinishedStep:
    def test_no_completed_steps_returns_first(
        self, state_manager: StateManager
    ) -> None:
        run_id = state_manager.init_run("pipe", {})
        defn = _make_definition(["design", "tasks", "implement"])
        result = state_manager.first_unfinished_step(run_id, defn)
        assert result == "design"

    def test_first_two_completed_returns_third(
        self, state_manager: StateManager
    ) -> None:
        run_id = state_manager.init_run("pipe", {})
        cb = state_manager.make_step_callback(run_id)
        cb(_make_step_result(step_name="design"))
        cb(_make_step_result(step_name="tasks"))
        defn = _make_definition(["design", "tasks", "implement"])
        result = state_manager.first_unfinished_step(run_id, defn)
        assert result == "implement"

    def test_all_completed_returns_none(self, state_manager: StateManager) -> None:
        run_id = state_manager.init_run("pipe", {})
        cb = state_manager.make_step_callback(run_id)
        for name in ["design", "tasks", "implement"]:
            cb(_make_step_result(step_name=name))
        defn = _make_definition(["design", "tasks", "implement"])
        result = state_manager.first_unfinished_step(run_id, defn)
        assert result is None


# ---------------------------------------------------------------------------
# T18: list_runs tests
# ---------------------------------------------------------------------------


class TestListRuns:
    def _create_run(
        self,
        mgr: StateManager,
        pipeline: str,
        status: str = "completed",
    ) -> str:
        run_id = mgr.init_run(pipeline, {})
        if status != "running":
            state = mgr.load(run_id)
            state.status = status
            mgr._write_atomic(
                mgr._state_path(run_id),
                json.dumps(state.model_dump(mode="json"), indent=2),
            )
        return run_id

    def test_returns_all_runs(self, state_manager: StateManager) -> None:
        self._create_run(state_manager, "pipeline-a")
        self._create_run(state_manager, "pipeline-a")
        self._create_run(state_manager, "pipeline-b")
        runs = state_manager.list_runs()
        assert len(runs) == 3

    def test_filter_by_pipeline(self, state_manager: StateManager) -> None:
        self._create_run(state_manager, "pipeline-a")
        self._create_run(state_manager, "pipeline-a")
        self._create_run(state_manager, "pipeline-b")
        runs = state_manager.list_runs(pipeline="pipeline-a")
        assert len(runs) == 2
        assert all(r.pipeline == "pipeline-a" for r in runs)

    def test_filter_by_status(self, state_manager: StateManager) -> None:
        self._create_run(state_manager, "pipeline-a", status="completed")
        self._create_run(state_manager, "pipeline-a", status="running")
        runs = state_manager.list_runs(status="running")
        assert len(runs) == 1
        assert runs[0].status == "running"

    def test_sort_most_recent_first(self, state_manager: StateManager) -> None:
        rid1 = self._create_run(state_manager, "pipe")
        time.sleep(0.01)
        rid2 = self._create_run(state_manager, "pipe")
        runs = state_manager.list_runs()
        assert runs[0].run_id == rid2
        assert runs[1].run_id == rid1

    def test_corrupt_json_file_skipped(
        self, state_manager: StateManager, tmp_path: Path
    ) -> None:
        (tmp_path / "corrupt.json").write_text("NOT JSON{{{{", encoding="utf-8")
        self._create_run(state_manager, "pipe")
        runs = state_manager.list_runs()
        assert len(runs) == 1


# ---------------------------------------------------------------------------
# T20: find_matching_run tests
# ---------------------------------------------------------------------------


class TestFindMatchingRun:
    def _create_paused_run(
        self,
        mgr: StateManager,
        pipeline: str,
        params: dict[str, object],
    ) -> str:
        run_id = mgr.init_run(pipeline, params)
        state = mgr.load(run_id)
        state.status = "paused"
        mgr._write_atomic(
            mgr._state_path(run_id),
            json.dumps(state.model_dump(mode="json"), indent=2),
        )
        return run_id

    def test_finds_paused_run_by_params(self, state_manager: StateManager) -> None:
        self._create_paused_run(state_manager, "slice-lifecycle", {"slice": "191"})
        match = state_manager.find_matching_run(
            "slice-lifecycle", {"slice": "191"}, status="paused"
        )
        assert match is not None
        assert match.params["slice"] == "191"

    def test_returns_none_when_params_differ(self, state_manager: StateManager) -> None:
        self._create_paused_run(state_manager, "slice-lifecycle", {"slice": "191"})
        match = state_manager.find_matching_run(
            "slice-lifecycle", {"slice": "192"}, status="paused"
        )
        assert match is None

    def test_returns_none_when_status_doesnt_match(
        self, state_manager: StateManager
    ) -> None:
        state_manager.init_run("slice-lifecycle", {"slice": "191"})
        match = state_manager.find_matching_run(
            "slice-lifecycle", {"slice": "191"}, status="paused"
        )
        assert match is None

    def test_returns_most_recent_when_multiple_matches(
        self, state_manager: StateManager
    ) -> None:
        self._create_paused_run(state_manager, "pipe", {"s": "1"})
        time.sleep(0.01)
        rid2 = self._create_paused_run(state_manager, "pipe", {"s": "1"})
        match = state_manager.find_matching_run("pipe", {"s": "1"}, status="paused")
        assert match is not None
        assert match.run_id == rid2


# ---------------------------------------------------------------------------
# T22: prune tests
# ---------------------------------------------------------------------------


class TestPrune:
    def _create_completed_run(self, mgr: StateManager, pipeline: str) -> str:
        run_id = mgr.init_run(pipeline, {})
        result = PipelineResult(
            pipeline_name=pipeline,
            status=ExecutionStatus.COMPLETED,
            step_results=[],
        )
        mgr.finalize(run_id, result)
        return run_id

    def _create_paused_run(self, mgr: StateManager, pipeline: str) -> str:
        run_id = mgr.init_run(pipeline, {})
        state = mgr.load(run_id)
        state.status = "paused"
        mgr._write_atomic(
            mgr._state_path(run_id),
            json.dumps(state.model_dump(mode="json"), indent=2),
        )
        return run_id

    def test_deletes_oldest_beyond_keep(
        self, state_manager: StateManager, tmp_path: Path
    ) -> None:
        # Create 12 completed runs without triggering auto-prune on init_run.
        # Use a custom pipeline name per run to avoid auto-prune interference.
        mgr = StateManager(runs_dir=tmp_path)
        for i in range(12):
            # Override prune so auto-prune in init_run is a no-op
            original_prune = mgr.prune
            mgr.prune = lambda *a, **kw: 0  # type: ignore[method-assign]
            run_id = mgr.init_run("pipeline-x", {})
            mgr.prune = original_prune  # type: ignore[method-assign]
            result = PipelineResult(
                pipeline_name="pipeline-x",
                status=ExecutionStatus.COMPLETED,
                step_results=[],
            )
            mgr.finalize(run_id, result)
        deleted = mgr.prune("pipeline-x", keep=10)
        assert deleted == 2
        remaining = list(tmp_path.glob("*.json"))
        assert len(remaining) == 10

    def test_oldest_are_deleted(self, state_manager: StateManager) -> None:
        run_ids = []
        for _ in range(5):
            run_ids.append(self._create_completed_run(state_manager, "pipe"))
            time.sleep(0.01)
        state_manager.prune("pipe", keep=3)
        # oldest 2 should be gone
        with pytest.raises(FileNotFoundError):
            state_manager.load(run_ids[0])
        with pytest.raises(FileNotFoundError):
            state_manager.load(run_ids[1])
        # newest 3 should remain
        for rid in run_ids[2:]:
            assert state_manager.load(rid) is not None

    def test_paused_run_never_pruned(self, state_manager: StateManager) -> None:
        paused_id = self._create_paused_run(state_manager, "pipe")
        for _ in range(12):
            self._create_completed_run(state_manager, "pipe")
        state_manager.prune("pipe", keep=10)
        # paused run must still exist
        assert state_manager.load(paused_id) is not None

    def test_returns_correct_count(self, state_manager: StateManager) -> None:
        for _ in range(5):
            self._create_completed_run(state_manager, "pipe")
        deleted = state_manager.prune("pipe", keep=3)
        assert deleted == 2

    def test_noop_when_within_keep(self, state_manager: StateManager) -> None:
        for _ in range(5):
            self._create_completed_run(state_manager, "pipe")
        deleted = state_manager.prune("pipe", keep=10)
        assert deleted == 0
