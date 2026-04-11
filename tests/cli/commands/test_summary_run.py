"""Tests for the sq _summary-run hidden subcommand (T10)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from squadron.cli.app import app

_runner = CliRunner()


def _invoke(*args: str) -> object:
    return _runner.invoke(app, ["_summary-run", *args])


class TestSummaryRunHappyPath:
    def test_happy_path_prints_summary_and_exits_0(self) -> None:
        """Mocked provider returns text; command prints it to stdout."""
        with (
            patch(
                "squadron.cli.commands.summary_run.capture_summary_via_profile",
                new=AsyncMock(return_value="SUMMARY OUTPUT"),
            ),
            patch(
                "squadron.cli.commands.summary_run.load_compaction_template"
            ) as mock_load,
            patch(
                "squadron.cli.commands.summary_run.render_instructions",
                return_value="rendered instructions",
            ),
        ):
            from squadron.pipeline.compaction_templates import CompactionTemplate

            mock_load.return_value = CompactionTemplate(
                name="minimal",
                description="d",
                instructions="summarize",
            )
            result = _invoke(
                "--template",
                "minimal",
                "--profile",
                "openrouter",
                "--model",
                "minimax-01",
            )

        assert result.exit_code == 0
        assert "SUMMARY OUTPUT" in (result.output or "")

    def test_params_passed_to_render(self) -> None:
        """--param flags are parsed and forwarded to render_instructions."""
        render_calls: list[dict[str, object]] = []

        def _fake_render(template: object, **kwargs: object) -> str:
            render_calls.append(dict(kwargs))
            return "rendered"

        with (
            patch(
                "squadron.cli.commands.summary_run.capture_summary_via_profile",
                new=AsyncMock(return_value="OK"),
            ),
            patch(
                "squadron.cli.commands.summary_run.load_compaction_template"
            ) as mock_load,
            patch(
                "squadron.cli.commands.summary_run.render_instructions",
                side_effect=_fake_render,
            ),
        ):
            from squadron.pipeline.compaction_templates import CompactionTemplate

            mock_load.return_value = CompactionTemplate(
                name="minimal",
                description="d",
                instructions="summarize",
            )
            result = _invoke(
                "--template",
                "minimal",
                "--profile",
                "openrouter",
                "--model",
                "minimax-01",
                "--param",
                "slice=164",
                "--param",
                "phase=6",
            )

        assert result.exit_code == 0
        assert render_calls
        params = render_calls[0].get("pipeline_params", {})
        assert params == {"slice": "164", "phase": "6"}  # type: ignore[comparison-overlap]


class TestSummaryRunErrorCases:
    def test_bad_param_format_exits_1(self) -> None:
        """--param value without '=' produces exit code 1 with stderr message."""
        result = _invoke(
            "--template",
            "minimal",
            "--profile",
            "openrouter",
            "--model",
            "minimax-01",
            "--param",
            "badvalue",
        )

        assert result.exit_code == 1
        assert "badvalue" in (result.output or "")

    def test_missing_template_exits_1(self) -> None:
        """Non-existent template produces exit code 1."""
        result = _invoke(
            "--template",
            "does-not-exist",
            "--profile",
            "openrouter",
            "--model",
            "minimax-01",
        )

        assert result.exit_code == 1
        assert "does-not-exist" in (result.output or "")

    def test_provider_raises_exits_1(self) -> None:
        """Provider exception is caught and reported as exit 1."""
        with (
            patch(
                "squadron.cli.commands.summary_run.capture_summary_via_profile",
                new=AsyncMock(side_effect=RuntimeError("network failed")),
            ),
            patch(
                "squadron.cli.commands.summary_run.load_compaction_template"
            ) as mock_load,
            patch(
                "squadron.cli.commands.summary_run.render_instructions",
                return_value="rendered",
            ),
        ):
            from squadron.pipeline.compaction_templates import CompactionTemplate

            mock_load.return_value = CompactionTemplate(
                name="minimal",
                description="d",
                instructions="summarize",
            )
            result = _invoke(
                "--template",
                "minimal",
                "--profile",
                "openrouter",
                "--model",
                "minimax-01",
            )

        assert result.exit_code == 1
        assert "network failed" in (result.output or "")
