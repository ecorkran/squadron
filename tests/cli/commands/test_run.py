"""Unit tests for the sq run command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.run import _assemble_params, _resolve_target
from squadron.pipeline.models import PipelineDefinition, StepConfig

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
        result = runner.invoke(app, ["run", "--list", "slice-lifecycle"])
        assert result.exit_code == 1
        assert "--list cannot be combined" in result.output

    def test_list_with_model_exits_error(self) -> None:
        result = runner.invoke(app, ["run", "--list", "--model", "opus"])
        assert result.exit_code == 1
        assert "--list cannot be combined" in result.output

    def test_status_with_pipeline_exits_error(self) -> None:
        result = runner.invoke(app, ["run", "--status", "latest", "slice-lifecycle"])
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
