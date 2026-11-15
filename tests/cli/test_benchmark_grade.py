"""``sq benchmark grade``: options, refusals, output and exit codes (slice 425 Task 42).

The command runs against doubles through its one seam (``make_grade_command``), so no model,
sandbox or git is involved beyond a throwaway ``git init`` for ``--repo``.
"""

from __future__ import annotations

import subprocess
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from squadron.benchmark.grade_budget import GradeCapReached, ReviewBudget
from squadron.benchmark.grade_deps import GradeDeps
from squadron.benchmark.grade_plan import GradePlan
from squadron.benchmark.grade_services import GradeServices
from squadron.benchmark.run_services import KeptSandbox
from squadron.cli.commands.benchmark_grade import make_grade_command
from squadron.config.keys import (
    BENCHMARK_GRADING_REVIEW_MODEL_KEY,
    BENCHMARK_REVIEW_FLOOR_RUNS_KEY,
    BENCHMARK_REVIEW_TIMEOUT_KEY,
    BENCHMARK_TARGET_PASS_RATE_DIFFERENCE_KEY,
)
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.grade_models import ReviewerRef
from squadron.metrology.grade_store import GradeRecordStore
from squadron.metrology.store import MetrologyStore
from squadron.models.aliases import UnknownModelAliasError
from tests.benchmark.grade_support import World, make_world
from tests.benchmark.grading_fixtures import GradingRepo, build_grading_repo
from tests.benchmark.test_grade_identity import make_reviewer
from tests.benchmark.test_grade_plan import make_replay, make_run
from tests.benchmark.test_grade_runner import Calls, FakeGrader
from tests.metrology.test_benchmark_store import make_case

NOW = datetime(2026, 11, 14, 12, tzinfo=UTC)
BENCHMARK = "bench-3f9c"


class Harness:
    """Fake services over a real record store, seeded with one benchmark of two cases."""

    def __init__(self, tmp_path: Path, repo: GradingRepo) -> None:
        self.records = BenchmarkRecordStore(MetrologyStore(store_dir=tmp_path / "store"))
        self.grade_store = GradeRecordStore(self.records)
        self.cases = [make_case(task=f"issue {n}") for n in range(2)]
        for case in self.cases:
            self.records.write_case(case)
        self.records.write_case_set("fixes", [case.case_id for case in self.cases])
        self.records.write_run(make_run(BENCHMARK))
        for case in self.cases:
            record_id, replay = make_replay(case, 0, benchmark_id=BENCHMARK)
            self.records.write_replay(record_id, replay)
        self.world: World = make_world(tmp_path / "world", repo)
        self.config: dict[str, object] = {
            BENCHMARK_GRADING_REVIEW_MODEL_KEY: "gpt-review",
            BENCHMARK_REVIEW_TIMEOUT_KEY: 120.0,
            BENCHMARK_REVIEW_FLOOR_RUNS_KEY: 3,
            BENCHMARK_TARGET_PASS_RATE_DIFFERENCE_KEY: 0.2,
        }
        self.calls: Calls = []
        self.cap_on_call: int | None = None
        self.kept: list[KeptSandbox] = []
        self.project = "proj"
        self.lock_root = tmp_path / "locks"
        self.repo_dir = tmp_path / "repo"
        self.repo_dir.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo_dir)], check=True)

    def grader(self) -> FakeGrader:
        def on_call(count: int) -> None:
            if self.cap_on_call is not None and count == self.cap_on_call:
                raise GradeCapReached(1.0, 1.0)

        return FakeGrader(self.world, self.calls, on_call=on_call)

    def resolve_reviewer(self, alias: str) -> ReviewerRef:
        if alias == "no-such-alias":
            raise UnknownModelAliasError(alias, [])
        return make_reviewer(alias=alias)

    def make_deps(self, budget: ReviewBudget, plan: GradePlan, repos: Any, keep: bool) -> GradeDeps:
        return replace(
            self.world.deps, budget=budget, grader=plan.grader, store=self.grade_store, keep=keep
        )

    def services(self, repo_root: Path) -> GradeServices:
        return GradeServices(
            repo_root=repo_root,
            store=self.records,
            grade_store=self.grade_store,
            process_runner=SubprocessRunner(),
            lock_root=self.lock_root,
            sweep=lambda runner, root: None,
            clock=lambda: NOW,
            read_config=self.config.get,
            resolve_reviewer=self.resolve_reviewer,
            project_id_of=lambda path: self.project,
            make_deps=self.make_deps,
            grade=self.grader(),
            kept_sandboxes=lambda: list(self.kept),
        )

    def invoke(self, *args: str, benchmark: str = BENCHMARK) -> Any:
        app = typer.Typer()
        app.command("grade")(make_grade_command(self.services))
        app.callback()(lambda: None)
        return CliRunner().invoke(app, ["grade", benchmark, "--repo", str(self.repo_dir), *args])


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    return Harness(tmp_path, build_grading_repo(tmp_path / "grading-repo"))


CAP = ["--max-cost", "50", "--review-cost", "0.25"]


