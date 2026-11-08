"""Qualification stages that need no sandbox (slice 422 D1, D2, D3, D13)."""

from __future__ import annotations

import logging
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadron.benchmark.adapter import SandboxContext, SuiteRun, SuiteSelection
from squadron.benchmark.build_errors import BuildHalted
from squadron.benchmark.diff_classify import DiffClassification
from squadron.benchmark.fix_discovery import FixCandidate
from squadron.benchmark.python_fairness import PythonFixCaseAdapter
from squadron.benchmark.qualify import qualify_candidate
from squadron.benchmark.qualify_types import QualifyDeps, QualifyResult, QualifySandbox
from squadron.codehost.errors import (
    GitHubCliMissingError,
    HostCommandTimeoutError,
    HostUnauthenticatedError,
    IssueNotFoundError,
    ReferenceIsPullRequestError,
)
from squadron.codehost.github_cli import GitHubCli
from squadron.codehost.models import IssueComment, IssueSnapshot, RepositoryLocator
from squadron.core.process_runner import ProcessResult, ProcessTimedOutError
from squadron.metrology.benchmark_models import CandidateRejection, QualificationOutcome
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.store import MetrologyStore
from tests.benchmark.support import RunnerCall, ScriptedRunner
from tests.codehost.fake_runner import FakeProcessRunner

PARENT = "p" * 40
FIX = "f" * 40
COMMITTED = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
PROJECT = ProjectId(value="proj", source=ProjectIdSource.RECORDED)
CANDIDATE = FixCandidate(FIX, PARENT, COMMITTED, "#5", None, 5)
PYPROJECT = "[project]\nname = 'p'\n"
LOCATOR = RepositoryLocator("github.com", "acme", "widgets", "origin")


class ScriptedHost(GitHubCli):
    """A real ``GitHubCli`` whose ``get_issue`` is scripted."""

    def __init__(self, outcome: IssueSnapshot | Exception) -> None:
        super().__init__(FakeProcessRunner([]), frozenset({"github.com"}))
        self._outcome = outcome

    def get_issue(self, locator: RepositoryLocator, number: int) -> IssueSnapshot:
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def snapshot(*, edited: datetime | None = None) -> IssueSnapshot:
    return IssueSnapshot(
        locator=LOCATOR,
        number=5,
        title="Crash",
        body="It crashes.",
        created_at=COMMITTED.replace(day=1),
        last_edited_at=edited,
        comments=(
            IssueComment("ann", "more detail", COMMITTED.replace(day=2), None),
            IssueComment("bob", "after the fix", COMMITTED.replace(day=20), None),
        ),
        title_renamed_at=(),
    )


@dataclass
class GitWorld:
    """What the scripted git answers; ``failing`` maps an argv prefix to a failure."""

    remotes: dict[str, str] = field(
        default_factory=lambda: {"origin": "git@github.com:acme/widgets.git"}
    )
    files: dict[tuple[str, str], str] = field(
        default_factory=lambda: {(PARENT, "pyproject.toml"): PYPROJECT}
    )
    diff: str = "A\ttests/test_new.py\nM\tsrc/pkg/mod.py\n"
    failing: dict[tuple[str, ...], ProcessResult | Exception] = field(default_factory=dict)

    def handle(self, call: RunnerCall) -> ProcessResult:
        argv = call.argv
        for prefix, outcome in self.failing.items():
            if argv[: len(prefix)] == prefix:
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome
        return self._answer(argv)

    def _answer(self, argv: tuple[str, ...]) -> ProcessResult:
        if argv == ("git", "remote"):
            return ProcessResult(argv, 0, "".join(f"{name}\n" for name in self.remotes), "")
        if argv[:3] == ("git", "remote", "get-url"):
            return ProcessResult(argv, 0, self.remotes[argv[3]] + "\n", "")
        if argv[:3] == ("git", "ls-tree", "--name-only"):
            sha, path = argv[3], argv[5]
            return ProcessResult(argv, 0, f"{path}\n" if (sha, path) in self.files else "", "")
        if argv[:2] == ("git", "show"):
            sha, _, path = argv[2].partition(":")
            return ProcessResult(argv, 0, self.files[(sha, path)], "")
        if argv[:3] == ("git", "diff", "--name-status"):
            return ProcessResult(argv, 0, self.diff, "")
        raise AssertionError(f"unscripted git call: {argv}")


