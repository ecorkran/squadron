"""``slice_case_build`` end to end on the ``slice_project`` fixture (slice 426, Task 23).

Real sandboxes, real git, real uv installs and real pytest runs; nothing runs against
squadron's own history and no model is called. All ``network`` tests: they install the
fixture project.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadron.benchmark.adapter import SandboxContext, SuiteRun, SuiteSelection
from squadron.benchmark.python_adapter import PythonBenchmarkAdapter
from squadron.benchmark.python_fairness import PythonFixCaseAdapter
from squadron.benchmark.sandbox import BenchmarkSandbox
from squadron.benchmark.slice_case_build import SliceBuildDeps, SliceBuildResult, build_slice_cases
from squadron.benchmark.slice_qualify_types import SliceQualifyDeps
from squadron.benchmark.slice_yield import build_slice_yield
from squadron.config.keys import BENCHMARK_QUALIFICATION_REPEATS_KEY
from squadron.config.manager import get_positive_int_config
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import BenchmarkCase, CaseKind, QualificationOutcome
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.slice_case_models import SliceCandidateRejection
from squadron.metrology.slice_case_store import SliceCaseRecordStore
from squadron.metrology.slice_range_models import SliceRanges
from squadron.metrology.store import MetrologyStore
from tests.benchmark.slice_repos import (
    CODE_SLICE_INDEX,
    DOCS_SLICE_INDEX,
    SliceProjectRepos,
    landing_of,
    slice_project_history,
    tasks_path,
)

pytestmark = pytest.mark.network

PROJECT = ProjectId(value="e2e-slice-project", source=ProjectIdSource.RECORDED)
SET_NAME = "e2e-slices"


class CountingSuites:
    """Wraps the real suite runner and counts the suites that ran."""

    def __init__(self) -> None:
        self._inner = PythonBenchmarkAdapter()
        self.calls = 0

    def run_suite(self, ctx: SandboxContext, selection: SuiteSelection) -> SuiteRun:
        self.calls += 1
        return self._inner.run_suite(ctx, selection)


class RecordedRanges:
    """The ``slice_ranges`` record ``sq metrology slice-ranges`` would have stored."""

    def __init__(self, history: SliceProjectRepos) -> None:
        self._ranges = SliceRanges(
            record_id="sliceranges-e2e",
            project_id=PROJECT,
            slices={
                history.code.index: [landing_of(history.code)],
                history.docs.index: [landing_of(history.docs)],
            },
        )

    def get_slice_ranges(self, project_id: ProjectId) -> SliceRanges | None:
        return self._ranges


class Setup:
    def __init__(self, tmp_path: Path) -> None:
        self.history = slice_project_history(tmp_path / "history")
        self.suites = CountingSuites()
        self.records = BenchmarkRecordStore(MetrologyStore(store_dir=tmp_path / "store"))
        runner = SubprocessRunner()
        counter = 0
        repo = self.history.repo

        def factory(start_sha: str) -> BenchmarkSandbox:
            nonlocal counter
            counter += 1
            return BenchmarkSandbox(
                start_sha=start_sha,
                sandbox_id=f"e2e-slice-{counter}",
                repo_root=repo,
                runner=runner,
                adapter=PythonBenchmarkAdapter(),
                harness_env=dict(os.environ),
                install_timeout_s=900,
                suite_timeout_s=300,
                root=tmp_path / "sandboxes",
            )

        qualify = SliceQualifyDeps(
            project_id=PROJECT,
            repo=repo,
            runner=runner,
            qualifications=SliceCaseRecordStore(self.records),
            cases=self.records,
            sandbox_factory=factory,
            adapter=PythonFixCaseAdapter(),
            suite_runner=self.suites,
            repeats=get_positive_int_config(BENCHMARK_QUALIFICATION_REPEATS_KEY, cwd=str(repo)),
            git_timeout_s=60,
            clock=lambda: datetime.now(UTC),
        )
        self.deps = SliceBuildDeps(
            qualify=qualify, ranges=RecordedRanges(self.history), case_sets=self.records
        )

    def build(self) -> SliceBuildResult:
        return build_slice_cases(self.history.repo, SET_NAME, self.deps, lambda line: None)

    def case_of(self, result: SliceBuildResult) -> BenchmarkCase:
        assert result.case_set is not None
        (case_id,) = result.case_set.case_ids
        case = self.records.get_case(case_id)
        assert case is not None
        return case


def test_the_code_slice_qualifies_and_the_docs_slice_is_rejected(tmp_path: Path) -> None:
    setup = Setup(tmp_path)

    result = setup.build()

    code, docs = setup.history.code, setup.history.docs
    assert [line.split()[1] for line in result.lines] == [str(code.index), str(docs.index)]
    assert result.lines[0].startswith(f"slice {CODE_SLICE_INDEX} qualified case-")
    assert result.lines[1].startswith(
        f"slice {DOCS_SLICE_INDEX} {SliceCandidateRejection.NO_CODE_CHANGE.value}:"
    )
    assert result.stopped_at is None
    assert result.case_set is not None
    assert (result.case_set.name, result.case_set.version) == (SET_NAME, 1)

    case = setup.case_of(result)
    assert case.kind is CaseKind.SLICE
    assert case.start_sha == code.landing.fork
    assert case.reference_sha == code.landing.tip
    assert case.task_text.index("# Design 511") < case.task_text.index("- [ ] task 511")
    assert "task 512" not in case.task_text
    assert case.hidden_tests == ()


def test_the_fork_task_text_is_the_file_as_of_the_fork(tmp_path: Path) -> None:
    """The task file changes after the fork in the docs slice; the code slice's text is
    the committed content, frontmatter included."""
    setup = Setup(tmp_path)
    case = setup.case_of(setup.build())
    expected = (setup.history.repo / tasks_path(CODE_SLICE_INDEX)).read_text()
    assert expected in case.task_text
    assert f"## File: {tasks_path(CODE_SLICE_INDEX)}" in case.task_text


def test_the_regression_selection_is_the_forks_unchanged_tests(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    case = setup.case_of(setup.build())
    qualification = setup.deps.qualify.qualifications.get_slice_qualification(
        PROJECT, CODE_SLICE_INDEX, setup.history.code.landing.after, None
    )
    assert qualification is None, "a qualified record is keyed on the fork environment"
    stored = [
        q
        for q in setup.deps.qualify.qualifications.list_slice_qualifications(PROJECT)
        if q.slice_index == CODE_SLICE_INDEX
    ]
    assert len(stored) == 1
    assert stored[0].outcome is QualificationOutcome.QUALIFIED
    assert stored[0].case_id == case.case_id
    assert stored[0].start_environment is not None
    assert stored[0].reference_environment is not None
    assert "3 regression nodes" in stored[0].detail
    assert case.excluded_tests == ()


def test_a_second_build_reuses_the_stored_qualification(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    first = setup.build()
    suites_after_first = setup.suites.calls
    assert suites_after_first > 0

    second = setup.build()

    assert setup.suites.calls == suites_after_first, "a reused candidate runs no suite"
    assert setup.case_of(second).case_id == setup.case_of(first).case_id
    assert second.case_set is not None and second.case_set.version == 1


def test_the_yield_rows_count_both_slices(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    setup.build()

    (row,) = build_slice_yield(setup.deps.qualify.qualifications.list_slice_qualifications(PROJECT))

    assert row.project == PROJECT.value
    assert (row.candidates, row.qualified, row.harness_errors) == (2, 1, 0)
    assert dict(row.rejected) == {SliceCandidateRejection.NO_CODE_CHANGE: 1}