class TestRefusals:
    def test_no_run_cap_names_the_flag(self, harness: Harness) -> None:
        result = harness.invoke("--review-cost", "0.25")
        assert result.exit_code == 1
        assert "Error:" in result.output and "--max-cost" in result.output

    def test_no_reviewer_names_both_sources(self, harness: Harness) -> None:
        harness.config.pop(BENCHMARK_GRADING_REVIEW_MODEL_KEY)
        result = harness.invoke(*CAP)
        assert result.exit_code == 1
        assert "--review-model" in result.output
        assert BENCHMARK_GRADING_REVIEW_MODEL_KEY in result.output

    def test_an_unset_review_timeout_names_the_key(self, harness: Harness) -> None:
        harness.config.pop(BENCHMARK_REVIEW_TIMEOUT_KEY)
        result = harness.invoke(*CAP)
        assert result.exit_code == 1
        assert BENCHMARK_REVIEW_TIMEOUT_KEY in result.output

    def test_a_case_project_with_no_matching_repo_names_the_project(self, harness: Harness) -> None:
        harness.project = "somewhere-else"
        result = harness.invoke(*CAP)
        assert result.exit_code == 1
        assert "proj" in result.output and "--repo" in result.output

    def test_no_per_review_figure_names_the_flag(self, harness: Harness) -> None:
        result = harness.invoke("--max-cost", "50")
        assert result.exit_code == 1
        assert "--review-cost" in result.output

    def test_an_unknown_benchmark_id_names_it(self, harness: Harness) -> None:
        result = harness.invoke(*CAP, benchmark="bench-nope")
        assert result.exit_code == 1
        assert "bench-nope" in result.output

    def test_an_unknown_review_alias_is_refused_naming_it(self, harness: Harness) -> None:
        result = harness.invoke(*CAP, "--review-model", "no-such-alias")
        assert result.exit_code == 1
        assert "no-such-alias" in result.output

    def test_a_floor_run_count_below_two_names_the_key(self, harness: Harness) -> None:
        harness.config[BENCHMARK_REVIEW_FLOOR_RUNS_KEY] = 1
        result = harness.invoke(*CAP)
        assert result.exit_code == 1
        assert BENCHMARK_REVIEW_FLOOR_RUNS_KEY in result.output

    def test_a_refusal_prints_no_stack_trace_and_grades_nothing(self, harness: Harness) -> None:
        result = harness.invoke("--review-cost", "0.25")
        assert "Traceback" not in result.output
        assert harness.calls == []


class TestRun:
    def test_the_bound_prints_first(self, harness: Harness) -> None:
        result = harness.invoke(*CAP)
        assert result.exit_code == 0, result.output
        lines = result.output.splitlines()
        assert lines[0].startswith(f"grade {BENCHMARK}")
        assert lines[1].startswith("references 2 × 3 reviews + replays 2 × 1 review = 8 reviews")
        assert "bound: 8 × $0.25 (--review-cost) = $2.00, under run cap $50.00" in result.output

    def test_one_line_per_subject_then_the_summary(self, harness: Harness) -> None:
        result = harness.invoke(*CAP)
        lines = result.output.splitlines()
        assert sum(line.startswith("reference ") and line.endswith(" pass") for line in lines) == 2
        assert sum(line.endswith(" s0 pass") for line in lines) == 2
        assert any(
            line.startswith("graded 2 references, 2 replays: 4 passed, 0 failed") for line in lines
        )
        assert any(line.startswith("spent $") for line in lines)

    def test_a_cap_stop_exits_2(self, harness: Harness) -> None:
        harness.cap_on_call = 2
        result = harness.invoke(*CAP)
        assert result.exit_code == 2
        assert "stopped at the run cap" in result.output

    def test_completion_exits_0(self, harness: Harness) -> None:
        assert harness.invoke(*CAP).exit_code == 0

    def test_keep_prints_the_kept_path_and_the_hidden_tests_notice(self, harness: Harness) -> None:
        harness.kept = [
            KeptSandbox(
                tree=Path("/tmp/kept-tree"),
                home=Path("/tmp/kept-home"),
                output_dir=Path("/tmp/kept-out"),
            )
        ]
        result = harness.invoke(*CAP, "--keep")
        assert "kept: /tmp/kept-tree (holds the reference's hidden tests" in result.output
        assert "kept:" not in harness.invoke(*CAP).output

    def test_case_limits_the_plan(self, harness: Harness) -> None:
        only = harness.cases[0].case_id
        result = harness.invoke(*CAP, "--case", only)
        assert result.exit_code == 0, result.output
        assert "references 1 × 3 reviews + replays 1 × 1 review = 4 reviews" in result.output
        assert all(only in detail for kind, detail in harness.calls if kind == "reference")

    def test_the_command_lists_every_option_in_help(self) -> None:
        app = typer.Typer()
        app.command("grade")(make_grade_command(lambda root: None))  # type: ignore[arg-type,return-value]
        app.callback()(lambda: None)
        text = CliRunner().invoke(app, ["grade", "--help"], terminal_width=200).output
        for option in (
            "--max-cost",
            "--review-model",
            "--review-cost",
            "--repo",
            "--case",
            "--retry-harness",
            "--keep",
        ):
            assert option in text
