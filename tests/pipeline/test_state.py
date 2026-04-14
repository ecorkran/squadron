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
    CompactSummary,
    ExecutionMode,
    RunState,
    SchemaVersionError,
    StateManager,
    StepState,
)

# ---------------------------------------------------------------------------
# T1: ExecutionMode enum tests
# ---------------------------------------------------------------------------


class TestExecutionMode:
    def test_sdk_value(self) -> None:
        assert ExecutionMode.SDK.value == "sdk"

    def test_prompt_only_value(self) -> None:
        assert ExecutionMode.PROMPT_ONLY.value == "prompt-only"

    def test_round_trip_from_string_sdk(self) -> None:
        assert ExecutionMode("sdk") == ExecutionMode.SDK

    def test_round_trip_from_string_prompt_only(self) -> None:
        assert ExecutionMode("prompt-only") == ExecutionMode.PROMPT_ONLY


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
            execution_mode=ExecutionMode.SDK,
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

    def test_run_state_execution_mode_sdk_serialises(self) -> None:
        now = datetime.now(UTC)
        state = RunState(
            run_id="run-x",
            pipeline="pipe",
            params={},
            execution_mode=ExecutionMode.SDK,
            started_at=now,
            updated_at=now,
            status="running",
        )
        dumped = state.model_dump(mode="json")
        assert dumped["execution_mode"] == "sdk"

    def test_run_state_execution_mode_prompt_only_serialises(self) -> None:
        now = datetime.now(UTC)
        state = RunState(
            run_id="run-x",
            pipeline="pipe",
            params={},
            execution_mode=ExecutionMode.PROMPT_ONLY,
            started_at=now,
            updated_at=now,
            status="running",
        )
        dumped = state.model_dump(mode="json")
        assert dumped["execution_mode"] == "prompt-only"

    def test_run_state_missing_execution_mode_defaults_to_sdk(self) -> None:
        now = datetime.now(UTC)
        data: dict[str, object] = {
            "schema_version": 3,
            "run_id": "run-x",
            "pipeline": "pipe",
            "params": {},
            "started_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "status": "running",
        }
        state = RunState.model_validate(data)
        assert state.execution_mode == ExecutionMode.SDK

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
        run_id = state_manager.init_run("slice", {"slice": "191"})
        assert run_id.startswith("run-")
        assert "slice" in run_id

    def test_init_run_stores_execution_mode_prompt_only(
        self, state_manager: StateManager
    ) -> None:
        run_id = state_manager.init_run(
            "pipe", {}, execution_mode=ExecutionMode.PROMPT_ONLY
        )
        state = state_manager.load(run_id)
        assert state.execution_mode == ExecutionMode.PROMPT_ONLY

    def test_init_run_normalises_pipeline_name_to_lowercase(
        self, state_manager: StateManager
    ) -> None:
        run_id = state_manager.init_run("Test-Pipeline", {})
        state = state_manager.load(run_id)
        assert state.pipeline == "test-pipeline"


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

    def test_load_schema_version_1_raises_with_message(
        self, state_manager: StateManager, tmp_path: Path
    ) -> None:
        bad = tmp_path / "run-v1.json"
        bad.write_text(
            json.dumps({"schema_version": 1, "run_id": "run-v1"}), encoding="utf-8"
        )
        with pytest.raises(
            SchemaVersionError, match="Unsupported state file schema_version"
        ):
            state_manager.load("run-v1")

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
        self._create_paused_run(state_manager, "slice", {"slice": "191"})
        match = state_manager.find_matching_run(
            "slice", {"slice": "191"}, status="paused"
        )
        assert match is not None
        assert match.params["slice"] == "191"

    def test_returns_none_when_params_differ(self, state_manager: StateManager) -> None:
        self._create_paused_run(state_manager, "slice", {"slice": "191"})
        match = state_manager.find_matching_run(
            "slice", {"slice": "192"}, status="paused"
        )
        assert match is None

    def test_returns_none_when_status_doesnt_match(
        self, state_manager: StateManager
    ) -> None:
        state_manager.init_run("slice", {"slice": "191"})
        match = state_manager.find_matching_run(
            "slice", {"slice": "191"}, status="paused"
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


# ---------------------------------------------------------------------------
# record_step_done tests (T8)
# ---------------------------------------------------------------------------


class TestRecordStepDone:
    def test_basic_step_completion(self, tmp_path: Path) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        run_id = mgr.init_run("test-pipe", {"slice": "152"})
        mgr.record_step_done(run_id, "design-0", "design")

        state = mgr.load(run_id)
        assert len(state.completed_steps) == 1
        assert state.completed_steps[0].step_name == "design-0"
        assert state.completed_steps[0].step_type == "design"
        assert state.completed_steps[0].status == "completed"

    def test_with_verdict(self, tmp_path: Path) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        run_id = mgr.init_run("test-pipe", {})
        mgr.record_step_done(run_id, "design-0", "design", verdict="PASS")

        state = mgr.load(run_id)
        assert state.completed_steps[0].verdict == "PASS"

    def test_sequential_steps(self, tmp_path: Path) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        run_id = mgr.init_run("test-pipe", {})
        mgr.record_step_done(run_id, "design-0", "design")
        mgr.record_step_done(run_id, "tasks-1", "tasks")

        state = mgr.load(run_id)
        assert len(state.completed_steps) == 2
        assert state.completed_steps[0].step_name == "design-0"
        assert state.completed_steps[1].step_name == "tasks-1"

    def test_invalid_run_id(self, tmp_path: Path) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        with pytest.raises(FileNotFoundError):
            mgr.record_step_done("nonexistent-run", "s", "t")


# ---------------------------------------------------------------------------
# T2/T3: CompactSummary and schema v3
# ---------------------------------------------------------------------------


def _make_summary(
    key: str = "3:compact",
    text: str = "summary text",
    summary_model: str | None = "haiku-id",
    source_step_index: int = 3,
    source_step_name: str = "compact",
) -> CompactSummary:
    return CompactSummary(
        key=key,
        text=text,
        summary_model=summary_model,
        source_step_index=source_step_index,
        source_step_name=source_step_name,
        created_at=datetime.now(UTC),
    )


class TestCompactSummary:
    def test_round_trip(self) -> None:
        s = _make_summary()
        restored = CompactSummary.model_validate(s.model_dump(mode="json"))
        assert restored == s

    def test_run_state_empty_compact_summaries_default(self) -> None:
        now = datetime.now(UTC)
        state = RunState(
            run_id="r",
            pipeline="p",
            params={},
            started_at=now,
            updated_at=now,
            status="running",
        )
        assert state.compact_summaries == {}

    def test_run_state_with_compact_summaries_round_trip(self) -> None:
        now = datetime.now(UTC)
        s = _make_summary()
        state = RunState(
            run_id="r",
            pipeline="p",
            params={},
            started_at=now,
            updated_at=now,
            status="running",
            compact_summaries={s.key: s},
        )
        restored = RunState.model_validate(state.model_dump(mode="json"))
        assert restored.compact_summaries == {s.key: s}

    def test_load_v2_file_raises_schema_version_error(self, tmp_path: Path) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        bad = tmp_path / "run-v2.json"
        bad.write_text(
            json.dumps({"schema_version": 2, "run_id": "run-v2"}), encoding="utf-8"
        )
        with pytest.raises(SchemaVersionError):
            mgr.load("run-v2")

    def test_load_v3_file_without_compact_summaries_defaults_empty(
        self, tmp_path: Path
    ) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        now = datetime.now(UTC)
        path = tmp_path / "run-v3.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": 3,
                    "run_id": "run-v3",
                    "pipeline": "p",
                    "params": {},
                    "started_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    "status": "running",
                }
            ),
            encoding="utf-8",
        )
        state = mgr.load("run-v3")
        assert state.compact_summaries == {}


