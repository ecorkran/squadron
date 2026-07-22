"""CLI capture and failure-mode tests (T14/T15).

One assertion per Failure Modes table row, plus the happy-path capture/list and
the budget ceiling. The store dir is patched to a tmp path so tests never touch
a developer's real ~/.config/squadron/metrology/.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.store import MetrologyStore
from tests.metrology.conftest import CaptureProject

runner = CliRunner()


@pytest.fixture
def cli_store(tmp_path: Path) -> Iterator[Path]:
    """Redirect the CLI's store-dir resolution to a temp path."""
    store_dir = tmp_path / "cli-store"
    with patch("squadron.cli.commands.metrology.resolve_store_dir", return_value=store_dir):
        yield store_dir


def _budget(limit: int) -> AbstractContextManager[object]:
    """Patch the CLI's sample-budget read to a fixed value."""
    return patch("squadron.cli.commands.metrology._sample_budget", return_value=limit)


class TestCaptureAndList:
    def test_sample_records_and_prints_sample_id(
        self, capture_project: CaptureProject, cli_store: Path
    ) -> None:
        with _budget(10):
            result = runner.invoke(
                app,
                [
                    "metrology",
                    "sample",
                    str(capture_project.review_index),
                    "--type",
                    capture_project.review_type,
                    "--verdict",
                    "PASS",
                    "--cwd",
                    str(capture_project.root),
                ],
            )
        assert result.exit_code == 0, result.output
        assert "Recorded sample-" in result.output
        # The blind presentation must not leak the judge's actual score.
        assert "98.0" not in result.output
        assert len(MetrologyStore(store_dir=cli_store).list_samples()) == 1

    def test_list_shows_stored_record(self, capture_project: CaptureProject, cli_store: Path) -> None:
        with _budget(10):
            runner.invoke(
                app,
                [
                    "metrology",
                    "sample",
                    str(capture_project.review_index),
                    "--type",
                    capture_project.review_type,
                    "--verdict",
                    "CONCERNS",
                    "--cwd",
                    str(capture_project.root),
                ],
            )
        result = runner.invoke(app, ["metrology", "list", "--cwd", str(capture_project.root)])
        assert result.exit_code == 0
        assert "github.com/manta/capture-repo" in result.output
        assert "CONCERNS" in result.output


class TestBudgetExhausted:
    def test_reports_ceiling_and_exits_zero_writing_nothing(
        self, capture_project: CaptureProject, cli_store: Path
    ) -> None:
        args = [
            "metrology",
            "sample",
            str(capture_project.review_index),
            "--type",
            capture_project.review_type,
            "--verdict",
            "PASS",
            "--cwd",
            str(capture_project.root),
        ]
        with _budget(1):
            first = runner.invoke(app, args)
            assert first.exit_code == 0
            second = runner.invoke(app, args)
        assert second.exit_code == 0  # a ceiling, not an error
        assert "budget reached" in second.output.lower()
        # Only the first write landed.
        assert len(MetrologyStore(store_dir=cli_store).list_samples()) == 1


class TestBudgetConfig:
    """F001: budget honors project cwd and rejects a non-integer value."""

    def test_project_budget_read_with_cwd(
        self,
        capture_project: CaptureProject,
        cli_store: Path,
        write_project_config: Callable[[Path, dict[str, object]], Path],
    ) -> None:
        # Project-level budget of 1, read via --cwd (no _budget patch here).
        write_project_config(capture_project.root, {"metrology.sample_budget": 1})
        args = [
            "metrology",
            "sample",
            str(capture_project.review_index),
            "--type",
            capture_project.review_type,
            "--verdict",
            "PASS",
            "--cwd",
            str(capture_project.root),
        ]
        first = runner.invoke(app, args)
        assert first.exit_code == 0
        second = runner.invoke(app, args)
        assert second.exit_code == 0
        assert "budget reached" in second.output.lower()
        assert len(MetrologyStore(store_dir=cli_store).list_samples()) == 1

    def test_non_integer_budget_errors_not_silent_zero(
        self,
        capture_project: CaptureProject,
        cli_store: Path,
    ) -> None:
        # A non-int budget must fail explicitly, not silently disable capture.
        with patch("squadron.cli.commands.metrology.get_config", return_value="not-an-int"):
            result = runner.invoke(
                app,
                [
                    "metrology",
                    "sample",
                    str(capture_project.review_index),
                    "--type",
                    capture_project.review_type,
                    "--verdict",
                    "PASS",
                    "--cwd",
                    str(capture_project.root),
                ],
            )
        assert result.exit_code != 0
        assert "sample_budget must be an integer" in result.output
        assert not (cli_store.exists() and list(cli_store.glob("*.json")))


