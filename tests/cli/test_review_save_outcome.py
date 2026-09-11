"""Save-outcome tests for every review subcommand (slice 916, issue #70).

The prior model was a bare ``saved`` boolean initialized to ``True``, so a
review that was never persistable reported success for a write that was never
attempted. These tests pin all four outcomes across all four subcommands.

Assertions are on exit codes, the ``SaveOutcome`` enum, and whether an artifact
appeared — never on warning text, which is not logical structure.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.review import SaveOutcome, _resolve_save_outcome, _worst_outcome
from squadron.review.models import ReviewResult, Verdict


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def _result(verdict: Verdict = Verdict.PASS) -> ReviewResult:
    return ReviewResult(
        verdict=verdict,
        findings=[],
        raw_output="## Summary\nPASS\n",
        template_name="code",
        input_files={"cwd": "."},
    )


@pytest.fixture
def mock_run_review():
    with patch(
        "squadron.cli.commands.review.run_review_with_profile",
        new_callable=AsyncMock,
        return_value=_result(),
    ) as mock:
        yield mock


@pytest.fixture
def docs(tmp_path: Path) -> tuple[str, str]:
    input_doc = tmp_path / "input.md"
    against_doc = tmp_path / "against.md"
    input_doc.write_text("# input\n")
    against_doc.write_text("# against\n")
    return str(input_doc), str(against_doc)


def _argv(subcommand: str, docs: tuple[str, str]) -> list[str]:
    """Minimal invocation of each subcommand with no slice identifier."""
    input_doc, against_doc = docs
    if subcommand == "code":
        return ["review", "code", "--files", "**/*"]
    argv = ["review", subcommand, input_doc]
    if subcommand in ("slice", "tasks"):
        argv += ["--against", against_doc]
    return argv


SUBCOMMANDS = ["slice", "arch", "tasks", "code"]


class TestSaveOutcomeResolution:
    """The outcome helper itself — the unit every subcommand shares."""

    def test_no_save_is_suppressed_without_attempting(self) -> None:
        calls: list[int] = []
        outcome = _resolve_save_outcome(
            no_save=True,
            persistable=True,
            save=lambda: calls.append(1) or True,
            review_type="code",
        )
        assert outcome == SaveOutcome.SUPPRESSED
        assert calls == []

    def test_not_persistable_does_not_attempt(self) -> None:
        calls: list[int] = []
        outcome = _resolve_save_outcome(
            no_save=False,
            persistable=False,
            save=lambda: calls.append(1) or True,
            review_type="code",
        )
        assert outcome == SaveOutcome.NOT_PERSISTABLE
        assert calls == []

    def test_successful_write_is_saved(self) -> None:
        outcome = _resolve_save_outcome(
            no_save=False, persistable=True, save=lambda: True, review_type="code"
        )
        assert outcome == SaveOutcome.SAVED

    def test_failed_write_is_unsaved(self) -> None:
        outcome = _resolve_save_outcome(
            no_save=False, persistable=True, save=lambda: False, review_type="code"
        )
        assert outcome == SaveOutcome.UNSAVED

    @pytest.mark.parametrize(
        ("left", "right", "expected"),
        [
            (SaveOutcome.SAVED, SaveOutcome.UNSAVED, SaveOutcome.UNSAVED),
            (SaveOutcome.UNSAVED, SaveOutcome.SAVED, SaveOutcome.UNSAVED),
            (SaveOutcome.SAVED, SaveOutcome.SUPPRESSED, SaveOutcome.SAVED),
            (SaveOutcome.NOT_PERSISTABLE, SaveOutcome.SAVED, SaveOutcome.NOT_PERSISTABLE),
        ],
    )
    def test_worst_outcome_keeps_the_more_serious(
        self, left: SaveOutcome, right: SaveOutcome, expected: SaveOutcome
    ) -> None:
        """A multi-part tasks review reports the worst thing that happened."""
        assert _worst_outcome(left, right) == expected


class TestNotPersistableAcrossSubcommands:
    """No slice identifier: exit on verdict, but warn — both halves matter.

    Exit 0 alone was the bug's symptom; a silent exit 0 is what let an
    unwritten review look like a successful one.
    """

    @pytest.mark.parametrize("subcommand", SUBCOMMANDS)
    def test_exits_on_verdict_and_warns(
        self,
        subcommand: str,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
        docs: tuple[str, str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level("WARNING", logger="squadron.cli.commands.review"):
            result = cli_runner.invoke(app, _argv(subcommand, docs))

        assert result.exit_code == 0, result.output
        warnings = [
            r for r in caplog.records if r.levelname == "WARNING" and "not saved" in r.getMessage()
        ]
        assert warnings, "a not-persistable review must be reported, not silently dropped"

    @pytest.mark.parametrize("subcommand", SUBCOMMANDS)
    def test_no_save_is_quiet(
        self,
        subcommand: str,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
        docs: tuple[str, str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """--no-save is a deliberate choice, so it earns no warning."""
        with caplog.at_level("WARNING", logger="squadron.cli.commands.review"):
            result = cli_runner.invoke(app, [*_argv(subcommand, docs), "--no-save"])

        assert result.exit_code == 0, result.output
        warnings = [
            r for r in caplog.records if r.levelname == "WARNING" and "not saved" in r.getMessage()
        ]
        assert warnings == []


class TestFailedSaveExitsOne:
    """An attempted write that failed exits 1 regardless of a PASS verdict."""

    @pytest.mark.parametrize("subcommand", SUBCOMMANDS)
    def test_oserror_on_save_exits_one(
        self,
        subcommand: str,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
        docs: tuple[str, str],
        tmp_path: Path,
    ) -> None:
        slice_info = {
            "index": 916,
            "name": "Probe",
            "slice_name": "probe",
            "design_file": None,
            "task_files": [str(tmp_path / "916-tasks.probe.md")],
            "arch_file": None,
            "project": "squadron",
        }
        Path(slice_info["task_files"][0]).write_text("# tasks\n")

        if subcommand == "arch":
            argv = ["review", "arch", "916"]
        elif subcommand == "code":
            argv = ["review", "code", "916", "--files", "**/*"]
        else:
            argv = ["review", subcommand, "916", "--against", docs[1]]

        with (
            patch(
                "squadron.cli.commands.review._resolve_slice_number",
                return_value=slice_info,
            ),
            patch(
                "squadron.cli.commands.review.resolve_slice_info",
                return_value=slice_info,
            ),
            patch(
                "squadron.cli.commands.review.save_review_result",
                side_effect=OSError("read-only filesystem"),
            ),
            patch(
                "squadron.cli.commands.review.resolve_slice_diff_range",
                return_value="HEAD~1...HEAD",
            ),
            patch(
                "squadron.cli.commands.review.extract_diff_paths",
                return_value=["app.py"],
            ),
            patch(
                "squadron.cli.commands.review._resolve_arch_file",
                return_value=docs[0],
            ),
        ):
            result = cli_runner.invoke(app, argv)

        assert result.exit_code == 1, result.output
