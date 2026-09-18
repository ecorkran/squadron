"""Tests for summary_instructions --restore flag behavior (T9)."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.summary_instructions import _sibling_projects

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


def _isolated_cwd(tmp_path: Path) -> Path:
    """A checkout dir whose parent holds no sibling projects.

    `--cwd` defaults to ".", which would make `_sibling_projects` enumerate the
    real parent of wherever pytest runs — passing on a dev machine that happens
    to have a same-prefix checkout and failing on CI. Every --restore
    invocation pins it to a directory this test controls.
    """
    cwd = tmp_path / "checkouts" / "myproject"
    cwd.mkdir(parents=True, exist_ok=True)
    return cwd


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
            result = runner.invoke(
                app, ["_summary-instructions", "--restore", "--cwd", str(_isolated_cwd(tmp_path))]
            )

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
            result = runner.invoke(
                app, ["_summary-instructions", "--restore", "--cwd", str(_isolated_cwd(tmp_path))]
            )

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
            result = runner.invoke(
                app, ["_summary-instructions", "--restore", "--cwd", str(_isolated_cwd(tmp_path))]
            )

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
            result = runner.invoke(
                app, ["_summary-instructions", "--restore", "--cwd", str(_isolated_cwd(tmp_path))]
            )

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
            result = runner.invoke(
                app, ["_summary-instructions", "--restore", "--cwd", str(_isolated_cwd(tmp_path))]
            )

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
            return runner.invoke(
                app,
                [
                    "_summary-instructions",
                    "--restore",
                    "--cwd",
                    str(_isolated_cwd(summaries.parent)),
                    *args,
                ],
            )

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


# ---------------------------------------------------------------------------
# #103 — sibling-project exclusion from default selection
# ---------------------------------------------------------------------------


class TestSiblingProjects:
    """`_sibling_projects` derives sibling checkout names from the filesystem."""

    def test_returns_sibling_dirs_excluding_self(self, tmp_path: Path) -> None:
        # Nested under its own root: pytest's tmp_path has sibling dirs of its
        # own, so the enumerated parent must be one this test alone controls.
        root = tmp_path / "checkouts"
        root.mkdir()
        (root / "squadron").mkdir()
        (root / "squadron-pr").mkdir()
        (root / "other-repo").mkdir()
        (root / "loose-file.md").write_text("not a dir\n", encoding="utf-8")

        result = _sibling_projects(str(root / "squadron"), "squadron")

        assert result == {"squadron-pr", "other-repo"}

    def test_no_siblings_returns_empty_set(self, tmp_path: Path) -> None:
        root = tmp_path / "checkouts"
        root.mkdir()
        (root / "squadron").mkdir()

        assert _sibling_projects(str(root / "squadron"), "squadron") == set()

    def test_oserror_degrades_to_empty_set_with_warning(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """An unreadable parent must not fail the restore — observable, not silent."""
        root = tmp_path / "checkouts"
        root.mkdir()
        (root / "squadron").mkdir()

        def _raise(self: Path) -> object:
            raise OSError("permission denied")

        monkeypatch.setattr(Path, "iterdir", _raise)

        with caplog.at_level(logging.WARNING):
            result = _sibling_projects(str(root / "squadron"), "squadron")

        assert result == set()
        assert any(rec.levelno == logging.WARNING for rec in caplog.records)
        assert "cannot enumerate siblings" in caplog.text


class TestRestoreSiblingExclusion:
    """End-to-end: default selection skips sibling-owned files; --key reaches them."""

    def _layout(self, tmp_path: Path, *, project: str, sibling: str) -> tuple[Path, Path]:
        """Return (cwd, summaries) for two real checkouts under a private root."""
        root = tmp_path / "checkouts"
        root.mkdir()
        cwd = root / project
        cwd.mkdir()
        (root / sibling).mkdir()
        summaries = tmp_path / "summaries"
        summaries.mkdir()
        return cwd, summaries

    def _run(self, summaries: Path, cwd: Path, project: str, *args: str):
        runner = CliRunner()
        with (
            patch(
                "squadron.cli.commands.summary_instructions.gather_cf_params",
                return_value={"project": project},
            ),
            patch(
                "squadron.cli.commands.summary_instructions._SUMMARIES_DIR",
                summaries,
            ),
        ):
            return runner.invoke(
                app,
                ["_summary-instructions", "--restore", "--cwd", str(cwd), *args],
            )

    def test_default_skips_newer_sibling_file(self, tmp_path: Path) -> None:
        """#103's motivating case: the newer sibling file must not win."""
        cwd, summaries = self._layout(tmp_path, project="squadron", sibling="squadron-pr")
        _write_summary(summaries, "squadron-interactive.md", "own summary", 1000.0)
        _write_summary(summaries, "squadron-pr-p5a.md", "sibling summary", 2000.0)

        result = self._run(summaries, cwd, "squadron")

        assert result.exit_code == 0, result.output
        assert "own summary" in result.output
        assert "Using: squadron-interactive.md" in result.output

    def test_key_still_restores_the_excluded_sibling_file(self, tmp_path: Path) -> None:
        """The escape hatch: exclusion scopes the default, not --key."""
        cwd, summaries = self._layout(tmp_path, project="squadron", sibling="squadron-pr")
        _write_summary(summaries, "squadron-interactive.md", "own summary", 1000.0)
        _write_summary(summaries, "squadron-pr-p5a.md", "sibling summary", 2000.0)

        result = self._run(summaries, cwd, "squadron", "--key", "pr-p5a")

        assert result.exit_code == 0, result.output
        assert "sibling summary" in result.output
        assert "Using: squadron-pr-p5a.md" in result.output

    def test_listing_marks_excluded_entries(self, tmp_path: Path) -> None:
        cwd, summaries = self._layout(tmp_path, project="squadron", sibling="squadron-pr")
        _write_summary(summaries, "squadron-interactive.md", "own summary", 1000.0)
        _write_summary(summaries, "squadron-pr-p5a.md", "sibling summary", 2000.0)

        result = self._run(summaries, cwd, "squadron")

        assert "squadron-pr-p5a.md" in result.output
        assert "excluded from default" in result.output
        assert "sibling project 'squadron-pr'" in result.output
        assert "--key 'pr-p5a'" in result.output

    def test_all_matches_excluded_errors_rather_than_falling_back(self, tmp_path: Path) -> None:
        """No own summary: refuse, don't silently restore a sibling's."""
        cwd, summaries = self._layout(tmp_path, project="squadron", sibling="squadron-pr")
        _write_summary(summaries, "squadron-pr-p5a.md", "sibling summary", 2000.0)

        result = self._run(summaries, cwd, "squadron")

        assert result.exit_code == 1
        assert "no summary files found for project 'squadron'" in result.output
        assert "sibling summary" not in result.output

    def test_shorter_sibling_does_not_exclude_own_summaries(self, tmp_path: Path) -> None:
        """Reversed roles: from squadron-pr, sibling `squadron` prefixes every own stem.

        Without the prefix-continuation qualifier, `clean` is empty here and the
        command fails in a checkout holding summaries of its own — the inverse
        of #103 and strictly worse than the unfixed behavior.
        """
        cwd, summaries = self._layout(tmp_path, project="squadron-pr", sibling="squadron")
        _write_summary(summaries, "squadron-pr-interactive.md", "pr older", 1000.0)
        _write_summary(summaries, "squadron-pr-p5a.md", "pr newest", 2000.0)

        result = self._run(summaries, cwd, "squadron-pr")

        assert result.exit_code == 0, result.output
        assert "pr newest" in result.output
        assert "Using: squadron-pr-p5a.md" in result.output
        assert "excluded from default" not in result.output