class TestRecordCompactSummary:
    def test_adds_summary(self, tmp_path: Path) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        run_id = mgr.init_run("pipe", {})
        s = _make_summary()
        mgr.record_compact_summary(run_id, s)
        reloaded = mgr.load(run_id)
        assert reloaded.compact_summaries == {s.key: s}

    def test_overwrites_same_key(self, tmp_path: Path) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        run_id = mgr.init_run("pipe", {})
        first = _make_summary(text="first")
        second = _make_summary(text="second")
        mgr.record_compact_summary(run_id, first)
        mgr.record_compact_summary(run_id, second)
        reloaded = mgr.load(run_id)
        assert reloaded.compact_summaries[first.key].text == "second"


class TestActiveCompactSummaryForResume:
    def _state_with(self, summaries: list[CompactSummary]) -> RunState:
        now = datetime.now(UTC)
        return RunState(
            run_id="r",
            pipeline="p",
            params={},
            started_at=now,
            updated_at=now,
            status="running",
            compact_summaries={s.key: s for s in summaries},
        )

    def test_empty_returns_none(self) -> None:
        state = self._state_with([])
        assert state.active_compact_summary_for_resume(5) is None

    def test_single_summary_below_resume_returns_it(self) -> None:
        s = _make_summary(source_step_index=3)
        state = self._state_with([s])
        assert state.active_compact_summary_for_resume(5) == s

    def test_strict_less_than(self) -> None:
        s = _make_summary(source_step_index=3)
        state = self._state_with([s])
        assert state.active_compact_summary_for_resume(3) is None

    def test_picks_highest_applicable(self) -> None:
        s2 = _make_summary(key="2:a", source_step_index=2, source_step_name="a")
        s5 = _make_summary(key="5:b", source_step_index=5, source_step_name="b")
        state = self._state_with([s2, s5])
        assert state.active_compact_summary_for_resume(7) == s5

    def test_skips_summaries_at_or_beyond_resume(self) -> None:
        s2 = _make_summary(key="2:a", source_step_index=2, source_step_name="a")
        s5 = _make_summary(key="5:b", source_step_index=5, source_step_name="b")
        state = self._state_with([s2, s5])
        assert state.active_compact_summary_for_resume(4) == s2


