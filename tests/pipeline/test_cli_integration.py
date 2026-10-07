"""Integration tests for sq run CLI wiring.

Exercises the full wiring path: _run_pipeline → load_pipeline → execute_pipeline
→ StateManager, using mock action registries at the action boundary.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.cli.commands.run import _run_pipeline
from squadron.pipeline.executor import ExecutionStatus, PipelineResult
from squadron.pipeline.models import ActionResult
from squadron.pipeline.state import RUNNING_STATUS, ExecutionMode, RunState, StateManager
from tests.pipeline.conftest import (
    FIXTURE_PIPELINES_DIR,
    artifact_writing_action,
    load_fixture_pipeline,
    phase_artifact_cf_client,
)

# ---------------------------------------------------------------------------
# Helpers (shared with test_state_integration.py)
# ---------------------------------------------------------------------------


def _mock_action(success: bool = True, verdict: str | None = None) -> MagicMock:
    result = ActionResult(
        success=success,
        action_type="mock",
        outputs={},
        verdict=verdict,
    )
    action = MagicMock()
    action.execute = AsyncMock(return_value=result)
    return action


def _success_registry(dispatch_action: MagicMock | None = None) -> dict[str, object]:
    """Registry where all actions return success."""
    action = _mock_action(success=True)
    return {
        "cf-op": action,
        "branch": action,
        "dispatch": dispatch_action or action,
        "review": _mock_action(success=True, verdict="PASS"),
        "checkpoint": _mock_action(success=True),
        "commit": action,
        "compact": action,
        "summary": action,
        "devlog": action,
    }


def _paused_checkpoint_registry(
    pause_on_step: int = 2,
    dispatch_action: MagicMock | None = None,
) -> dict[str, object]:
    """Registry where the checkpoint action pauses on the Nth call."""
    call_count = [0]
    normal_action = _mock_action(success=True)
    review_action = _mock_action(success=True, verdict="PASS")

    paused_result = ActionResult(
        success=True,
        action_type="checkpoint",
        outputs={"checkpoint": "paused"},
        verdict="CONCERNS",
    )
    normal_checkpoint = ActionResult(
        success=True,
        action_type="checkpoint",
        outputs={},
    )

    checkpoint_mock = MagicMock()

    async def checkpoint_execute(ctx: object) -> ActionResult:
        call_count[0] += 1
        if call_count[0] >= pause_on_step:
            return paused_result
        return normal_checkpoint

    checkpoint_mock.execute = checkpoint_execute

    return {
        "branch": normal_action,
        "cf-op": normal_action,
        "dispatch": dispatch_action or normal_action,
        "review": review_action,
        "checkpoint": checkpoint_mock,
        "commit": normal_action,
        "compact": normal_action,
        "devlog": normal_action,
    }


# ---------------------------------------------------------------------------
# T12: Full execution integration test
# ---------------------------------------------------------------------------


class TestCliIntegration:
    @pytest.fixture(autouse=True)
    def _project_slice_pipeline(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Install the fixture 'slice' pipeline as a project pipeline, resolved by name."""
        monkeypatch.chdir(tmp_path)
        project_pipelines = tmp_path / "project-documents" / "user" / "pipelines"
        project_pipelines.mkdir(parents=True)
        shutil.copy(FIXTURE_PIPELINES_DIR / "slice.yaml", project_pipelines)

    @pytest.mark.asyncio
    async def test_run_pipeline_completes_successfully(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_run_pipeline returns COMPLETED and persists state."""
        monkeypatch.chdir(tmp_path)
        cf_client = phase_artifact_cf_client(191, "191-slice.stub.md", "191-tasks.stub.md")
        dispatch_action = artifact_writing_action(tmp_path, 191)
        with (
            patch("squadron.cli.commands.run._check_cf"),
            patch("squadron.cli.commands.run.ContextForgeClient", return_value=cf_client),
        ):
            result = await _run_pipeline(
                "slice",
                {"slice": "191"},
                runs_dir=tmp_path,
                _action_registry=_success_registry(dispatch_action=dispatch_action),
            )

        assert result.status == ExecutionStatus.COMPLETED
        assert len(result.step_results) == 12

        # State file should be loadable
        mgr = StateManager(runs_dir=tmp_path)
        runs = mgr.list_runs()
        assert len(runs) == 1
        assert runs[0].status == "completed"
        assert len(runs[0].completed_steps) == 12

    @pytest.mark.asyncio
    async def test_state_file_loadable_after_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """State file is persisted and loadable via StateManager."""
        monkeypatch.chdir(tmp_path)
        cf_client = phase_artifact_cf_client(191, "191-slice.stub.md", "191-tasks.stub.md")
        dispatch_action = artifact_writing_action(tmp_path, 191)
        with (
            patch("squadron.cli.commands.run._check_cf"),
            patch("squadron.cli.commands.run.ContextForgeClient", return_value=cf_client),
        ):
            await _run_pipeline(
                "slice",
                {"slice": "191"},
                runs_dir=tmp_path,
                _action_registry=_success_registry(dispatch_action=dispatch_action),
            )

        mgr = StateManager(runs_dir=tmp_path)
        runs = mgr.list_runs()
        state = mgr.load(runs[0].run_id)
        assert state.pipeline == "slice"
        assert state.params["slice"] == "191"

    # -------------------------------------------------------------------
    # T13: Resume from paused
    # -------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_resume_from_paused_completes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """First run pauses; second run resumes and completes all steps."""
        monkeypatch.chdir(tmp_path)
        cf_client = phase_artifact_cf_client(191, "191-slice.stub.md", "191-tasks.stub.md")
        dispatch_action = artifact_writing_action(tmp_path, 191)
        with (
            patch("squadron.cli.commands.run._check_cf"),
            patch("squadron.cli.commands.run.ContextForgeClient", return_value=cf_client),
        ):
            result1 = await _run_pipeline(
                "slice",
                {"slice": "191"},
                runs_dir=tmp_path,
                _action_registry=_paused_checkpoint_registry(
                    pause_on_step=2, dispatch_action=dispatch_action
                ),
            )

        assert result1.status == ExecutionStatus.PAUSED

        mgr = StateManager(runs_dir=tmp_path)
        runs = mgr.list_runs()
        assert runs[0].status == "paused"
        run_id = runs[0].run_id

        # Resume: load definition, find next step, re-execute
        definition = load_fixture_pipeline("slice")
        next_step = mgr.first_unfinished_step(run_id, definition)
        assert next_step is not None

        from squadron.pipeline.executor import execute_pipeline

        with patch("squadron.cli.commands.run._check_cf"):
            result2 = await execute_pipeline(
                definition,
                {"slice": "191"},
                resolver=MagicMock(),
                cf_client=cf_client,
                cwd=str(tmp_path),
                run_id=run_id,
                runs_dir=tmp_path,
                start_from=next_step,
                observer=mgr.observer(run_id),
                _action_registry=_success_registry(dispatch_action=dispatch_action),
            )
        mgr.finalize(run_id, result2)

        final = mgr.load(run_id)
        assert final.status == "completed"
        # 12 top-level steps, but the paused step ("tasks") is recorded twice:
        # once as PAUSED, once as COMPLETED on resume (slice 915 Part A —
        # first_unfinished_step now returns to the paused step and it
        # re-executes, rather than being skipped as already-done).
        assert len(final.completed_steps) == 13

    # -------------------------------------------------------------------
    # T18: --from mid-process adoption
    # -------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_from_step_skips_earlier_steps(self, tmp_path: Path) -> None:
        """Starting from 'implement-6' skips design/tasks/summary/compact/summary."""
        with patch("squadron.cli.commands.run._check_cf"):
            result = await _run_pipeline(
                "slice",
                {"slice": "191"},
                runs_dir=tmp_path,
                from_step="implement-6",
                _action_registry=_success_registry(),
            )

        assert result.status == ExecutionStatus.COMPLETED
        completed_names = [sr.step_name for sr in result.step_results]
        assert "design-0" not in completed_names
        assert "tasks-1" not in completed_names
        assert "implement-6" in completed_names

    # -------------------------------------------------------------------
    # T19: Dry-run produces no state file
    # -------------------------------------------------------------------

    def test_dry_run_creates_no_state_file(self, tmp_path: Path) -> None:
        """--dry-run path does not write any state file."""
        from typer.testing import CliRunner

        from squadron.cli.app import app
        from squadron.pipeline.models import PipelineDefinition, StepConfig

        test_runner = CliRunner()
        defn = PipelineDefinition(
            name="test",
            description="Test",
            params={"slice": "required"},
            steps=[StepConfig(step_type="phase", name="s1", config={})],
        )
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=defn),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
        ):
            result = test_runner.invoke(app, ["run", "--dry-run", "test", "191"])
        assert result.exit_code == 0
        assert not list(tmp_path.glob("*.json"))


# ---------------------------------------------------------------------------
# Slice 174: SDK runs are owned and heartbeated while the executor runs
# ---------------------------------------------------------------------------


class TestRunOwnership:
    @pytest.fixture(autouse=True)
    def _project_slice_pipeline(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        project_pipelines = tmp_path / "project-documents" / "user" / "pipelines"
        project_pipelines.mkdir(parents=True)
        shutil.copy(FIXTURE_PIPELINES_DIR / "slice.yaml", project_pipelines)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("path", ["new", "resume", "item-resume"])
    @pytest.mark.parametrize("outcome", [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED])
    async def test_running_with_owner_during_execution(
        self, tmp_path: Path, path: str, outcome: ExecutionStatus
    ) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        run_id: str | None = None
        if path != "new":
            run_id = mgr.init_run("slice", {"slice": "191"})
            mgr.finalize(
                run_id,
                PipelineResult(pipeline_name="slice", status=ExecutionStatus.PAUSED, step_results=[]),
            )
        seen: list[RunState] = []

        async def fake_execute(*_: object, run_id: str, **__: object) -> PipelineResult:
            seen.append(mgr.load(run_id))
            return PipelineResult(pipeline_name="slice", status=outcome, step_results=[])

        with (
            patch("squadron.cli.commands.run._check_cf"),
            patch("squadron.cli.commands.run.ContextForgeClient"),
            patch("squadron.cli.commands.run.execute_pipeline", side_effect=fake_execute),
        ):
            await _run_pipeline(
                "slice",
                {"slice": "191"},
                runs_dir=tmp_path,
                run_id=run_id,
                item_rerun=MagicMock() if path == "item-resume" else None,
            )

        assert len(seen) == 1
        during = seen[0]
        assert during.status == RUNNING_STATUS
        assert during.owner is not None and during.owner.pid == os.getpid()
        after = mgr.load(during.run_id)
        assert after.status == outcome.value
        assert after.owner == during.owner

    @pytest.mark.asyncio
    async def test_new_run_owner_is_in_the_creating_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        first_writes: list[dict[str, object]] = []
        real_write = StateManager._write_atomic  # pyright: ignore[reportPrivateUsage]

        def recording_write(self: StateManager, path: Path, data: str) -> None:
            if not path.exists():
                first_writes.append(json.loads(data))
            real_write(self, path, data)

        monkeypatch.setattr(StateManager, "_write_atomic", recording_write)

        async def fake_execute(*_: object, **__: object) -> PipelineResult:
            return PipelineResult(
                pipeline_name="slice", status=ExecutionStatus.COMPLETED, step_results=[]
            )

        with (
            patch("squadron.cli.commands.run._check_cf"),
            patch("squadron.cli.commands.run.ContextForgeClient"),
            patch("squadron.cli.commands.run.execute_pipeline", side_effect=fake_execute),
        ):
            await _run_pipeline("slice", {"slice": "191"}, runs_dir=tmp_path)

        assert len(first_writes) == 1
        assert first_writes[0]["status"] == RUNNING_STATUS
        assert first_writes[0]["owner"] is not None

    @pytest.mark.asyncio
    async def test_prompt_only_resume_stays_unowned(self, tmp_path: Path) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        run_id = mgr.init_run("slice", {"slice": "191"}, execution_mode=ExecutionMode.PROMPT_ONLY)
        seen: list[RunState] = []

        async def fake_execute(*_: object, run_id: str, **__: object) -> PipelineResult:
            seen.append(mgr.load(run_id))
            return PipelineResult(
                pipeline_name="slice", status=ExecutionStatus.COMPLETED, step_results=[]
            )

        with (
            patch("squadron.cli.commands.run._check_cf"),
            patch("squadron.cli.commands.run.ContextForgeClient"),
            patch("squadron.cli.commands.run.execute_pipeline", side_effect=fake_execute),
        ):
            await _run_pipeline(
                "slice",
                {"slice": "191"},
                runs_dir=tmp_path,
                run_id=run_id,
                execution_mode=ExecutionMode.PROMPT_ONLY,
            )

        assert seen[0].owner is None