def _no_sandbox(start_sha: str) -> AbstractContextManager[QualifySandbox]:
    raise AssertionError("a pre-sandbox test built a sandbox")


class _NoSuites:
    def run_suite(self, ctx: SandboxContext, selection: SuiteSelection) -> SuiteRun:
        raise AssertionError("a pre-sandbox test ran a suite")


class FailingStore(BenchmarkRecordStore):
    def write_fix_qualification(self, qualification: object) -> str:
        raise MetrologyStoreError("disk full")


@dataclass
class Harness:
    deps: QualifyDeps
    store: BenchmarkRecordStore
    sandbox_calls: list[tuple[FixCandidate, DiffClassification, str]] = field(default_factory=list)


def harness(
    tmp_path: Path,
    host: GitHubCli,
    world: GitWorld | None = None,
    *,
    failing_store: bool = False,
) -> Harness:
    world = world or GitWorld()
    raw = MetrologyStore(store_dir=tmp_path / "store")
    store = FailingStore(raw) if failing_store else BenchmarkRecordStore(raw)
    calls: list[tuple[FixCandidate, DiffClassification, str]] = []

    def sandbox_stages(
        candidate: FixCandidate, classification: DiffClassification, task_text: str, deps: QualifyDeps
    ) -> QualifyResult:
        calls.append((candidate, classification, task_text))
        raise AssertionError("the sandbox stages must not run in these tests unless expected")

    deps = QualifyDeps(
        repo_root=tmp_path,
        project_id=PROJECT,
        host=host,
        store=store,
        runner=ScriptedRunner(world.handle),
        adapter=PythonFixCaseAdapter(),
        sandbox_stages=sandbox_stages,
        sandbox_factory=_no_sandbox,
        suite_runner=_NoSuites(),
        repeats=3,
        git_timeout_seconds=30,
    )
    return Harness(deps, store, calls)


def run(
    tmp_path: Path, host: GitHubCli, world: GitWorld | None = None
) -> tuple[QualifyResult, Harness]:
    setup = harness(tmp_path, host, world)
    return qualify_candidate_expecting_no_sandbox(setup), setup


def qualify_candidate_expecting_no_sandbox(setup: Harness) -> QualifyResult:
    result = qualify_candidate(CANDIDATE, setup.deps)
    assert setup.sandbox_calls == [], "a pre-sandbox outcome must not reach the sandbox stages"
    return result


def assert_stored(setup: Harness, result: QualifyResult) -> None:
    assert result.record.environment is None
    assert result.reused is False
    stored = setup.store.get_fix_qualification(PROJECT, FIX, None)
    assert stored == result.record


# --- One test per rejection reached in these stages -------------------------------------


def test_no_issue_host(tmp_path: Path) -> None:
    result, setup = run(tmp_path, ScriptedHost(snapshot()), GitWorld(remotes={}))
    assert result.record.outcome is QualificationOutcome.REJECTED
    assert result.record.rejection is CandidateRejection.NO_ISSUE_HOST
    assert_stored(setup, result)


def test_issue_not_found(tmp_path: Path) -> None:
    result, setup = run(tmp_path, ScriptedHost(IssueNotFoundError("no issue acme/widgets#5")))
    assert result.record.rejection is CandidateRejection.ISSUE_NOT_FOUND
    assert_stored(setup, result)


def test_reference_is_pull_request(tmp_path: Path) -> None:
    result, setup = run(tmp_path, ScriptedHost(ReferenceIsPullRequestError("is a pull request")))
    assert result.record.rejection is CandidateRejection.REFERENCE_IS_PULL_REQUEST
    assert_stored(setup, result)


def test_issue_edited_after_the_fix(tmp_path: Path) -> None:
    edited = snapshot(edited=COMMITTED.replace(day=15))
    result, setup = run(tmp_path, ScriptedHost(edited))
    assert result.record.rejection is CandidateRejection.ISSUE_EDITED_AFTER_FIX
    assert result.record.issue_ref == "acme/widgets#5"
    assert_stored(setup, result)


def test_a_parent_without_pyproject_has_no_fix_case_adapter_not_a_harness_error(tmp_path: Path) -> None:
    world = GitWorld(files={})
    result, setup = run(tmp_path, ScriptedHost(snapshot()), world)
    assert result.record.outcome is QualificationOutcome.REJECTED
    assert result.record.rejection is CandidateRejection.NO_FIX_CASE_ADAPTER
    assert_stored(setup, result)


