"""Qualification end to end on real fixture history (slice 422 success criteria).

Each scenario is a two-commit repository built by ``fix_history``; the sandbox, the trace
plugin, the boundary resolver and the suite runs are real, and the issue host is scripted.
All ``network`` tests: they install the fixture project.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from squadron.benchmark import qualify_sandbox, qualify_types
from squadron.benchmark.adapter import SandboxContext, SuiteRun, SuiteSelection
from squadron.benchmark.fix_discovery import FixCandidate, discover
from squadron.benchmark.python_adapter import PythonBenchmarkAdapter
from squadron.benchmark.python_fairness import PythonFixCaseAdapter
from squadron.benchmark.qualify import qualify_candidate
from squadron.benchmark.qualify_sandbox import qualify_in_sandbox
from squadron.benchmark.qualify_types import QualifyDeps, QualifyResult
from squadron.benchmark.sandbox import BenchmarkSandbox
from squadron.codehost.github_cli import GitHubCli
from squadron.codehost.models import IssueComment, IssueSnapshot, RepositoryLocator
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import (
    CandidateRejection,
    QualificationOutcome,
    TestRejection,
)
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.store import MetrologyStore
from tests.benchmark.support import FixHistory, fix_history, hermetic_git
from tests.codehost.fake_runner import FakeProcessRunner

pytestmark = pytest.mark.network

PROJECT = ProjectId(value="e2e", source=ProjectIdSource.RECORDED)
LOCATOR = RepositoryLocator("github.com", "acme", "widgets", "origin")
NODE_NONE = "tests/test_none_input.py::test_none_input_returns_zero"


class ScriptedHost(GitHubCli):
    def __init__(self, snapshot: IssueSnapshot) -> None:
        super().__init__(FakeProcessRunner([]), frozenset({"github.com"}))
        self.snapshot = snapshot

    def get_issue(self, locator: RepositoryLocator, number: int) -> IssueSnapshot:
        return self.snapshot


def issue(*, later_comment: bool = False, edited_later: bool = False) -> IssueSnapshot:
    now = datetime.now(UTC)
    comments = [IssueComment("ann", "It crashes on None.", now - timedelta(days=1), None)]
    if later_comment:
        comments.append(IssueComment("bob", "Thanks for the fix!", now + timedelta(days=1), None))
    return IssueSnapshot(
        locator=LOCATOR,
        number=1,
        title="Crash on None input",
        body="exported_function(None) raises TypeError.",
        created_at=now - timedelta(days=3),
        last_edited_at=now + timedelta(days=1) if edited_later else None,
        comments=tuple(comments),
        title_renamed_at=(),
    )


class CountingSuites:
    """Wraps the suite runner and counts how many suites ran."""

    def __init__(self) -> None:
        self._inner = PythonBenchmarkAdapter()
        self.calls = 0

    def run_suite(self, ctx: SandboxContext, selection: SuiteSelection) -> SuiteRun:
        self.calls += 1
        return self._inner.run_suite(ctx, selection)


@dataclass
class Run:
    history: FixHistory
    deps: QualifyDeps
    suites: CountingSuites
    candidate: FixCandidate

    def qualify(self) -> QualifyResult:
        return qualify_candidate(self.candidate, self.deps)


def build_run(
    tmp_path: Path,
    scenario: str,
    *,
    base_scenario: str | None = None,
    snapshot: IssueSnapshot | None = None,
) -> Run:
    history = fix_history("fixfair_project", scenario, tmp_path / "history", base_scenario)
    hermetic_git(history.repo, "remote", "add", "origin", "git@github.com:acme/widgets.git")
    runner = SubprocessRunner()
    candidates = discover(runner, history.repo, timeout_seconds=60).candidates
    assert [c.sha for c in candidates] == [history.fix_sha]
    suites = CountingSuites()
    sandboxes = 0

    def factory(start_sha: str) -> BenchmarkSandbox:
        nonlocal sandboxes
        sandboxes += 1
        return BenchmarkSandbox(
            start_sha=start_sha,
            sandbox_id=f"e2e-{scenario}-{sandboxes}",
            repo_root=history.repo,
            runner=runner,
            adapter=PythonBenchmarkAdapter(),
            harness_env=dict(os.environ),
            install_timeout_s=900,
            suite_timeout_s=300,
            root=tmp_path / "sandboxes",
        )

    deps = QualifyDeps(
        repo_root=history.repo,
        project_id=PROJECT,
        host=ScriptedHost(snapshot or issue()),
        store=BenchmarkRecordStore(MetrologyStore(store_dir=tmp_path / "store")),
        runner=runner,
        adapter=PythonFixCaseAdapter(),
        sandbox_stages=qualify_in_sandbox,
        sandbox_factory=factory,
        suite_runner=suites,
        repeats=2,
        git_timeout_seconds=60,
    )
    return Run(history, deps, suites, candidates[0])


def rejection_of(result: QualifyResult) -> CandidateRejection | None:
    return result.record.rejection


# --- A qualifying crash fix --------------------------------------------------------------


def test_a_crash_fix_qualifies_with_the_expected_case(tmp_path: Path) -> None:
    setup = build_run(tmp_path, "crash_fix")
    result = setup.qualify()
    assert result.record.outcome is QualificationOutcome.QUALIFIED, result.record.detail
    case = setup.deps.store.get_case(result.record.case_id or "")
    assert case is not None
    assert case.hidden_tests == (NODE_NONE,)
    assert case.start_sha == setup.history.parent_sha
    assert case.reference_sha == setup.history.fix_sha
    assert "It crashes on None." in case.task_text
    assert [command.kind.value for command in case.grader_commands] == ["suite"]
    assert case.excluded_tests == ()
    assert result.record.environment is not None


def test_a_second_run_reuses_the_record_and_runs_no_suite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup = build_run(tmp_path, "crash_fix")
    first = setup.qualify()
    suites_after_first = setup.suites.calls
    assert suites_after_first > 0
    second = setup.qualify()
    assert second.reused is True
    assert second.record == first.record
    assert setup.suites.calls == suites_after_first, "a reused candidate runs no suite"

    # Bumping the rule version makes the stored record stale.
    for module in (qualify_sandbox, qualify_types):
        monkeypatch.setattr(module, "FAIRNESS_RULE_VERSION", qualify_types.FAIRNESS_RULE_VERSION + 1)
    third = setup.qualify()
    assert third.reused is False
    assert setup.suites.calls > suites_after_first


def test_a_later_comment_does_not_change_the_case_id(tmp_path: Path) -> None:
    """Same history, same environment, a comment added after the fix: the same case."""
    setup = build_run(tmp_path, "crash_fix", snapshot=issue())
    plain = setup.qualify()
    with_comment = replace(
        setup.deps,
        host=ScriptedHost(issue(later_comment=True)),
        store=BenchmarkRecordStore(MetrologyStore(store_dir=tmp_path / "second_store")),
    )
    later = qualify_candidate(setup.candidate, with_comment)
    assert plain.record.case_id is not None
    assert plain.record.case_id == later.record.case_id
    assert later.reused is False, "the second store is empty, so this was qualified again"


def test_an_issue_edited_after_the_fix_is_rejected(tmp_path: Path) -> None:
    result = build_run(tmp_path, "crash_fix", snapshot=issue(edited_later=True)).qualify()
    assert rejection_of(result) is CandidateRejection.ISSUE_EDITED_AFTER_FIX
    assert result.record.environment is None


# --- Fairness rejections -----------------------------------------------------------------


def hidden_reasons(result: QualifyResult) -> dict[str, tuple[TestRejection | None, str]]:
    return {v.node_id: (v.rejection, v.detail) for v in result.record.hidden_verdicts}


def test_a_test_coupled_to_an_internal_function_is_rejected(tmp_path: Path) -> None:
    result = build_run(tmp_path, "coupled_test").qualify()
    assert rejection_of(result) is CandidateRejection.NO_QUALIFYING_HIDDEN_TEST
    node = "tests/test_pricing_direct.py::test_discount_is_a_percentage"
    assert hidden_reasons(result)[node] == (
        TestRejection.REACHES_PAST_BOUNDARY,
        "fixpkg.pricing.apply_discount",
    )


def test_a_test_that_patches_project_code_is_rejected(tmp_path: Path) -> None:
    result = build_run(tmp_path, "patching_test").qualify()
    assert rejection_of(result) is CandidateRejection.NO_QUALIFYING_HIDDEN_TEST
    node = "tests/test_execute_timeout.py::test_execute_passes_a_timeout"
    assert hidden_reasons(result)[node] == (TestRejection.PATCHES_PROJECT_CODE, "fixpkg.mod.run")


def test_a_test_using_a_new_unexported_symbol_is_rejected_by_the_boundary_check_first(
    tmp_path: Path,
) -> None:
    """The trace runs before test-first, and a symbol the fix added is outside the parent's boundary."""
    setup = build_run(tmp_path, "test_first")
    result = setup.qualify()
    assert result.record.outcome is QualificationOutcome.QUALIFIED, result.record.detail
    reasons = hidden_reasons(result)
    assert reasons["tests/test_symbol.py::test_uses_added_symbol"][0] is (
        TestRejection.REACHES_PAST_BOUNDARY
    )
    assert reasons["tests/test_symbol_import.py::test_imports_added_symbol"][0] is (
        TestRejection.REACHES_PAST_BOUNDARY
    )
    assert reasons["tests/test_behavior.py::test_negative_is_clamped"][0] is None
    case = setup.deps.store.get_case(result.record.case_id or "")
    node = "tests/test_behavior.py::test_negative_is_clamped"
    assert case is not None and case.hidden_tests == (node,)