class TestFailureModes:
    """One assertion per Failure Modes table row (the rows T15 owns)."""

    def test_missing_target_errors(self, capture_project: CaptureProject, cli_store: Path) -> None:
        with _budget(10):
            result = runner.invoke(
                app,
                [
                    "metrology",
                    "sample",
                    "999",
                    "--type",
                    "slice",
                    "--verdict",
                    "PASS",
                    "--cwd",
                    str(capture_project.root),
                ],
            )
        assert result.exit_code != 0
        assert "No review result" in result.output

    def test_ambiguous_bare_index_names_candidates(
        self, capture_project: CaptureProject, cli_store: Path
    ) -> None:
        reviews_dir = capture_project.review_file.parent
        (reviews_dir / "500-review.code.example.md").write_text(
            "---\nreviewType: code\naiModel: m\nscore: 1.0\n---\n", encoding="utf-8"
        )
        with _budget(10):
            result = runner.invoke(
                app,
                [
                    "metrology",
                    "sample",
                    "500",
                    "--verdict",
                    "PASS",
                    "--cwd",
                    str(capture_project.root),
                ],
            )
        assert result.exit_code != 0
        assert "ambiguous" in result.output.lower()
        assert "code" in result.output and "judge.slice-vs-arch" in result.output

    def test_non_tty_without_verdict_errors_no_hang(
        self, capture_project: CaptureProject, cli_store: Path
    ) -> None:
        # CliRunner supplies a non-interactive stdin; without --verdict the
        # command must error rather than block on a prompt.
        with _budget(10):
            result = runner.invoke(
                app,
                [
                    "metrology",
                    "sample",
                    str(capture_project.review_index),
                    "--type",
                    capture_project.review_type,
                    "--cwd",
                    str(capture_project.root),
                ],
            )
        assert result.exit_code != 0
        assert "--verdict" in result.output

    def test_skip_records_nothing_exit_zero(
        self, capture_project: CaptureProject, cli_store: Path
    ) -> None:
        result = runner.invoke(
            app,
            [
                "metrology",
                "sample",
                str(capture_project.review_index),
                "--type",
                capture_project.review_type,
                "--skip",
                "--cwd",
                str(capture_project.root),
            ],
        )
        assert result.exit_code == 0
        assert "skipped" in result.output.lower()
        # Store dir may not even exist; certainly no record.
        if cli_store.exists():
            assert list(cli_store.glob("*.json")) == []

    def test_bad_verdict_value_errors_no_record(
        self, capture_project: CaptureProject, cli_store: Path
    ) -> None:
        with _budget(10):
            result = runner.invoke(
                app,
                [
                    "metrology",
                    "sample",
                    str(capture_project.review_index),
                    "--type",
                    capture_project.review_type,
                    "--verdict",
                    "MAYBE",
                    "--cwd",
                    str(capture_project.root),
                ],
            )
        assert result.exit_code != 0
        assert "invalid --verdict" in result.output.lower()
        assert not (cli_store.exists() and list(cli_store.glob("*.json")))

    def test_identity_absent_errors(self, repo_no_remote: Path, cli_store: Path) -> None:
        # A repo with no remote and no recorded id: build a minimal review so
        # target resolution succeeds and identity is the failing boundary.
        reviews_dir = repo_no_remote / "project-documents/user/reviews"
        reviews_dir.mkdir(parents=True, exist_ok=True)
        (reviews_dir / "500-review.slice.example.md").write_text(
            "---\nreviewType: slice\naiModel: m\nscore: 1.0\nsourceDocument: x.md\n---\n",
            encoding="utf-8",
        )
        with _budget(10):
            result = runner.invoke(
                app,
                [
                    "metrology",
                    "sample",
                    "500",
                    "--type",
                    "slice",
                    "--verdict",
                    "PASS",
                    "--cwd",
                    str(repo_no_remote),
                ],
            )
        assert result.exit_code != 0
        assert "metrology.project_id" in result.output

    def test_unwritable_store_errors_no_partial(
        self, capture_project: CaptureProject, tmp_path: Path
    ) -> None:
        store_dir = tmp_path / "ro-store"
        store_dir.mkdir()
        with patch("squadron.cli.commands.metrology.resolve_store_dir", return_value=store_dir):
            with (
                _budget(10),
                patch.object(Path, "rename", side_effect=OSError("read-only")),
            ):
                result = runner.invoke(
                    app,
                    [
                        "metrology",
                        "sample",
                        str(capture_project.review_index),
                        "--type",
                        capture_project.review_type,
                        "--verdict",
                        "PASS",
                        "--cwd",
                        str(capture_project.root),
                    ],
                )
        assert result.exit_code != 0
        assert "store error" in result.output.lower()
        assert list(store_dir.glob("*.json")) == []  # no partial record

    def test_list_handles_store_init_error(self, capture_project: CaptureProject) -> None:
        # F002: an unbuildable store must yield a formatted error + clean exit,
        # not a raw traceback.
        with patch(
            "squadron.cli.commands.metrology.resolve_store_dir",
            side_effect=MetrologyStoreError("store dir not creatable"),
        ):
            result = runner.invoke(app, ["metrology", "list", "--cwd", str(capture_project.root)])
        assert result.exit_code != 0
        assert "store error" in result.output.lower()