@pytest.mark.parametrize(
    ("diff", "files", "rejection"),
    [
        ("M\tsrc/pkg/mod.py\n", {}, CandidateRejection.NO_TEST_CHANGE),
        ("A\ttests/data/case.json\n", {}, CandidateRejection.TEST_DATA_CHANGED),
        ("A\ttests/test_new.py\nM\tuv.lock\n", {}, CandidateRejection.CHANGES_LOCKFILE),
        (
            "A\ttests/test_new.py\nM\ttests/conftest.py\n",
            {
                (PARENT, "tests/conftest.py"): "X = 1\n",
                (FIX, "tests/conftest.py"): "X = 2\n",
            },
            CandidateRejection.MODIFIES_TEST_SUPPORT,
        ),
    ],
    ids=["no test change", "test data", "lockfile", "conftest"],
)
def test_diff_classification_rejections(
    tmp_path: Path, diff: str, files: dict[tuple[str, str], str], rejection: CandidateRejection
) -> None:
    world = GitWorld(diff=diff)
    world.files.update(files)
    result, setup = run(tmp_path, ScriptedHost(snapshot()), world)
    assert result.record.rejection is rejection
    assert result.record.issue_ref == "acme/widgets#5"
    assert_stored(setup, result)


def test_a_clean_candidate_reaches_the_sandbox_stages_with_the_frozen_task_text(tmp_path: Path) -> None:
    setup = harness(tmp_path, ScriptedHost(snapshot()))
    with pytest.raises(AssertionError, match="must not run"):
        qualify_candidate(CANDIDATE, setup.deps)
    ((candidate, classification, task_text),) = setup.sandbox_calls
    assert candidate is CANDIDATE
    assert classification.added == ("tests/test_new.py",)
    assert "more detail" in task_text and "after the fix" not in task_text


# --- Harness failures: harness_error with detail and an ERROR log, never a rejection -----


def assert_harness_error(
    setup: Harness, result: QualifyResult, caplog: pytest.LogCaptureFixture, text: str
) -> None:
    assert result.record.outcome is QualificationOutcome.HARNESS_ERROR
    assert result.record.rejection is None
    assert text in result.record.detail
    assert any(record.levelno == logging.ERROR for record in caplog.records)
    assert_stored(setup, result)


@pytest.mark.parametrize(
    ("host_error", "text"),
    [
        (HostCommandTimeoutError(["gh", "api", "graphql"], 30), "HostCommandTimeoutError"),
        (HostUnauthenticatedError("not authenticated to github.com"), "HostUnauthenticatedError"),
    ],
)
def test_host_failures_are_harness_errors(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, host_error: Exception, text: str
) -> None:
    with caplog.at_level(logging.ERROR):
        result, setup = run(tmp_path, ScriptedHost(host_error))
    assert_harness_error(setup, result, caplog, text)


@pytest.mark.parametrize(
    ("failing", "text"),
    [
        (("git", "remote"), "git remote"),
        (("git", "ls-tree"), "git ls-tree"),
        (("git", "show"), "git show"),
        (("git", "diff"), "git diff"),
    ],
)
@pytest.mark.parametrize("failure", ["exit", "timeout"])
def test_git_failures_are_harness_errors(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, failing: tuple[str, ...], text: str, failure: str
) -> None:
    outcome: ProcessResult | Exception = (
        ProcessResult(failing, 128, "", "fatal: bad object")
        if failure == "exit"
        else ProcessTimedOutError(failing, 30)
    )
    world = GitWorld(failing={failing: outcome})
    with caplog.at_level(logging.ERROR):
        result, setup = run(tmp_path, ScriptedHost(snapshot()), world)
    assert_harness_error(setup, result, caplog, text)


def test_a_missing_gh_halts_the_build_and_writes_no_record(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    setup = harness(tmp_path, ScriptedHost(GitHubCliMissingError("the GitHub CLI (gh) is not on PATH")))
    with caplog.at_level(logging.ERROR), pytest.raises(BuildHalted, match="gh is not available"):
        qualify_candidate(CANDIDATE, setup.deps)
    assert setup.store.list_fix_qualifications() == []
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_a_failing_store_write_halts_the_build(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    setup = harness(tmp_path, ScriptedHost(IssueNotFoundError("gone")), failing_store=True)
    with caplog.at_level(logging.ERROR), pytest.raises(BuildHalted, match="could not store"):
        qualify_candidate(CANDIDATE, setup.deps)
    assert any(record.levelno == logging.ERROR for record in caplog.records)
