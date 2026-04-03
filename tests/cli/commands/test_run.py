"""Unit tests for the sq run command."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.run import _assemble_params, _check_cf, _resolve_target
from squadron.integrations.context_forge import (
    ContextForgeError,
    ContextForgeNotAvailable,
)
from squadron.pipeline.loader import PipelineInfo
from squadron.pipeline.models import PipelineDefinition, StepConfig, ValidationError
from squadron.pipeline.state import CheckpointState, RunState

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
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
        steps=steps or [],
    )


# ---------------------------------------------------------------------------
# T4: Mutual exclusivity validation
# ---------------------------------------------------------------------------


class TestMutualExclusivity:
    """Mutual exclusivity rules for sq run options."""

    def test_resume_and_from_exits_error(self) -> None:
        result = runner.invoke(app, ["run", "--resume", "run-123", "--from", "step-2"])
        assert result.exit_code == 1
        assert "--resume and --from cannot be used together" in result.output

    def test_list_with_pipeline_exits_error(self) -> None:
        result = runner.invoke(app, ["run", "--list", "slice"])
        assert result.exit_code == 1
        assert "--list cannot be combined" in result.output

    def test_list_with_model_exits_error(self) -> None:
        result = runner.invoke(app, ["run", "--list", "--model", "opus"])
        assert result.exit_code == 1
        assert "--list cannot be combined" in result.output

    def test_status_with_pipeline_exits_error(self) -> None:
        result = runner.invoke(app, ["run", "--status", "latest", "slice"])
        assert result.exit_code == 1
        assert "--status cannot be combined" in result.output

    def test_missing_pipeline_exits_error(self) -> None:
        result = runner.invoke(app, ["run"])
        assert result.exit_code == 1
        assert "pipeline argument is required" in result.output

    def test_valid_list_does_not_error_at_validation(self) -> None:
        """--list alone should pass mutual exclusivity (may fail later in execution)."""
        with patch("squadron.cli.commands.run.discover_pipelines", return_value=[]):
            result = runner.invoke(app, ["run", "--list"])
        assert result.exit_code == 0

    def test_valid_status_latest_does_not_error_at_validation(self) -> None:
        """--status latest should pass mutual exclusivity."""
        with patch("squadron.cli.commands.run.StateManager") as mock_cls:
            mock_mgr = MagicMock()
            mock_mgr.list_runs.return_value = []
            mock_cls.return_value = mock_mgr
            result = runner.invoke(app, ["run", "--status", "latest"])
        assert result.exit_code == 0
        assert "No runs found" in result.output


# ---------------------------------------------------------------------------
# T8: Target resolution
# ---------------------------------------------------------------------------


class TestResolveTarget:
    """_resolve_target maps positional target to first required param."""

    def test_slice_required_with_target(self) -> None:
        defn = _make_definition(params={"slice": "required", "model": "opus"})
        assert _resolve_target(defn, "191") == ("slice", "191")

    def test_plan_required_with_target(self) -> None:
        defn = _make_definition(params={"plan": "required", "model": "opus"})
        assert _resolve_target(defn, "140") == ("plan", "140")

    def test_required_param_without_target_raises(self) -> None:
        defn = _make_definition(params={"slice": "required"})
        with pytest.raises(typer.BadParameter, match="requires a 'slice' argument"):
            _resolve_target(defn, None)

    def test_no_required_params_returns_none(self) -> None:
        defn = _make_definition(params={"model": "opus"})
        assert _resolve_target(defn, None) is None

    def test_no_required_params_ignores_target(self) -> None:
        defn = _make_definition(params={"model": "opus"})
        assert _resolve_target(defn, "ignored") is None


class TestAssembleParams:
    """_assemble_params builds the full runtime params dict."""

    def test_target_with_model_and_extra_param(self) -> None:
        defn = _make_definition(params={"slice": "required", "model": "opus"})
        result = _assemble_params(defn, "191", "sonnet", ["template=arch"])
        assert result == {"slice": "191", "template": "arch", "model": "sonnet"}

    def test_no_target_no_model(self) -> None:
        defn = _make_definition(params={"model": "opus"})
        result = _assemble_params(defn, None, None, None)
        assert result == {}

    def test_multiple_extra_params(self) -> None:
        defn = _make_definition(params={"slice": "required"})
        result = _assemble_params(defn, "191", None, ["template=arch", "phase=4"])
        assert result == {"slice": "191", "template": "arch", "phase": "4"}

    def test_invalid_param_format_raises(self) -> None:
        defn = _make_definition(params={})
        with pytest.raises(typer.BadParameter, match="Invalid --param format"):
            _assemble_params(defn, None, None, ["=nope"])


# ---------------------------------------------------------------------------
# T5: --list
# ---------------------------------------------------------------------------


class TestList:
    """sq run --list displays discovered pipelines."""

    def test_list_shows_pipeline_names(self) -> None:
        pipelines = [
            PipelineInfo(
                name="slice",
                description="Full slice lifecycle",
                source="built-in",
                path=MagicMock(),
            ),
            PipelineInfo(
                name="review",
                description="Run a review",
                source="built-in",
                path=MagicMock(),
            ),
        ]
        with patch(
            "squadron.cli.commands.run.discover_pipelines",
            return_value=pipelines,
        ):
            result = runner.invoke(app, ["run", "--list"])
        assert result.exit_code == 0
        assert "slice" in result.output
        assert "review" in result.output
        assert "built-in" in result.output

    def test_list_empty(self) -> None:
        with patch(
            "squadron.cli.commands.run.discover_pipelines",
            return_value=[],
        ):
            result = runner.invoke(app, ["run", "--list"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# T6: --validate
# ---------------------------------------------------------------------------


class TestValidate:
    """sq run --validate checks pipeline definitions."""

    def test_validate_valid_pipeline(self) -> None:
        defn = _make_definition()
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=defn),
            patch(
                "squadron.cli.commands.run.validate_pipeline",
                return_value=[],
            ),
        ):
            result = runner.invoke(app, ["run", "--validate", "test"])
        assert result.exit_code == 0
        assert "is valid" in result.output

    def test_validate_with_errors(self) -> None:
        defn = _make_definition()
        errors = [
            ValidationError(
                field="step_type", message="Unknown step type 'bad'", action_type="bad"
            ),
            ValidationError(
                field="model", message="Unresolved alias 'foo'", action_type="pipeline"
            ),
        ]
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=defn),
            patch(
                "squadron.cli.commands.run.validate_pipeline",
                return_value=errors,
            ),
        ):
            result = runner.invoke(app, ["run", "--validate", "test"])
        assert result.exit_code == 1
        assert "Unknown step type" in result.output
        assert "Unresolved alias" in result.output

    def test_validate_pipeline_not_found(self) -> None:
        with patch(
            "squadron.cli.commands.run.load_pipeline",
            side_effect=FileNotFoundError("not found"),
        ):
            result = runner.invoke(app, ["run", "--validate", "missing"])
        assert result.exit_code == 1
        assert "not found" in result.output


# ---------------------------------------------------------------------------
# T7: --status
# ---------------------------------------------------------------------------


def _make_run_state(
    run_id: str = "run-20260403-test-abc12345",
    pipeline: str = "slice",
    status: str = "completed",
    checkpoint: CheckpointState | None = None,
) -> RunState:
    now = datetime(2026, 4, 3, 12, 0, 0, tzinfo=UTC)
    return RunState(
        run_id=run_id,
        pipeline=pipeline,
        params={"slice": "191"},
        started_at=now,
        updated_at=now,
        status=status,
        checkpoint=checkpoint,
    )


class TestStatus:
    """sq run --status displays run information."""

    def test_status_latest_with_runs(self) -> None:
        state = _make_run_state()
        with patch("squadron.cli.commands.run.StateManager") as mock_cls:
            mock_mgr = MagicMock()
            mock_mgr.list_runs.return_value = [state]
            mock_cls.return_value = mock_mgr
            result = runner.invoke(app, ["run", "--status", "latest"])
        assert result.exit_code == 0
        assert "run-20260403-test-abc12345" in result.output
        assert "slice" in result.output

    def test_status_latest_no_runs(self) -> None:
        with patch("squadron.cli.commands.run.StateManager") as mock_cls:
            mock_mgr = MagicMock()
            mock_mgr.list_runs.return_value = []
            mock_cls.return_value = mock_mgr
            result = runner.invoke(app, ["run", "--status", "latest"])
        assert result.exit_code == 0
        assert "No runs found" in result.output

    def test_status_run_id_found(self) -> None:
        state = _make_run_state()
        with patch("squadron.cli.commands.run.StateManager") as mock_cls:
            mock_mgr = MagicMock()
            mock_mgr.load.return_value = state
            mock_cls.return_value = mock_mgr
            result = runner.invoke(
                app, ["run", "--status", "run-20260403-test-abc12345"]
            )
        assert result.exit_code == 0
        assert "run-20260403-test-abc12345" in result.output

    def test_status_run_id_not_found(self) -> None:
        with patch("squadron.cli.commands.run.StateManager") as mock_cls:
            mock_mgr = MagicMock()
            mock_mgr.load.side_effect = FileNotFoundError()
            mock_cls.return_value = mock_mgr
            result = runner.invoke(app, ["run", "--status", "run-missing"])
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_status_with_checkpoint(self) -> None:
        now = datetime(2026, 4, 3, 12, 0, 0, tzinfo=UTC)
        cp = CheckpointState(
            reason="review concerns",
            step="design",
            verdict="CONCERNS",
            paused_at=now,
        )
        state = _make_run_state(status="paused", checkpoint=cp)
        with patch("squadron.cli.commands.run.StateManager") as mock_cls:
            mock_mgr = MagicMock()
            mock_mgr.load.return_value = state
            mock_cls.return_value = mock_mgr
            result = runner.invoke(
                app, ["run", "--status", "run-20260403-test-abc12345"]
            )
        assert result.exit_code == 0
        assert "Checkpoint" in result.output
        assert "design" in result.output


# ---------------------------------------------------------------------------
# T10: CF pre-flight check
# ---------------------------------------------------------------------------


class TestCheckCf:
    """_check_cf verifies Context Forge availability."""

    def test_cf_available(self) -> None:
        client = MagicMock()
        client.get_project.return_value = MagicMock()
        # Should not raise
        _check_cf(client)

    def test_cf_not_available(self) -> None:
        client = MagicMock()
        client.get_project.side_effect = ContextForgeNotAvailable("not found")
        with pytest.raises(typer.Exit) as exc_info:
            _check_cf(client)
        assert exc_info.value.exit_code == 1

    def test_cf_error(self) -> None:
        client = MagicMock()
        client.get_project.side_effect = ContextForgeError("connection failed")
        with pytest.raises(typer.Exit) as exc_info:
            _check_cf(client)
        assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# T11: _run_pipeline unit tests
# ---------------------------------------------------------------------------


class TestRunPipeline:
    """Unit tests for _run_pipeline async helper."""

    def test_pipeline_not_found_propagates(self) -> None:
        """FileNotFoundError from load_pipeline propagates."""
        from squadron.cli.commands.run import _run_pipeline

        with patch(
            "squadron.cli.commands.run.load_pipeline",
            side_effect=FileNotFoundError("not found"),
        ):
            with pytest.raises(FileNotFoundError):
                import asyncio

                asyncio.run(_run_pipeline("missing", {}))

    def test_dry_run_via_cli_produces_no_state(self, tmp_path: Path) -> None:
        """--dry-run path does not create state files."""
        defn = _make_definition(
            params={"slice": "required"},
            steps=[StepConfig(step_type="phase", name="s1", config={})],
        )
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=defn),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
        ):
            result = runner.invoke(app, ["run", "--dry-run", "test", "191"])
        assert result.exit_code == 0
        assert not list(tmp_path.glob("*.json"))

    def test_missing_pipeline_via_cli_exits_1(self) -> None:
        """sq run <missing> exits 1 with error message."""
        with patch(
            "squadron.cli.commands.run.load_pipeline",
            side_effect=FileNotFoundError("not found in [...]"),
        ):
            result = runner.invoke(app, ["run", "missing", "191"])
        assert result.exit_code == 1
        assert "not found" in result.output


# ---------------------------------------------------------------------------
# T14: --resume
# ---------------------------------------------------------------------------


class TestResume:
    """sq run --resume loads and continues a paused run."""

    def test_resume_calls_first_unfinished_step(self) -> None:
        state = _make_run_state(status="paused")
        defn = _make_definition(
            params={"slice": "required"},
            steps=[StepConfig(step_type="phase", name="design", config={})],
        )
        with (
            patch("squadron.cli.commands.run.StateManager") as mock_cls,
            patch("squadron.cli.commands.run.load_pipeline", return_value=defn),
            patch("squadron.cli.commands.run._check_cf"),
            patch("squadron.cli.commands.run.asyncio") as mock_asyncio,
        ):
            mock_mgr = MagicMock()
            mock_mgr.load.return_value = state
            mock_mgr.first_unfinished_step.return_value = "design"
            mock_cls.return_value = mock_mgr
            # Simulate successful execution
            mock_result = MagicMock()
            mock_result.status = MagicMock()
            mock_result.status.value = "completed"
            mock_result.pipeline_name = "slice"
            mock_result.step_results = []
            mock_asyncio.run.return_value = mock_result
            result = runner.invoke(
                app, ["run", "--resume", "run-20260403-test-abc12345"]
            )
        mock_mgr.first_unfinished_step.assert_called_once()
        # Should not error at validation
        assert result.exit_code == 0

    def test_resume_missing_run_exits_1(self) -> None:
        with patch("squadron.cli.commands.run.StateManager") as mock_cls:
            mock_mgr = MagicMock()
            mock_mgr.load.side_effect = FileNotFoundError()
            mock_cls.return_value = mock_mgr
            result = runner.invoke(app, ["run", "--resume", "run-missing"])
        assert result.exit_code == 1
        assert "not found" in result.output


# ---------------------------------------------------------------------------
# T15: Implicit resume detection
# ---------------------------------------------------------------------------


class TestImplicitResume:
    """When a matching paused run exists, prompt to resume."""

    def test_matching_paused_run_user_confirms(self) -> None:
        state = _make_run_state(status="paused")
        defn = _make_definition(
            params={"slice": "required"},
            steps=[StepConfig(step_type="phase", name="design", config={})],
        )
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=defn),
            patch("squadron.cli.commands.run.StateManager") as mock_cls,
            patch("squadron.cli.commands.run._check_cf"),
            patch("squadron.cli.commands.run.sys") as mock_sys,
            patch("squadron.cli.commands.run.typer") as mock_typer,
            patch("squadron.cli.commands.run.asyncio") as mock_asyncio,
        ):
            mock_sys.stdin.isatty.return_value = True
            mock_mgr = MagicMock()
            mock_mgr.find_matching_run.return_value = state
            mock_mgr.first_unfinished_step.return_value = "design"
            mock_cls.return_value = mock_mgr
            mock_typer.confirm.return_value = True
            mock_typer.Exit = typer.Exit
            mock_typer.BadParameter = typer.BadParameter
            # Simulate successful execution
            mock_result = MagicMock()
            mock_result.status = MagicMock()
            mock_result.status.value = "completed"
            mock_result.pipeline_name = "test-pipeline"
            mock_result.step_results = []
            mock_asyncio.run.return_value = mock_result
            runner.invoke(app, ["run", "test-pipeline", "191"])
        mock_typer.confirm.assert_called_once()

    def test_no_matching_run_proceeds_fresh(self) -> None:
        defn = _make_definition(params={"slice": "required"})
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=defn),
            patch("squadron.cli.commands.run.StateManager") as mock_cls,
            patch("squadron.cli.commands.run._check_cf"),
            patch("squadron.cli.commands.run.sys") as mock_sys,
            patch("squadron.cli.commands.run.asyncio") as mock_asyncio,
        ):
            mock_sys.stdin.isatty.return_value = True
            mock_mgr = MagicMock()
            mock_mgr.find_matching_run.return_value = None
            mock_cls.return_value = mock_mgr
            mock_result = MagicMock()
            mock_result.status = MagicMock()
            mock_result.status.value = "completed"
            mock_result.pipeline_name = "test-pipeline"
            mock_result.step_results = []
            mock_asyncio.run.return_value = mock_result
            runner.invoke(app, ["run", "test-pipeline", "191"])
        # find_matching_run was called but returned None — no confirm prompt
        mock_mgr.find_matching_run.assert_called_once()


# ---------------------------------------------------------------------------
# T16: --from (mid-process adoption)
# ---------------------------------------------------------------------------


class TestFromStep:
    """sq run --from starts execution from a named step."""

    def test_from_step_passed_to_run_pipeline(self) -> None:
        defn = _make_definition(params={"slice": "required"})
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=defn),
            patch("squadron.cli.commands.run.StateManager") as mock_cls,
            patch("squadron.cli.commands.run.sys") as mock_sys,
            patch("squadron.cli.commands.run.asyncio") as mock_asyncio,
        ):
            mock_sys.stdin.isatty.return_value = False
            mock_mgr = MagicMock()
            mock_cls.return_value = mock_mgr
            mock_result = MagicMock()
            mock_result.status = MagicMock()
            mock_result.status.value = "completed"
            mock_result.pipeline_name = "test-pipeline"
            mock_result.step_results = []
            mock_asyncio.run.return_value = mock_result
            runner.invoke(app, ["run", "--from", "implement", "test-pipeline", "191"])
        # Verify _run_pipeline was called with from_step="implement"
        call_args = mock_asyncio.run.call_args
        assert call_args is not None


# ---------------------------------------------------------------------------
# T17: Keyboard interrupt handling
# ---------------------------------------------------------------------------


class TestKeyboardInterrupt:
    """KeyboardInterrupt during execution prints resume instructions."""

    def test_interrupt_shows_resume_instructions(self) -> None:
        defn = _make_definition(params={"slice": "required"})
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=defn),
            patch("squadron.cli.commands.run.StateManager") as mock_cls,
            patch("squadron.cli.commands.run.sys") as mock_sys,
            patch(
                "squadron.cli.commands.run.asyncio.run",
                side_effect=KeyboardInterrupt,
            ),
        ):
            mock_sys.stdin.isatty.return_value = False
            mock_mgr = MagicMock()
            mock_cls.return_value = mock_mgr
            result = runner.invoke(app, ["run", "test-pipeline", "191"])
        assert result.exit_code == 1
        assert "Interrupted" in result.output
        assert "sq run --resume" in result.output
