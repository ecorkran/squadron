"""Tests for summary_instructions --restore flag behavior (T9)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from squadron.cli.app import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_summary(summaries_dir: Path, name: str, content: str, mtime: float) -> Path:
    """Write a summary file with a given mtime (seconds since epoch)."""
    path = summaries_dir / name
    path.write_text(content, encoding="utf-8")
    import os

    os.utime(path, (mtime, mtime))
    return path


# ---------------------------------------------------------------------------
# T9 — --restore flag behavior
# ---------------------------------------------------------------------------


class TestRestoreFlag:
    def test_restore_single_file_prints_contents(self, tmp_path: Path) -> None:
        """Single matching file: contents on stdout, exit 0."""
        summaries = tmp_path / "summaries"
        summaries.mkdir()
        _write_summary(summaries, "myproject-P4.md", "summary content here", 1000.0)

        runner = CliRunner()
        with (
            patch(
                "squadron.cli.commands.summary_instructions.gather_cf_params",
                return_value={"project": "myproject"},
            ),
            patch(
                "squadron.cli.commands.summary_instructions._SUMMARIES_DIR",
                summaries,
            ),
        ):
            result = runner.invoke(app, ["_summary-instructions", "--restore"])

        assert result.exit_code == 0
        assert "summary content here" in result.output

    def test_restore_multiple_files_uses_most_recent(self, tmp_path: Path) -> None:
        """Multiple matching files: most recent contents on stdout, list on stderr."""
        summaries = tmp_path / "summaries"
        summaries.mkdir()
        # older file
        _write_summary(summaries, "myproject-P4.md", "old summary", 1000.0)
        # newer file
        _write_summary(summaries, "myproject-P5.md", "new summary", 2000.0)

        runner = CliRunner()
        with (
            patch(
                "squadron.cli.commands.summary_instructions.gather_cf_params",
                return_value={"project": "myproject"},
            ),
            patch(
                "squadron.cli.commands.summary_instructions._SUMMARIES_DIR",
                summaries,
            ),
        ):
            result = runner.invoke(app, ["_summary-instructions", "--restore"])

        assert result.exit_code == 0
        assert "new summary" in result.output

    def test_restore_multiple_files_lists_options_on_stderr(
        self, tmp_path: Path
    ) -> None:
        """Multiple files: lists pipeline names and selects most recent."""
        summaries = tmp_path / "summaries"
        summaries.mkdir()
        _write_summary(summaries, "myproject-P4.md", "old summary", 1000.0)
        _write_summary(summaries, "myproject-P5.md", "new summary", 2000.0)

        runner = CliRunner()
        with (
            patch(
                "squadron.cli.commands.summary_instructions.gather_cf_params",
                return_value={"project": "myproject"},
            ),
            patch(
                "squadron.cli.commands.summary_instructions._SUMMARIES_DIR",
                summaries,
            ),
        ):
            result = runner.invoke(app, ["_summary-instructions", "--restore"])

        assert result.exit_code == 0
        # CliRunner merges stderr/stdout by default — verify selection info present
        assert "Found 2 summaries" in result.output
        assert "Using most recent" in result.output
        assert "new summary" in result.output

    def test_restore_no_files_exits_1(self, tmp_path: Path) -> None:
        """No matching files → exit 1 with error message."""
        summaries = tmp_path / "summaries"
        summaries.mkdir()

        runner = CliRunner()
        with (
            patch(
                "squadron.cli.commands.summary_instructions.gather_cf_params",
                return_value={"project": "myproject"},
            ),
            patch(
                "squadron.cli.commands.summary_instructions._SUMMARIES_DIR",
                summaries,
            ),
        ):
            result = runner.invoke(app, ["_summary-instructions", "--restore"])

        assert result.exit_code == 1
        assert "no summary files found" in result.output

    def test_restore_no_project_exits_1(self, tmp_path: Path) -> None:
        """CF unavailable (no project) → exit 1 with error message."""
        summaries = tmp_path / "summaries"
        summaries.mkdir()

        runner = CliRunner()
        with (
            patch(
                "squadron.cli.commands.summary_instructions.gather_cf_params",
                return_value={},
            ),
            patch(
                "squadron.cli.commands.summary_instructions._SUMMARIES_DIR",
                summaries,
            ),
        ):
            result = runner.invoke(app, ["_summary-instructions", "--restore"])

        assert result.exit_code == 1
        assert "cannot resolve project name" in result.output
