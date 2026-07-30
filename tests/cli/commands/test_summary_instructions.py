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
        assert "Using: myproject-P4.md" in result.output

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

    def test_restore_multiple_files_lists_options_on_stderr(self, tmp_path: Path) -> None:
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
        assert "Using: myproject-P5.md" in result.output
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


# ---------------------------------------------------------------------------
# --restore --key selection
# ---------------------------------------------------------------------------


class TestRestoreKey:
    """--key selects a specific saved summary instead of the most recent."""

    def _run(self, summaries: Path, *args: str):
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
            return runner.invoke(app, ["_summary-instructions", "--restore", *args])

    def _two_summaries(self, tmp_path: Path) -> Path:
        """P4 is older; interactive is the most recent."""
        summaries = tmp_path / "summaries"
        summaries.mkdir()
        _write_summary(summaries, "myproject-P4.md", "old p4 summary", 1000.0)
        _write_summary(summaries, "myproject-interactive.md", "new interactive summary", 2000.0)
        return summaries

    def test_key_selects_older_summary_over_most_recent(self, tmp_path: Path) -> None:
        """--key P4 wins over the more recent interactive summary."""
        result = self._run(self._two_summaries(tmp_path), "--key", "P4")

        assert result.exit_code == 0
        assert "Using: myproject-P4.md" in result.output
        assert "old p4 summary" in result.output
        assert "new interactive summary" not in result.output

    def test_key_matches_case_insensitively(self, tmp_path: Path) -> None:
        """Lowercase --key resolves a file saved with uppercase key, and vice versa."""
        summaries = self._two_summaries(tmp_path)

        lowered = self._run(summaries, "--key", "p4")
        assert lowered.exit_code == 0
        assert "Using: myproject-P4.md" in lowered.output

        raised = self._run(summaries, "--key", "INTERACTIVE")
        assert raised.exit_code == 0
        assert "Using: myproject-interactive.md" in raised.output

    def test_unknown_key_exits_1_and_lists_available(self, tmp_path: Path) -> None:
        """A key with no matching file fails loudly and names the real options."""
        result = self._run(self._two_summaries(tmp_path), "--key", "nope")

        assert result.exit_code == 1
        assert "no summary saved under key 'nope'" in result.output
        assert "P4" in result.output
        assert "interactive" in result.output
        # The unselected content must not leak into the restore stream.
        assert "old p4 summary" not in result.output

    def test_without_key_still_uses_most_recent(self, tmp_path: Path) -> None:
        """Default path is unchanged: bare --restore takes the newest summary."""
        result = self._run(self._two_summaries(tmp_path))

        assert result.exit_code == 0
        assert "Using: myproject-interactive.md" in result.output
        assert "new interactive summary" in result.output

    def test_key_with_single_summary(self, tmp_path: Path) -> None:
        """--key works when only one summary exists (no picker listing shown)."""
        summaries = tmp_path / "summaries"
        summaries.mkdir()
        _write_summary(summaries, "myproject-P4.md", "only summary", 1000.0)

        result = self._run(summaries, "--key", "p4")

        assert result.exit_code == 0
        assert "only summary" in result.output
        assert "Found" not in result.output

    def test_unknown_key_with_no_files_reports_missing_files(self, tmp_path: Path) -> None:
        """No summaries at all: the empty-directory error wins over the key error."""
        summaries = tmp_path / "summaries"
        summaries.mkdir()

        result = self._run(summaries, "--key", "p4")

        assert result.exit_code == 1
        assert "no summary files found" in result.output
