"""Unit tests for the sq run command."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.run import (
    _DRY_RUN_COMMIT_EACH_ITERATION_SUFFIX,
    _DRY_RUN_NO_UNTIL_DISPLAY,
    _assemble_params,
    _check_cf,
    _resolve_target,
)
from squadron.integrations.context_forge import (
    ContextForgeError,
    ContextForgeNotAvailable,
)
from squadron.pipeline.classification import (
    ClassificationError,
    PipelineClassification,
    PoolClassificationPolicy,
    StepClass,
    StepClassification,
)
from squadron.pipeline.loader import PipelineInfo
from squadron.pipeline.models import PipelineDefinition, StepConfig, ValidationError
from squadron.pipeline.state import CheckpointState, RunState

runner = CliRunner()


def _extract_json(output: str) -> dict[str, object]:
    """Extract the first JSON object from mixed CLI output."""
    start = output.index("{")
    return json.loads(output[start:])


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
        # Pipeline defaults (non-"required" values) are seeded into params
        assert result == {"model": "opus"}

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
            ValidationError(field="step_type", message="Unknown step type 'bad'", action_type="bad"),
            ValidationError(field="model", message="Unresolved alias 'foo'", action_type="pipeline"),
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
            result = runner.invoke(app, ["run", "--status", "run-20260403-test-abc12345"])
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
            result = runner.invoke(app, ["run", "--status", "run-20260403-test-abc12345"])
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

    def test_dry_run_expands_loop_step_body(self) -> None:
        """--dry-run on a loop: step shows body, max, until, on_exhaust."""
        defn = _make_definition(
            params={"slice": "required"},
            steps=[
                StepConfig(
                    step_type="loop",
                    name="design-review-loop",
                    config={
                        "max": 3,
                        "until": "review.pass",
                        "on_exhaust": "checkpoint",
                        "steps": [
                            {"design": {"phase": 4}},
                            {"review": {"template": "slice", "name": "review-design"}},
                        ],
                    },
                )
            ],
        )
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=defn),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
        ):
            result = runner.invoke(app, ["run", "--dry-run", "test", "191"])
        assert result.exit_code == 0
        assert "design-review-loop (loop)" in result.output
        assert "max: 3" in result.output
        assert "until: review.pass" in result.output
        assert "on_exhaust: checkpoint" in result.output
        assert "design-0 (design)" in result.output
        assert "review-design (review)" in result.output

    def test_dry_run_loop_without_until_shows_default_message(self) -> None:
        """--dry-run on a loop: step with no until: shows the no-until fallback."""
        defn = _make_definition(
            params={"slice": "required"},
            steps=[
                StepConfig(
                    step_type="loop",
                    name="single-pass-loop",
                    config={
                        "max": 1,
                        "steps": [{"dispatch": {}}],
                    },
                )
            ],
        )
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=defn),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
        ):
            result = runner.invoke(app, ["run", "--dry-run", "test", "191"])
        assert result.exit_code == 0
        assert _DRY_RUN_NO_UNTIL_DISPLAY in result.output

    def test_dry_run_loop_with_commit_each_iteration_shows_line(self) -> None:
        """--dry-run on a loop: step with commit_each_iteration: true renders it."""
        defn = _make_definition(
            params={"slice": "required"},
            steps=[
                StepConfig(
                    step_type="loop",
                    name="commit-each-loop",
                    config={
                        "max": 3,
                        "until": "action.success",
                        "commit_each_iteration": True,
                        "steps": [{"dispatch": {}}],
                    },
                )
            ],
        )
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=defn),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
        ):
            result = runner.invoke(app, ["run", "--dry-run", "test", "191"])
        assert result.exit_code == 0
        assert _DRY_RUN_COMMIT_EACH_ITERATION_SUFFIX in result.output

    def test_dry_run_loop_without_commit_each_iteration_omits_line(self) -> None:
        """--dry-run on a loop: step without the key renders no such line."""
        defn = _make_definition(
            params={"slice": "required"},
            steps=[
                StepConfig(
                    step_type="loop",
                    name="plain-loop",
                    config={
                        "max": 3,
                        "until": "action.success",
                        "steps": [{"dispatch": {}}],
                    },
                )
            ],
        )
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=defn),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
        ):
            result = runner.invoke(app, ["run", "--dry-run", "test", "191"])
        assert result.exit_code == 0
        assert _DRY_RUN_COMMIT_EACH_ITERATION_SUFFIX not in result.output

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
            result = runner.invoke(app, ["run", "--resume", "run-20260403-test-abc12345"])
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


# ---------------------------------------------------------------------------
# T10: --prompt-only CLI tests
# ---------------------------------------------------------------------------


class TestPromptOnly:
    """Tests for --prompt-only, --next, --step-done, and --verdict."""

    def test_prompt_only_and_dry_run_exclusive(self) -> None:
        result = runner.invoke(app, ["run", "slice", "152", "--prompt-only", "--dry-run"])
        assert result.exit_code == 1
        assert "cannot be used together" in result.output

    def test_next_requires_prompt_only_and_resume(self) -> None:
        result = runner.invoke(app, ["run", "--next", "--resume", "r1"])
        assert result.exit_code == 1
        assert "--next requires both" in result.output

    def test_verdict_requires_step_done(self) -> None:
        result = runner.invoke(app, ["run", "slice", "152", "--verdict", "PASS"])
        assert result.exit_code == 1
        assert "--verdict requires --step-done" in result.output

    def test_step_done_exclusive_with_prompt_only(self) -> None:
        result = runner.invoke(
            app,
            [
                "run",
                "slice",
                "152",
                "--step-done",
                "r1",
                "--prompt-only",
            ],
        )
        assert result.exit_code == 1
        assert "--step-done cannot be combined" in result.output

    @patch("squadron.cli.commands.run.load_pipeline")
    @patch("squadron.cli.commands.run.validate_pipeline", return_value=[])
    @patch("squadron.cli.commands.run.StateManager")
    def test_prompt_only_outputs_json(
        self, mock_cls: MagicMock, mock_validate: MagicMock, mock_load: MagicMock
    ) -> None:

        defn = PipelineDefinition(
            name="slice",
            description="Test",
            params={"slice": "required"},
            steps=[
                StepConfig(
                    step_type="devlog",
                    name="devlog-0",
                    config={"mode": "auto"},
                ),
            ],
        )
        mock_load.return_value = defn
        mock_mgr = MagicMock()
        mock_mgr.init_run.return_value = "run-test-123"
        mock_cls.return_value = mock_mgr

        result = runner.invoke(app, ["run", "slice", "152", "--prompt-only"])
        assert result.exit_code == 0
        parsed = _extract_json(result.output)
        assert parsed["run_id"] == "run-test-123"
        assert parsed["step_name"] == "devlog-0"
        assert len(parsed["actions"]) == 1

    @patch("squadron.cli.commands.run.load_pipeline")
    @patch("squadron.cli.commands.run.StateManager")
    def test_prompt_only_creates_state(self, mock_cls: MagicMock, mock_load: MagicMock) -> None:
        defn = PipelineDefinition(
            name="slice",
            description="Test",
            params={"slice": "required"},
            steps=[
                StepConfig(
                    step_type="devlog",
                    name="devlog-0",
                    config={"mode": "auto"},
                ),
            ],
        )
        mock_load.return_value = defn
        mock_mgr = MagicMock()
        mock_mgr.init_run.return_value = "run-test-123"
        mock_cls.return_value = mock_mgr

        with patch("squadron.cli.commands.run.validate_pipeline", return_value=[]):
            runner.invoke(app, ["run", "slice", "152", "--prompt-only"])
        mock_mgr.init_run.assert_called_once()

    @patch("squadron.cli.commands.run.load_pipeline")
    @patch("squadron.cli.commands.run.StateManager")
    def test_prompt_only_next(self, mock_cls: MagicMock, mock_load: MagicMock) -> None:

        defn = PipelineDefinition(
            name="slice",
            description="Test",
            params={"slice": "required"},
            steps=[
                StepConfig(
                    step_type="devlog",
                    name="devlog-0",
                    config={"mode": "auto"},
                ),
                StepConfig(
                    step_type="devlog",
                    name="devlog-1",
                    config={"mode": "auto"},
                ),
            ],
        )
        mock_load.return_value = defn
        mock_mgr = MagicMock()
        mock_mgr.first_unfinished_step.return_value = "devlog-1"
        mock_state = RunState(
            run_id="run-123",
            pipeline="slice",
            params={"slice": "152"},
            started_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            status="running",
        )
        mock_mgr.load.return_value = mock_state
        mock_cls.return_value = mock_mgr

        result = runner.invoke(
            app,
            [
                "run",
                "--prompt-only",
                "--next",
                "--resume",
                "run-123",
            ],
        )
        assert result.exit_code == 0
        parsed = _extract_json(result.output)
        assert parsed["step_name"] == "devlog-1"

    @patch("squadron.cli.commands.run.load_pipeline")
    @patch("squadron.cli.commands.run.StateManager")
    def test_prompt_only_next_all_done(self, mock_cls: MagicMock, mock_load: MagicMock) -> None:

        defn = PipelineDefinition(
            name="slice",
            description="Test",
            params={},
            steps=[],
        )
        mock_load.return_value = defn
        mock_mgr = MagicMock()
        mock_mgr.first_unfinished_step.return_value = None
        mock_state = RunState(
            run_id="run-123",
            pipeline="slice",
            params={},
            started_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            status="running",
        )
        mock_mgr.load.return_value = mock_state
        mock_cls.return_value = mock_mgr

        result = runner.invoke(
            app,
            [
                "run",
                "--prompt-only",
                "--next",
                "--resume",
                "run-123",
            ],
        )
        assert result.exit_code == 0
        parsed = _extract_json(result.output)
        assert parsed["status"] == "completed"

    @patch("squadron.cli.commands.run._run_post_action_bindings_for_step_done")
    @patch("squadron.cli.commands.run.load_pipeline")
    @patch("squadron.cli.commands.run.StateManager")
    def test_step_done_marks_complete(
        self, mock_cls: MagicMock, mock_load: MagicMock, mock_post_action: MagicMock
    ) -> None:
        defn = PipelineDefinition(
            name="slice",
            description="Test",
            params={},
            steps=[
                StepConfig(
                    step_type="design",
                    name="design-0",
                    config={"phase": 4},
                ),
            ],
        )
        mock_load.return_value = defn
        mock_mgr = MagicMock()
        mock_mgr.first_unfinished_step.return_value = "design-0"
        mock_state = RunState(
            run_id="run-123",
            pipeline="slice",
            params={},
            started_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            status="running",
        )
        mock_mgr.load.return_value = mock_state
        mock_cls.return_value = mock_mgr
        mock_post_action.return_value = None

        result = runner.invoke(app, ["run", "--step-done", "run-123"])
        assert result.exit_code == 0
        mock_mgr.record_step_done.assert_called_once_with("run-123", "design-0", "design", verdict=None)

    @patch("squadron.cli.commands.run._run_post_action_bindings_for_step_done")
    @patch("squadron.cli.commands.run.load_pipeline")
    @patch("squadron.cli.commands.run.StateManager")
    def test_step_done_with_verdict(
        self, mock_cls: MagicMock, mock_load: MagicMock, mock_post_action: MagicMock
    ) -> None:
        defn = PipelineDefinition(
            name="slice",
            description="Test",
            params={},
            steps=[
                StepConfig(
                    step_type="design",
                    name="design-0",
                    config={"phase": 4},
                ),
            ],
        )
        mock_load.return_value = defn
        mock_mgr = MagicMock()
        mock_mgr.first_unfinished_step.return_value = "design-0"
        mock_state = RunState(
            run_id="run-123",
            pipeline="slice",
            params={},
            started_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            status="running",
        )
        mock_mgr.load.return_value = mock_state
        mock_cls.return_value = mock_mgr
        mock_post_action.return_value = None

        result = runner.invoke(
            app,
            ["run", "--step-done", "run-123", "--verdict", "PASS"],
        )
        assert result.exit_code == 0
        mock_mgr.record_step_done.assert_called_once_with(
            "run-123", "design-0", "design", verdict="PASS"
        )

    @patch("squadron.cli.commands.run.StateManager")
    def test_step_done_nonexistent_run(self, mock_cls: MagicMock) -> None:
        mock_mgr = MagicMock()
        mock_mgr.load.side_effect = FileNotFoundError("not found")
        mock_cls.return_value = mock_mgr

        result = runner.invoke(app, ["run", "--step-done", "no-such-run"])
        assert result.exit_code == 1
        assert "not found" in result.output

    @patch("squadron.cli.commands.run.load_pipeline")
    @patch("squadron.cli.commands.run.StateManager")
    def test_step_done_all_steps_done(self, mock_cls: MagicMock, mock_load: MagicMock) -> None:
        defn = PipelineDefinition(
            name="slice",
            description="Test",
            params={},
            steps=[],
        )
        mock_load.return_value = defn
        mock_mgr = MagicMock()
        mock_mgr.first_unfinished_step.return_value = None
        mock_state = RunState(
            run_id="run-123",
            pipeline="slice",
            params={},
            started_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            status="running",
        )
        mock_mgr.load.return_value = mock_state
        mock_cls.return_value = mock_mgr

        result = runner.invoke(app, ["run", "--step-done", "run-123"])
        assert result.exit_code == 0
        assert "already completed" in result.output


class TestStepDonePostActionParity:
    """Design D9: --step-done runs POST_ACTION bindings before recording."""

    def _run_state(self) -> RunState:
        return RunState(
            run_id="run-123",
            pipeline="slice",
            params={},
            started_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            status="running",
        )

    def _design_pipeline(self) -> PipelineDefinition:
        return PipelineDefinition(
            name="slice",
            description="Test",
            params={},
            steps=[StepConfig(step_type="design", name="design-0", config={"phase": 4})],
        )

    def _implement_pipeline(self) -> PipelineDefinition:
        return PipelineDefinition(
            name="slice",
            description="Test",
            params={},
            steps=[StepConfig(step_type="implement", name="implement-0", config={"phase": 6})],
        )

    @patch("squadron.cli.commands.run.run_event")
    @patch("squadron.cli.commands.run.load_pipeline")
    @patch("squadron.cli.commands.run.StateManager")
    def test_failing_post_condition_blocks_step_done(
        self, mock_cls: MagicMock, mock_load: MagicMock, mock_run_event: MagicMock
    ) -> None:
        from squadron.events.dispatcher import EventOutcome, OutcomeErrorKind
        from squadron.pipeline.models import ActionResult

        mock_load.return_value = self._design_pipeline()
        mock_mgr = MagicMock()
        mock_mgr.first_unfinished_step.return_value = "design-0"
        mock_mgr.load.return_value = self._run_state()
        mock_cls.return_value = mock_mgr

        mock_run_event.return_value = [
            EventOutcome(
                action_name="squadron.dispatch-artifact",
                result=ActionResult(
                    success=False,
                    action_type="squadron.dispatch-artifact",
                    outputs={},
                    error="no design artifact was written",
                ),
                error_kind=OutcomeErrorKind.NONE,
            )
        ]

        result = runner.invoke(app, ["run", "--step-done", "run-123"])

        assert result.exit_code != 0
        assert "squadron.dispatch-artifact" in result.output
        mock_mgr.record_step_done.assert_not_called()

    @patch("squadron.cli.commands.run.run_event")
    @patch("squadron.cli.commands.run.load_pipeline")
    @patch("squadron.cli.commands.run.StateManager")
    def test_artifact_present_records_step_and_exits_zero(
        self, mock_cls: MagicMock, mock_load: MagicMock, mock_run_event: MagicMock
    ) -> None:
        from squadron.events.dispatcher import EventOutcome, OutcomeErrorKind
        from squadron.pipeline.models import ActionResult

        mock_load.return_value = self._design_pipeline()
        mock_mgr = MagicMock()
        mock_mgr.first_unfinished_step.return_value = "design-0"
        mock_mgr.load.return_value = self._run_state()
        mock_cls.return_value = mock_mgr

        mock_run_event.return_value = [
            EventOutcome(
                action_name="squadron.dispatch-artifact",
                result=ActionResult(success=True, action_type="squadron.dispatch-artifact", outputs={}),
                error_kind=OutcomeErrorKind.NONE,
            )
        ]

        result = runner.invoke(app, ["run", "--step-done", "run-123"])

        assert result.exit_code == 0
        mock_mgr.record_step_done.assert_called_once_with("run-123", "design-0", "design", verdict=None)

    @patch("squadron.cli.commands.run.run_event")
    @patch("squadron.cli.commands.run.load_pipeline")
    @patch("squadron.cli.commands.run.StateManager")
    def test_implement_phase_unaffected_by_post_action_bindings(
        self, mock_cls: MagicMock, mock_load: MagicMock, mock_run_event: MagicMock
    ) -> None:
        from squadron.events.dispatcher import EventOutcome, OutcomeErrorKind
        from squadron.pipeline.models import ActionResult

        mock_load.return_value = self._implement_pipeline()
        mock_mgr = MagicMock()
        mock_mgr.first_unfinished_step.return_value = "implement-0"
        mock_mgr.load.return_value = self._run_state()
        mock_cls.return_value = mock_mgr

        # dispatch-artifact no-ops (expected_artifact_kind is None for
        # implement); revision-stamp no-ops (iteration=0). Both report success.
        mock_run_event.return_value = [
            EventOutcome(
                action_name="squadron.dispatch-artifact",
                result=ActionResult(success=True, action_type="squadron.dispatch-artifact", outputs={}),
                error_kind=OutcomeErrorKind.NONE,
            ),
            EventOutcome(
                action_name="squadron.revision-stamp",
                result=ActionResult(success=True, action_type="squadron.revision-stamp", outputs={}),
                error_kind=OutcomeErrorKind.NONE,
            ),
        ]

        result = runner.invoke(app, ["run", "--step-done", "run-123"])

        assert result.exit_code == 0
        mock_mgr.record_step_done.assert_called_once_with(
            "run-123", "implement-0", "implement", verdict=None
        )


# ---------------------------------------------------------------------------
# Helpers shared by explain tests
# ---------------------------------------------------------------------------


def _make_step_classification(
    name: str = "design",
    action_type: str = "dispatch",
    classification: StepClass = StepClass.SDK_REQUIRED,
    resolved_alias: str | None = "sonnet",
    resolved_model_id: str | None = "claude-sonnet-4-6",
    profile: str | None = "sdk",
    rationale: str = "alias 'sonnet' resolves to profile 'sdk' (SDK)",
) -> StepClassification:
    return StepClassification(
        step_name=name,
        step_index=0,
        action_type=action_type,
        resolved_alias=resolved_alias,
        resolved_model_id=resolved_model_id,
        profile=profile,
        classification=classification,
        rationale=rationale,
    )


def _make_pipeline_classification(
    steps: list[StepClassification] | None = None,
    policy: PoolClassificationPolicy = PoolClassificationPolicy.LAZY,
    name: str = "my-pipeline",
) -> PipelineClassification:
    return PipelineClassification(
        pipeline_name=name,
        steps=tuple(steps or [_make_step_classification()]),
        policy=policy,
    )


# ---------------------------------------------------------------------------
# T3: TestExplainMutualExclusivity
# ---------------------------------------------------------------------------


class TestExplainMutualExclusivity:
    """--explain cannot be combined with execution options."""

    def test_explain_with_resume_exits_error(self) -> None:
        result = runner.invoke(app, ["run", "p", "--explain", "--resume", "run-123"])
        assert result.exit_code == 1
        assert "--explain" in result.output

    def test_explain_with_from_exits_error(self) -> None:
        result = runner.invoke(app, ["run", "p", "--explain", "--from", "step-1"])
        assert result.exit_code == 1
        assert "--explain" in result.output

    def test_explain_with_dry_run_exits_error(self) -> None:
        result = runner.invoke(app, ["run", "p", "--explain", "--dry-run"])
        assert result.exit_code == 1
        assert "--explain" in result.output

    def test_explain_with_prompt_only_exits_error(self) -> None:
        result = runner.invoke(app, ["run", "p", "--explain", "--prompt-only"])
        assert result.exit_code == 1
        assert "--explain" in result.output

    def test_explain_with_validate_exits_error(self) -> None:
        result = runner.invoke(app, ["run", "p", "--explain", "--validate"])
        assert result.exit_code == 1
        assert "--explain" in result.output


# ---------------------------------------------------------------------------
# T7+T8: TestExplainCommand — happy paths and error paths
# ---------------------------------------------------------------------------


class TestExplainCommand:
    """sq run --explain classifies and renders a pipeline without executing."""

    def _patch_explain(
        self,
        classification: PipelineClassification,
        defn: PipelineDefinition | None = None,
    ):
        """Return a context-manager stack for a successful explain invocation."""
        if defn is None:
            defn = _make_definition()
        return (
            patch("squadron.cli.commands.run.load_pipeline", return_value=defn),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch("squadron.cli.commands.run.DefaultPoolBackend"),
            patch("squadron.cli.commands.run.ModelResolver"),
            patch("squadron.cli.commands.run.classify_pipeline", return_value=classification),
        )

    # T7a — all SDK_REQUIRED steps → Claude-required (persistent)
    def test_all_sdk_pipeline(self) -> None:
        classification = _make_pipeline_classification(
            steps=[_make_step_classification(classification=StepClass.SDK_REQUIRED)]
        )
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=_make_definition()),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch("squadron.cli.commands.run.DefaultPoolBackend"),
            patch("squadron.cli.commands.run.ModelResolver"),
            patch("squadron.cli.commands.run.classify_pipeline", return_value=classification),
        ):
            result = runner.invoke(app, ["run", "my-pipeline", "--explain"])
        assert result.exit_code == 0
        # Rich may truncate "sdk_required" in narrow terminals; "sdk_requi" is always present
        assert "sdk_requi" in result.output
        assert "Claude-required (persistent)" in result.output

    # T7b — all NON_SDK steps → Claude-free
    def test_claude_free_pipeline(self) -> None:
        classification = _make_pipeline_classification(
            steps=[
                _make_step_classification(
                    classification=StepClass.NON_SDK,
                    resolved_model_id="minimax-01",
                    profile="openrouter",
                    rationale="alias 'minimax' resolves to profile 'openrouter' (non-SDK)",
                )
            ]
        )
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=_make_definition()),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch("squadron.cli.commands.run.DefaultPoolBackend"),
            patch("squadron.cli.commands.run.ModelResolver"),
            patch("squadron.cli.commands.run.classify_pipeline", return_value=classification),
        ):
            result = runner.invoke(app, ["run", "my-pipeline", "--explain"])
        assert result.exit_code == 0
        assert "non_sdk" in result.output
        assert "Claude-free" in result.output
        assert "needs persistent session" in result.output.lower()
        assert "no" in result.output

    # T7c — SDK review step, needs_persistent_session=False → one-shot only
    def test_one_shot_only_pipeline(self) -> None:
        classification = _make_pipeline_classification(
            steps=[
                _make_step_classification(
                    name="review",
                    action_type="review",
                    classification=StepClass.SDK_REQUIRED,
                )
            ]
        )
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=_make_definition()),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch("squadron.cli.commands.run.DefaultPoolBackend"),
            patch("squadron.cli.commands.run.ModelResolver"),
            patch("squadron.cli.commands.run.classify_pipeline", return_value=classification),
        ):
            result = runner.invoke(app, ["run", "my-pipeline", "--explain"])
        assert result.exit_code == 0
        assert "Claude-required (one-shot only)" in result.output

    # T7d — --param model=minimax → ModelResolver constructed with cli_override="minimax"
    def test_model_override_via_param(self) -> None:
        classification = _make_pipeline_classification()
        mock_resolver_cls = MagicMock()
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=_make_definition()),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch("squadron.cli.commands.run.DefaultPoolBackend"),
            patch("squadron.cli.commands.run.ModelResolver", mock_resolver_cls),
            patch("squadron.cli.commands.run.classify_pipeline", return_value=classification),
        ):
            result = runner.invoke(app, ["run", "p", "--explain", "--param", "model=minimax"])
        assert result.exit_code == 0
        mock_resolver_cls.assert_called_once()
        call_kwargs = mock_resolver_cls.call_args.kwargs
        assert call_kwargs.get("cli_override") == "minimax"

    # T7e — --strict → classify_pipeline called with STRICT policy
    def test_strict_flag_passed_to_classify(self) -> None:
        classification = _make_pipeline_classification(policy=PoolClassificationPolicy.STRICT)
        mock_classify = MagicMock(return_value=classification)
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=_make_definition()),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch("squadron.cli.commands.run.DefaultPoolBackend"),
            patch("squadron.cli.commands.run.ModelResolver"),
            patch("squadron.cli.commands.run.classify_pipeline", mock_classify),
        ):
            result = runner.invoke(app, ["run", "p", "--explain", "--strict"])
        assert result.exit_code == 0
        mock_classify.assert_called_once()
        call_kwargs = mock_classify.call_args.kwargs
        assert call_kwargs.get("policy") == PoolClassificationPolicy.STRICT

    # T8a — pipeline not found → exit 1, "not found"
    def test_pipeline_not_found(self) -> None:
        with patch(
            "squadron.cli.commands.run.load_pipeline",
            side_effect=FileNotFoundError("no such pipeline"),
        ):
            result = runner.invoke(app, ["run", "no-such", "--explain"])
        assert result.exit_code == 1
        assert "not found" in result.output

    # T8b — validation errors → exit 1, field+message in output
    def test_validation_errors(self) -> None:
        defn = _make_definition()
        errors = [
            ValidationError(field="model", message="Unresolved alias 'bad'", action_type="dispatch")
        ]
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=defn),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=errors),
        ):
            result = runner.invoke(app, ["run", "p", "--explain"])
        assert result.exit_code == 1
        assert "model" in result.output
        assert "Unresolved alias" in result.output

    # T8c — ClassificationError → exit 1, "Classification failed"
    def test_classification_error(self) -> None:
        defn = _make_definition()
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=defn),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch("squadron.cli.commands.run.DefaultPoolBackend"),
            patch("squadron.cli.commands.run.ModelResolver"),
            patch(
                "squadron.cli.commands.run.classify_pipeline",
                side_effect=ClassificationError("step has no model"),
            ),
        ):
            result = runner.invoke(app, ["run", "p", "--explain"])
        assert result.exit_code == 1
        assert "Classification failed" in result.output

    # T9a — container inner row shows ↳ prefix
    def test_explain_each_container_shows_indent_prefix(self) -> None:
        container_row = StepClassification(
            step_name="each-0",
            step_index=0,
            action_type="dispatch",
            resolved_alias="sonnet",
            resolved_model_id="claude-sonnet-4-6",
            profile="sdk",
            classification=StepClass.SDK_REQUIRED,
            rationale="alias 'sonnet' resolves to profile 'sdk' (SDK)",
            container_path="dispatch-0",
        )
        classification = _make_pipeline_classification(steps=[container_row])
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=_make_definition()),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch("squadron.cli.commands.run.DefaultPoolBackend"),
            patch("squadron.cli.commands.run.ModelResolver"),
            patch("squadron.cli.commands.run.classify_pipeline", return_value=classification),
        ):
            result = runner.invoke(app, ["run", "my-pipeline", "--explain"])
        assert result.exit_code == 0
        # Rich may wrap/truncate cell values in narrow test terminals;
        # assert the ↳ prefix appears (the inner step prefix is rendered).
        assert "↳" in result.output

    # T9b — container header row is shown for the container step
    def test_explain_container_header_row_shown(self) -> None:
        container_row = StepClassification(
            step_name="each-0",
            step_index=0,
            action_type="dispatch",
            resolved_alias="sonnet",
            resolved_model_id="claude-sonnet-4-6",
            profile="sdk",
            classification=StepClass.SDK_REQUIRED,
            rationale="alias 'sonnet' resolves to profile 'sdk' (SDK)",
            container_path="dispatch-0",
        )
        classification = _make_pipeline_classification(steps=[container_row])
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=_make_definition()),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch("squadron.cli.commands.run.DefaultPoolBackend"),
            patch("squadron.cli.commands.run.ModelResolver"),
            patch("squadron.cli.commands.run.classify_pipeline", return_value=classification),
        ):
            result = runner.invoke(app, ["run", "my-pipeline", "--explain"])
        assert result.exit_code == 0
        assert "each-0" in result.output
        # Rich may truncate "(container)" in narrow test terminals; check prefix.
        assert "contain" in result.output

    # T9c — top-level row (container_path=None) does not show ↳
    def test_explain_top_level_row_no_indent(self) -> None:
        top_row = _make_step_classification(name="dispatch-0")
        classification = _make_pipeline_classification(steps=[top_row])
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=_make_definition()),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch("squadron.cli.commands.run.DefaultPoolBackend"),
            patch("squadron.cli.commands.run.ModelResolver"),
            patch("squadron.cli.commands.run.classify_pipeline", return_value=classification),
        ):
            result = runner.invoke(app, ["run", "my-pipeline", "--explain"])
        assert result.exit_code == 0
        assert "↳" not in result.output
