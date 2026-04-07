"""Tests for pipeline executor hardening changes in sq run command.

Covers: run_id / execution_mode threading through _run_pipeline and
_run_pipeline_sdk, --resume dispatch by ExecutionMode, implicit resume
dispatch, _handle_prompt_only_init recording PROMPT_ONLY, pipeline name
normalisation at CLI boundary, and _display_run_status execution_mode field.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.cli.commands.run import _display_run_status, _handle_prompt_only_init
from squadron.pipeline.executor import ExecutionStatus, PipelineResult
from squadron.pipeline.models import PipelineDefinition, StepConfig
from squadron.pipeline.state import ExecutionMode, RunState, StateManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_definition(
    name: str = "test-pipeline",
    params: dict[str, object] | None = None,
    steps: list[StepConfig] | None = None,
) -> PipelineDefinition:
    return PipelineDefinition(
        name=name,
        description="Test pipeline",
        params=params or {},
        steps=steps or [StepConfig(step_type="phase", name="step1", config={})],
    )


def _make_run_state(
    run_id: str = "run-test",
    pipeline: str = "test-pipeline",
    execution_mode: ExecutionMode = ExecutionMode.SDK,
    status: str = "paused",
) -> RunState:
    now = datetime.now(UTC)
    return RunState(
        run_id=run_id,
        pipeline=pipeline,
        params={"slice": "1"},
        execution_mode=execution_mode,
        started_at=now,
        updated_at=now,
        status=status,
    )


# ---------------------------------------------------------------------------
# T4: _run_pipeline run_id parameter
# ---------------------------------------------------------------------------


class TestRunPipelineRunId:
    def test_without_run_id_calls_init_run(self, tmp_path: Path) -> None:
        """When run_id is None, _run_pipeline calls init_run to create a new state."""
        import asyncio

        from squadron.cli.commands.run import _run_pipeline

        definition = _make_definition()
        mock_result = PipelineResult(
            pipeline_name="test-pipeline",
            status=ExecutionStatus.COMPLETED,
            step_results=[],
        )

        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=definition),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch("squadron.cli.commands.run._check_cf"),
            patch(
                "squadron.cli.commands.run.execute_pipeline",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            mgr = StateManager(runs_dir=tmp_path)
            with patch("squadron.cli.commands.run.StateManager", return_value=mgr):
                asyncio.run(_run_pipeline("test-pipeline", {}, runs_dir=tmp_path))

        # A new state file should have been created
        state_files = list(tmp_path.glob("*.json"))
        assert len(state_files) == 1

    def test_with_run_id_skips_init_run(self, tmp_path: Path) -> None:
        """When run_id is provided, no new state file is created."""
        import asyncio

        from squadron.cli.commands.run import _run_pipeline

        definition = _make_definition()
        mock_result = PipelineResult(
            pipeline_name="test-pipeline",
            status=ExecutionStatus.COMPLETED,
            step_results=[],
        )

        # Pre-create a state file for the provided run_id
        mgr = StateManager(runs_dir=tmp_path)
        existing_id = mgr.init_run("test-pipeline", {"slice": "1"})

        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=definition),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch("squadron.cli.commands.run._check_cf"),
            patch(
                "squadron.cli.commands.run.execute_pipeline",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            with patch("squadron.cli.commands.run.StateManager", return_value=mgr):
                asyncio.run(
                    _run_pipeline(
                        "test-pipeline",
                        {"slice": "1"},
                        run_id=existing_id,
                        runs_dir=tmp_path,
                    )
                )

        # Only the pre-existing state file should exist
        state_files = list(tmp_path.glob("*.json"))
        assert len(state_files) == 1
        assert state_files[0].stem == existing_id


# ---------------------------------------------------------------------------
# _run_pipeline rejects invalid pipelines at validation
# ---------------------------------------------------------------------------


class TestRunPipelineValidation:
    def test_invalid_pipeline_raises_value_error(self) -> None:
        """_run_pipeline raises ValueError when validate_pipeline finds errors."""
        import asyncio

        from squadron.cli.commands.run import _run_pipeline
        from squadron.pipeline.models import ValidationError

        definition = _make_definition()
        errors = [
            ValidationError(
                field="checkpoint",
                message="'concerns' is not a valid checkpoint trigger",
                action_type="design",
            )
        ]

        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=definition),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=errors),
        ):
            with pytest.raises(ValueError, match="validation errors"):
                asyncio.run(_run_pipeline("test-pipeline", {}))


# ---------------------------------------------------------------------------
# T5: _run_pipeline_sdk run_id parameter
# ---------------------------------------------------------------------------


class TestRunPipelineSdkRunId:
    def test_sdk_with_explicit_run_id_reuses_state(self, tmp_path: Path) -> None:
        """_run_pipeline_sdk forwards run_id to _run_pipeline."""
        import asyncio

        from squadron.cli.commands.run import _run_pipeline_sdk

        mock_result = PipelineResult(
            pipeline_name="test-pipeline",
            status=ExecutionStatus.COMPLETED,
            step_results=[],
        )

        with (
            patch("squadron.cli.commands.run._resolve_execution_mode"),
            patch(
                "squadron.cli.commands.run.load_pipeline",
                return_value=_make_definition(),
            ),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch(
                "squadron.cli.commands.run._run_pipeline",
                new_callable=AsyncMock,
                return_value=mock_result,
            ) as mock_inner,
            patch("claude_agent_sdk.ClaudeAgentOptions"),
            patch("claude_agent_sdk.ClaudeSDKClient"),
            patch("squadron.cli.commands.run.SDKExecutionSession") as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_session_cls.return_value = mock_session

            asyncio.run(
                _run_pipeline_sdk("test-pipeline", {}, run_id="run-existing-123")
            )

        # run_id must be forwarded
        call_kwargs = mock_inner.call_args.kwargs
        assert call_kwargs.get("run_id") == "run-existing-123"

    def test_sdk_without_run_id_passes_none(self, tmp_path: Path) -> None:
        """When no run_id given, _run_pipeline_sdk passes run_id=None."""
        import asyncio

        from squadron.cli.commands.run import _run_pipeline_sdk

        mock_result = PipelineResult(
            pipeline_name="test-pipeline",
            status=ExecutionStatus.COMPLETED,
            step_results=[],
        )

        with (
            patch("squadron.cli.commands.run._resolve_execution_mode"),
            patch(
                "squadron.cli.commands.run.load_pipeline",
                return_value=_make_definition(),
            ),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch(
                "squadron.cli.commands.run._run_pipeline",
                new_callable=AsyncMock,
                return_value=mock_result,
            ) as mock_inner,
            patch("claude_agent_sdk.ClaudeAgentOptions"),
            patch("claude_agent_sdk.ClaudeSDKClient"),
            patch("squadron.cli.commands.run.SDKExecutionSession") as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_session_cls.return_value = mock_session

            asyncio.run(_run_pipeline_sdk("test-pipeline", {}))

        call_kwargs = mock_inner.call_args.kwargs
        assert call_kwargs.get("run_id") is None


class TestRunPipelineSdkValidation:
    def test_sdk_rejects_invalid_pipeline_before_connect(self) -> None:
        """_run_pipeline_sdk raises ValueError before SDK session connects."""
        import asyncio

        from squadron.cli.commands.run import _run_pipeline_sdk
        from squadron.pipeline.models import ValidationError

        errors = [
            ValidationError(
                field="checkpoint",
                message="'concerns' is not a valid checkpoint trigger",
                action_type="design",
            )
        ]

        with (
            patch("squadron.cli.commands.run._resolve_execution_mode"),
            patch(
                "squadron.cli.commands.run.load_pipeline",
                return_value=_make_definition(),
            ),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=errors),
            patch("squadron.cli.commands.run.SDKExecutionSession") as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_session_cls.return_value = mock_session

            with pytest.raises(ValueError, match="validation errors"):
                asyncio.run(_run_pipeline_sdk("test-pipeline", {}))

            # Session should never have connected
            mock_session.connect.assert_not_called()


# ---------------------------------------------------------------------------
# T6/T7: Resume dispatch by ExecutionMode
# ---------------------------------------------------------------------------


class TestResumeDispatch:
    """Verify --resume dispatches to the correct runner based on execution_mode."""

    def test_explicit_resume_sdk_calls_run_pipeline_sdk(self) -> None:
        """--resume with SDK state calls _run_pipeline_sdk."""
        import typer as _typer
        from typer.testing import CliRunner

        from squadron.cli.app import app

        sdk_state = _make_run_state(run_id="run-sdk", execution_mode=ExecutionMode.SDK)
        definition = _make_definition()
        mock_result = MagicMock()
        mock_result.status.value = "completed"
        mock_result.pipeline_name = "test-pipeline"
        mock_result.step_results = []

        with (
            patch("squadron.cli.commands.run.StateManager") as mock_mgr_cls,
            patch("squadron.cli.commands.run.load_pipeline", return_value=definition),
            patch("squadron.cli.commands.run.asyncio") as mock_asyncio,
            patch("squadron.cli.commands.run.typer") as mock_typer,
        ):
            mock_typer.Exit = _typer.Exit
            mock_typer.BadParameter = _typer.BadParameter
            mock_asyncio.run.return_value = mock_result
            mock_mgr = MagicMock()
            mock_mgr.load.return_value = sdk_state
            mock_mgr.first_unfinished_step.return_value = "step1"
            mock_mgr_cls.return_value = mock_mgr

            runner = CliRunner()
            runner.invoke(app, ["run", "--resume", "run-sdk"])

        assert mock_asyncio.run.call_count == 1
        coroutine_arg = mock_asyncio.run.call_args[0][0]
        assert coroutine_arg.__qualname__ == "_run_pipeline_sdk"

    def test_explicit_resume_prompt_only_calls_run_pipeline(self) -> None:
        """--resume with PROMPT_ONLY state calls _run_pipeline, not SDK."""
        import typer as _typer
        from typer.testing import CliRunner

        from squadron.cli.app import app

        po_state = _make_run_state(
            run_id="run-po", execution_mode=ExecutionMode.PROMPT_ONLY
        )
        definition = _make_definition()
        mock_result = MagicMock()
        mock_result.status.value = "completed"
        mock_result.pipeline_name = "test-pipeline"
        mock_result.step_results = []

        with (
            patch("squadron.cli.commands.run.StateManager") as mock_mgr_cls,
            patch("squadron.cli.commands.run.load_pipeline", return_value=definition),
            patch("squadron.cli.commands.run.asyncio") as mock_asyncio,
            patch("squadron.cli.commands.run.typer") as mock_typer,
        ):
            mock_typer.Exit = _typer.Exit
            mock_typer.BadParameter = _typer.BadParameter
            mock_asyncio.run.return_value = mock_result
            mock_mgr = MagicMock()
            mock_mgr.load.return_value = po_state
            mock_mgr.first_unfinished_step.return_value = "step1"
            mock_mgr_cls.return_value = mock_mgr

            runner = CliRunner()
            runner.invoke(app, ["run", "--resume", "run-po"])

        assert mock_asyncio.run.call_count == 1
        coroutine_arg = mock_asyncio.run.call_args[0][0]
        assert coroutine_arg.__qualname__ == "_run_pipeline"

    def test_implicit_resume_sdk_calls_run_pipeline_sdk(self) -> None:
        """Implicit resume with SDK state calls _run_pipeline_sdk."""
        import typer as _typer
        from typer.testing import CliRunner

        from squadron.cli.app import app

        sdk_state = _make_run_state(run_id="run-sdk", execution_mode=ExecutionMode.SDK)
        definition = _make_definition()
        mock_result = MagicMock()
        mock_result.status.value = "completed"
        mock_result.pipeline_name = "test-pipeline"
        mock_result.step_results = []

        with (
            patch("squadron.cli.commands.run.StateManager") as mock_mgr_cls,
            patch("squadron.cli.commands.run.load_pipeline", return_value=definition),
            patch("squadron.cli.commands.run.sys") as mock_sys,
            patch("squadron.cli.commands.run.typer") as mock_typer,
            patch("squadron.cli.commands.run.asyncio") as mock_asyncio,
        ):
            mock_sys.stdin.isatty.return_value = True
            mock_typer.confirm.return_value = True
            mock_typer.Exit = _typer.Exit
            mock_typer.BadParameter = _typer.BadParameter
            mock_asyncio.run.return_value = mock_result
            mock_mgr = MagicMock()
            mock_mgr.find_matching_run.return_value = sdk_state
            mock_mgr.first_unfinished_step.return_value = "step1"
            mock_mgr_cls.return_value = mock_mgr

            runner = CliRunner()
            runner.invoke(app, ["run", "test-pipeline"])

        # asyncio.run should be called with the sdk coroutine
        assert mock_asyncio.run.call_count == 1
        coroutine_arg = mock_asyncio.run.call_args[0][0]
        # The coroutine's function should be _run_pipeline_sdk
        assert coroutine_arg.__qualname__ == "_run_pipeline_sdk"

    def test_implicit_resume_prompt_only_calls_run_pipeline(self) -> None:
        """Implicit resume with PROMPT_ONLY state calls _run_pipeline (not SDK)."""
        import typer as _typer
        from typer.testing import CliRunner

        from squadron.cli.app import app

        po_state = _make_run_state(
            run_id="run-po", execution_mode=ExecutionMode.PROMPT_ONLY
        )
        definition = _make_definition()
        mock_result = MagicMock()
        mock_result.status.value = "completed"
        mock_result.pipeline_name = "test-pipeline"
        mock_result.step_results = []

        with (
            patch("squadron.cli.commands.run.StateManager") as mock_mgr_cls,
            patch("squadron.cli.commands.run.load_pipeline", return_value=definition),
            patch("squadron.cli.commands.run.sys") as mock_sys,
            patch("squadron.cli.commands.run.typer") as mock_typer,
            patch("squadron.cli.commands.run.asyncio") as mock_asyncio,
        ):
            mock_sys.stdin.isatty.return_value = True
            mock_typer.confirm.return_value = True
            mock_typer.Exit = _typer.Exit
            mock_typer.BadParameter = _typer.BadParameter
            mock_asyncio.run.return_value = mock_result
            mock_mgr = MagicMock()
            mock_mgr.find_matching_run.return_value = po_state
            mock_mgr.first_unfinished_step.return_value = "step1"
            mock_mgr_cls.return_value = mock_mgr

            runner = CliRunner()
            runner.invoke(app, ["run", "test-pipeline"])

        assert mock_asyncio.run.call_count == 1
        coroutine_arg = mock_asyncio.run.call_args[0][0]
        # The coroutine's function should be _run_pipeline (not SDK)
        assert coroutine_arg.__qualname__ == "_run_pipeline"


# ---------------------------------------------------------------------------
# T8: _handle_prompt_only_init records PROMPT_ONLY
# ---------------------------------------------------------------------------


class TestHandlePromptOnlyInit:
    def test_creates_state_with_prompt_only_mode(self, tmp_path: Path) -> None:
        """_handle_prompt_only_init stores execution_mode=PROMPT_ONLY."""
        definition = _make_definition(
            name="test-pipeline",
            steps=[StepConfig(step_type="phase", name="step1", config={})],
        )

        from squadron.pipeline.prompt_renderer import StepInstructions

        mock_instructions = MagicMock(spec=StepInstructions)
        mock_instructions.to_json.return_value = '{"step": "step1"}'

        state_mgr = StateManager(runs_dir=tmp_path)

        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=definition),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch(
                "squadron.cli.commands.run.render_step_instructions",
                return_value=mock_instructions,
            ),
            patch("squadron.cli.commands.run.StateManager", return_value=state_mgr),
        ):
            _handle_prompt_only_init("test-pipeline", None, None, None)

        # Find the created run
        runs = state_mgr.list_runs()
        assert len(runs) == 1
        assert runs[0].execution_mode == ExecutionMode.PROMPT_ONLY


# ---------------------------------------------------------------------------
# T11: Pipeline name normalisation at CLI boundary
# ---------------------------------------------------------------------------


class TestPipelineNameNormalisation:
    def test_mixed_case_pipeline_name_passed_to_load_pipeline(self) -> None:
        """The CLI normalises pipeline names to lowercase before load_pipeline."""
        import typer as _typer
        from typer.testing import CliRunner

        from squadron.cli.app import app

        definition = _make_definition()
        mock_result = MagicMock()
        mock_result.status.value = "completed"
        mock_result.pipeline_name = "test-pipeline"
        mock_result.step_results = []

        with (
            patch(
                "squadron.cli.commands.run.load_pipeline", return_value=definition
            ) as mock_load,
            patch("squadron.cli.commands.run.StateManager") as mock_mgr_cls,
            patch("squadron.cli.commands.run.sys") as mock_sys,
            patch("squadron.cli.commands.run.typer") as mock_typer,
            patch("squadron.cli.commands.run.asyncio") as mock_asyncio,
        ):
            mock_sys.stdin.isatty.return_value = True
            mock_typer.Exit = _typer.Exit
            mock_typer.BadParameter = _typer.BadParameter
            mock_asyncio.run.return_value = mock_result
            mock_mgr = MagicMock()
            mock_mgr.find_matching_run.return_value = None
            mock_mgr_cls.return_value = mock_mgr

            runner = CliRunner()
            runner.invoke(app, ["run", "Test-Pipeline"])

        # load_pipeline must receive the lowercase name
        mock_load.assert_called_once_with("test-pipeline")


# ---------------------------------------------------------------------------
# T12: _display_run_status shows execution_mode
# ---------------------------------------------------------------------------


class TestDisplayRunStatus:
    def test_sdk_execution_mode_shown(self, capsys: pytest.CaptureFixture[str]) -> None:
        """_display_run_status output includes 'sdk' for SDK mode."""
        state = _make_run_state(execution_mode=ExecutionMode.SDK, status="completed")
        _display_run_status(state)
        captured = capsys.readouterr()
        assert "sdk" in captured.out

    def test_prompt_only_execution_mode_shown(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """_display_run_status output includes 'prompt-only' for PROMPT_ONLY mode."""
        state = _make_run_state(
            execution_mode=ExecutionMode.PROMPT_ONLY, status="paused"
        )
        _display_run_status(state)
        captured = capsys.readouterr()
        assert "prompt-only" in captured.out
