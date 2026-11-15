"""``sq benchmark report``: text, JSON and refusals (slice 425 Task 43)."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from squadron.benchmark.bench_report_render import render_json, render_text
from squadron.benchmark.grade_services import GradeServices
from squadron.benchmark.report_models import BenchmarkReport
from squadron.cli.commands.benchmark_grade import make_report_command
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.store import MetrologyStore
from tests.benchmark.report_support import ReportWorld, fixture_world
from tests.benchmark.test_bench_report_review import estimate_for

BENCHMARK = "bench-3f9c"


class Harness:
    def __init__(self, tmp_path: Path, world: ReportWorld, *, persist_grades: bool = True) -> None:
        self.world = world
        self.records = BenchmarkRecordStore(MetrologyStore(store_dir=tmp_path / "store"))
        for case in world.cases.values():
            self.records.write_case(case)
        self.records.write_case_set(world.run.case_set, list(world.cases))
        self.records.write_run(world.run)
        for record_id, replay in world.replays:
            self.records.write_replay(record_id, replay)
        if persist_grades:
            for grade in world.grades:
                world.store.write_grade(grade)
        self.repo_dir = tmp_path / "repo"
        self.repo_dir.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo_dir)], check=True)

    def services(self, repo_root: Path) -> GradeServices:
        def unused(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("the report command uses neither grading nor config")

        return GradeServices(
            repo_root=repo_root,
            store=self.records,
            grade_store=self.world.store,
            process_runner=SubprocessRunner(),
            lock_root=self.repo_dir,
            sweep=unused,
            clock=lambda: datetime(2026, 11, 14, tzinfo=UTC),
            read_config=unused,
            resolve_reviewer=unused,
            project_id_of=unused,
            make_deps=unused,
            grade=unused,
            kept_sandboxes=unused,
        )

    def invoke(self, *args: str, benchmark: str = BENCHMARK) -> Any:
        app = typer.Typer()
        app.command("report")(make_report_command(self.services))
        app.callback()(lambda: None)
        return CliRunner().invoke(app, ["report", benchmark, "--repo", str(self.repo_dir), *args])


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    return Harness(tmp_path, fixture_world(tmp_path / "world"))


def test_the_text_output_is_the_rendered_report(harness: Harness) -> None:
    result = harness.invoke()
    assert result.exit_code == 0, result.output
    assert result.output.strip() == render_text(harness.world.build())
    assert "objective grade" in result.output and "opus" in result.output


def test_the_json_output_parses_into_the_report_model(harness: Harness) -> None:
    result = harness.invoke("--json")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["benchmark_id"] == BENCHMARK
    assert BenchmarkReport.model_validate_json(result.output) == harness.world.build()
    assert result.output.strip() == render_json(harness.world.build())


def test_a_stored_estimate_for_this_benchmark_is_shown(tmp_path: Path) -> None:
    world = fixture_world(tmp_path / "world")
    harness = Harness(tmp_path, world)
    world.store.write_estimate(estimate_for(world))
    assert "sample count (measured, k=3, n=10)" in harness.invoke().output


def test_an_estimate_of_another_benchmark_is_not_shown(tmp_path: Path) -> None:
    world = fixture_world(tmp_path / "world")
    harness = Harness(tmp_path, world)
    other = estimate_for(world).model_copy(update={"benchmark_id": "bench-other"})
    world.store.write_estimate(other)
    assert "sample count" not in harness.invoke().output


def test_an_unknown_benchmark_id_exits_1_naming_it(harness: Harness) -> None:
    result = harness.invoke(benchmark="bench-nope")
    assert result.exit_code == 1
    assert "bench-nope" in result.output
    assert "Traceback" not in result.output


def test_a_benchmark_with_no_grades_exits_1_saying_so(tmp_path: Path) -> None:
    harness = Harness(tmp_path, fixture_world(tmp_path / "world"), persist_grades=False)
    result = harness.invoke()
    assert result.exit_code == 1
    assert "has no grades" in result.output and "sq benchmark grade" in result.output