def test_a_test_importing_a_constant_the_fix_added_uses_a_symbol_the_fix_added(
    tmp_path: Path,
) -> None:
    """Constants are a known gap of the trace, so the boundary check passes and test-first decides."""
    result = build_run(tmp_path, "added_constant").qualify()
    assert rejection_of(result) is CandidateRejection.NO_QUALIFYING_HIDDEN_TEST
    node = "tests/test_limit.py::test_default_limit"
    assert hidden_reasons(result)[node][0] is TestRejection.USES_SYMBOL_ADDED_BY_FIX


def test_a_fix_that_changes_the_conftest_is_rejected_before_any_sandbox(tmp_path: Path) -> None:
    result = build_run(tmp_path, "conftest_change").qualify()
    assert rejection_of(result) is CandidateRejection.MODIFIES_TEST_SUPPORT
    assert result.record.environment is None


def test_a_fix_that_changes_the_lockfile_is_rejected_before_any_sandbox(tmp_path: Path) -> None:
    result = build_run(tmp_path, "lockfile_change").qualify()
    assert rejection_of(result) is CandidateRejection.CHANGES_LOCKFILE
    assert result.record.environment is None


# --- Flakiness ---------------------------------------------------------------------------


def test_a_flaky_unchanged_test_lands_on_excluded_tests(tmp_path: Path) -> None:
    setup = build_run(tmp_path, "crash_fix", base_scenario="flaky_base")
    result = setup.qualify()
    assert result.record.outcome is QualificationOutcome.QUALIFIED, result.record.detail
    flaky = "tests/test_flaky_env.py::test_alternates"
    assert result.record.excluded_with_reasons == ((flaky, TestRejection.FLAKY),)
    case = setup.deps.store.get_case(result.record.case_id or "")
    assert case is not None
    assert case.excluded_tests == (flaky,)