# ---------------------------------------------------------------------------
# T-pools: Pool selection logging and schema migration (slice 181)
# ---------------------------------------------------------------------------


def _make_pool_selection() -> object:
    """Return a PoolSelection with predictable field values."""
    from datetime import UTC, datetime

    from squadron.pipeline.intelligence.pools.models import PoolSelection

    return PoolSelection(
        pool_name="review",
        selected_alias="minimax",
        strategy="round-robin",
        step_name="design-0",
        action_type="dispatch",
        timestamp=datetime(2026, 4, 14, 12, 0, 0, tzinfo=UTC),
    )


class TestPoolSelectionLogging:
    """Tests for StateManager.log_pool_selection and RunState.pool_selections."""

    def test_log_pool_selection_appends_entry(self, tmp_path: Path) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        run_id = mgr.init_run("test-pipe", {})
        sel = _make_pool_selection()
        mgr.log_pool_selection(run_id, sel)

        state = mgr.load(run_id)
        assert len(state.pool_selections) == 1
        entry = state.pool_selections[0]
        assert entry["pool_name"] == "review"
        assert entry["selected_alias"] == "minimax"
        assert entry["strategy"] == "round-robin"
        assert entry["step_name"] == "design-0"
        assert entry["action_type"] == "dispatch"
        assert entry["timestamp"] == "2026-04-14T12:00:00+00:00"

    def test_log_pool_selection_appends_multiple(self, tmp_path: Path) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        run_id = mgr.init_run("test-pipe", {})
        sel = _make_pool_selection()
        mgr.log_pool_selection(run_id, sel)
        mgr.log_pool_selection(run_id, sel)

        state = mgr.load(run_id)
        assert len(state.pool_selections) == 2

    def test_schema_v3_file_loads_with_empty_pool_selections(
        self, tmp_path: Path
    ) -> None:
        """A schema_version=3 state file must load with pool_selections=[]."""
        state_data = {
            "schema_version": 3,
            "run_id": "run-20260101-old-abc12345",
            "pipeline": "old-pipe",
            "params": {},
            "execution_mode": "sdk",
            "started_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "status": "completed",
            "current_step": None,
            "completed_steps": [],
            "checkpoint": None,
            "compact_summaries": {},
        }
        path = tmp_path / "run-20260101-old-abc12345.json"
        path.write_text(json.dumps(state_data), encoding="utf-8")

        mgr = StateManager(runs_dir=tmp_path)
        state = mgr.load("run-20260101-old-abc12345")
        assert state.pool_selections == []

    def test_schema_v4_round_trips(self, tmp_path: Path) -> None:
        """State file written at v4 loads correctly."""
        mgr = StateManager(runs_dir=tmp_path)
        run_id = mgr.init_run("test-pipe", {})
        mgr.log_pool_selection(run_id, _make_pool_selection())

        state = mgr.load(run_id)
        assert state.schema_version == 4
        assert len(state.pool_selections) == 1

    def test_unsupported_schema_raises(self, tmp_path: Path) -> None:
        """Schema version 2 and 5 must raise SchemaVersionError."""
        mgr = StateManager(runs_dir=tmp_path)
        for bad_version in (2, 5):
            state_data = {
                "schema_version": bad_version,
                "run_id": f"run-bad-{bad_version}",
                "pipeline": "p",
                "params": {},
                "execution_mode": "sdk",
                "started_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "status": "completed",
            }
            path = tmp_path / f"run-bad-{bad_version}.json"
            path.write_text(json.dumps(state_data), encoding="utf-8")
            with pytest.raises(SchemaVersionError):
                mgr.load(f"run-bad-{bad_version}")
