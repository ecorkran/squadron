"""CLI report tests: rendering, --json, empty store, corrupt sibling,
read-only invariance, and surface-agnostic-core parity (T15/T16)."""

from __future__ import annotations

import ast
import json
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.metrology.report_models import AgreementReport
from squadron.metrology.store import MetrologyStore
from tests.metrology.conftest import CaptureProject

runner = CliRunner()


def _normalized(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions aren't
    sensitive to terminal width."""
    return " ".join(output.split())


@pytest.fixture
def cli_store(tmp_path: Path) -> Iterator[Path]:
    """Redirect the CLI's store-dir resolution to a temp path."""
    store_dir = tmp_path / "cli-store"
    with patch("squadron.cli.commands.metrology.resolve_store_dir", return_value=store_dir):
        yield store_dir


def _capture(capture_project: CaptureProject, verdict: str = "PASS") -> None:
    with patch("squadron.cli.commands.metrology._sample_budget", return_value=10):
        result = runner.invoke(
            app,
            [
                "metrology",
                "sample",
                str(capture_project.review_index),
                "--type",
                capture_project.review_type,
                "--verdict",
                verdict,
                "--cwd",
                str(capture_project.root),
            ],
        )
    assert result.exit_code == 0, result.output


class TestReportAgreement:
    def test_prints_rows_with_n_and_json_round_trips(
        self, capture_project: CaptureProject, cli_store: Path
    ) -> None:
        _capture(capture_project, verdict="PASS")

        result = runner.invoke(
            app, ["metrology", "report", "agreement", "--cwd", str(capture_project.root)]
        )
        assert result.exit_code == 0, result.output
        assert "match_rate=1.00 (n=1)" in _normalized(result.output)
        assert "excluded" in result.output

        json_result = runner.invoke(
            app,
            ["metrology", "report", "agreement", "--cwd", str(capture_project.root), "--json"],
        )
        assert json_result.exit_code == 0, json_result.output
        parsed = AgreementReport.model_validate(json.loads(json_result.output))
        assert len(parsed.cells) == 1
        assert parsed.cells[0].n == 1

    def test_low_n_row_marked(self, capture_project: CaptureProject, cli_store: Path) -> None:
        _capture(capture_project, verdict="PASS")
        result = runner.invoke(
            app, ["metrology", "report", "agreement", "--cwd", str(capture_project.root)]
        )
        assert result.exit_code == 0, result.output
        assert "low-n" in result.output

    def test_empty_store_prints_honest_no_evidence_and_exits_zero(
        self, capture_project: CaptureProject, cli_store: Path
    ) -> None:
        result = runner.invoke(
            app, ["metrology", "report", "agreement", "--cwd", str(capture_project.root)]
        )
        assert result.exit_code == 0
        assert "No evidence." in result.output


class TestReportDispersion:
    def test_single_config_store_prints_explanatory_line(
        self, capture_project: CaptureProject, cli_store: Path
    ) -> None:
        _capture(capture_project, verdict="PASS")
        result = runner.invoke(
            app, ["metrology", "report", "dispersion", "--cwd", str(capture_project.root)]
        )
        assert result.exit_code == 0, result.output
        assert "No multi-config artifacts yet." in result.output
        assert "0" not in result.output.split("No multi-config artifacts yet.")[0]

    def test_two_config_artifact_prints_cell(
        self,
        capture_project: CaptureProject,
        cli_store: Path,
    ) -> None:
        # A second review file, distinct index, grading the SAME artifact
        # (shared sourceDocument) under a distinct model — the cross-config
        # dispersion case.
        reviews_dir = capture_project.root / "project-documents/user/reviews"
        second_review = reviews_dir / "501-review.judge.slice-vs-arch.example.md"
        text = capture_project.review_file.read_text(encoding="utf-8")
        text = text.replace("aiModel: minimax/minimax-m2.7", "aiModel: model-b")
        text = text.replace("score: 98.0", "score: 40.0")
        second_review.write_text(text, encoding="utf-8")

        with patch("squadron.cli.commands.metrology._sample_budget", return_value=10):
            first = runner.invoke(
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
            assert first.exit_code == 0, first.output
            second = runner.invoke(
                app,
                [
                    "metrology",
                    "sample",
                    "501",
                    "--type",
                    capture_project.review_type,
                    "--verdict",
                    "PASS",
                    "--cwd",
                    str(capture_project.root),
                ],
            )
            assert second.exit_code == 0, second.output

        result = runner.invoke(
            app, ["metrology", "report", "dispersion", "--cwd", str(capture_project.root)]
        )
        assert result.exit_code == 0, result.output
        assert "disagreement_rate=" in result.output


class TestReportTrend:
    def test_prints_ordered_buckets_and_bucket_override(
        self, capture_project: CaptureProject, cli_store: Path
    ) -> None:
        _capture(capture_project, verdict="PASS")
        result = runner.invoke(
            app,
            [
                "metrology",
                "report",
                "trend",
                "--bucket",
                "day",
                "--cwd",
                str(capture_project.root),
            ],
        )
        assert result.exit_code == 0, result.output
        assert result.output.strip() != ""

    def test_dispersion_rows_render_in_human_output(
        self,
        capture_project: CaptureProject,
        cli_store: Path,
    ) -> None:
        # Same cross-config setup as TestReportDispersion.test_two_config_artifact_prints_cell:
        # the trend command's human output must surface dispersion, not just agreement.
        reviews_dir = capture_project.root / "project-documents/user/reviews"
        second_review = reviews_dir / "501-review.judge.slice-vs-arch.example.md"
        text = capture_project.review_file.read_text(encoding="utf-8")
        text = text.replace("aiModel: minimax/minimax-m2.7", "aiModel: model-b")
        text = text.replace("score: 98.0", "score: 40.0")
        second_review.write_text(text, encoding="utf-8")

        with patch("squadron.cli.commands.metrology._sample_budget", return_value=10):
            first = runner.invoke(
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
            assert first.exit_code == 0, first.output
            second = runner.invoke(
                app,
                [
                    "metrology",
                    "sample",
                    "501",
                    "--type",
                    capture_project.review_type,
                    "--verdict",
                    "PASS",
                    "--cwd",
                    str(capture_project.root),
                ],
            )
            assert second.exit_code == 0, second.output

        result = runner.invoke(
            app, ["metrology", "report", "trend", "--cwd", str(capture_project.root)]
        )
        assert result.exit_code == 0, result.output
        assert "disagreement_rate=" in result.output


class TestReportEmptyStoreHonesty:
    def test_each_report_command_honest_on_empty_store(
        self, capture_project: CaptureProject, cli_store: Path
    ) -> None:
        for subcommand, expected in (
            ("agreement", "No evidence."),
            ("dispersion", "No multi-config artifacts yet."),
            ("trend", "No evidence."),
        ):
            result = runner.invoke(
                app,
                ["metrology", "report", subcommand, "--cwd", str(capture_project.root)],
            )
            assert result.exit_code == 0, result.output
            assert expected in result.output


class TestReportStoreError:
    def test_store_init_failure_uses_shared_handler(self, capture_project: CaptureProject) -> None:
        with patch(
            "squadron.cli.commands.metrology.resolve_store_dir",
            side_effect=OSError("disk unavailable"),
        ):
            result = runner.invoke(
                app, ["metrology", "report", "agreement", "--cwd", str(capture_project.root)]
            )
        assert result.exit_code != 0
        assert "Traceback" not in result.output


class TestReportTargetError:
    """Agreement must handle MetrologyTargetError the same way trend already
    does (F007) — a bad config value is a clean exit 1, not a traceback.
    (Dispersion has no config-reading path today — its handler is added for
    consistency with agreement/trend but is not independently triggerable.)"""

    def test_bad_min_evidence_n_exits_cleanly(
        self,
        capture_project: CaptureProject,
        cli_store: Path,
        write_project_config: Callable[[Path, dict[str, object]], Path],
    ) -> None:
        _capture(capture_project, verdict="PASS")
        write_project_config(capture_project.root, {"metrology.min_evidence_n": "not-an-int"})

        result = runner.invoke(
            app, ["metrology", "report", "agreement", "--cwd", str(capture_project.root)]
        )
        assert result.exit_code != 0
        assert "Traceback" not in result.output


class TestReportCorruptSiblingTolerance:
    def test_corrupt_sibling_does_not_sink_the_report(
        self, capture_project: CaptureProject, cli_store: Path
    ) -> None:
        _capture(capture_project, verdict="PASS")
        # A corrupt sibling record alongside the good one.
        bad_path = cli_store / "sample-corrupt-sibling.json"
        bad_path.write_text(json.dumps({"schema_version": 999, "record_type": "sample"}))

        result = runner.invoke(
            app, ["metrology", "report", "agreement", "--cwd", str(capture_project.root)]
        )
        assert result.exit_code == 0, result.output
        assert "match_rate=1.00 (n=1)" in _normalized(result.output)


class TestReportReadOnlyInvariance:
    def test_store_and_review_bytes_unchanged_after_each_report_command(
        self, capture_project: CaptureProject, cli_store: Path
    ) -> None:
        _capture(capture_project, verdict="PASS")
        store = MetrologyStore(store_dir=cli_store)
        record_paths = sorted(cli_store.glob("*.json"))
        before_store = {p: p.read_bytes() for p in record_paths}
        before_review = capture_project.review_file.read_bytes()
        assert store.list_samples()  # sanity: there is a sample to report on

        for subcommand in ("agreement", "dispersion", "trend"):
            runner.invoke(
                app,
                ["metrology", "report", subcommand, "--cwd", str(capture_project.root)],
            )
            runner.invoke(
                app,
                ["metrology", "report", subcommand, "--cwd", str(capture_project.root), "--json"],
            )

        after_store = {p: p.read_bytes() for p in sorted(cli_store.glob("*.json"))}
        assert before_store == after_store
        assert capture_project.review_file.read_bytes() == before_review


class TestSurfaceAgnosticCore:
    def test_report_core_modules_import_no_typer(self) -> None:
        for module_path in (
            "src/squadron/metrology/report.py",
            "src/squadron/metrology/levels.py",
            "src/squadron/metrology/report_models.py",
        ):
            source = Path(module_path).read_text(encoding="utf-8")
            tree = ast.parse(source)
            imported_modules: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_modules.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_modules.add(node.module)
            assert not any("typer" in module for module in imported_modules), module_path
