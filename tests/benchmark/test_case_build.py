"""``build_fix_cases`` over a real closing-commit repository, scripted host (slice 422 D9, D13)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadron.benchmark.build_errors import BuildHalted
from squadron.benchmark.case_build import BuildDeps, BuildResult, build_fix_cases
from squadron.benchmark.diff_classify import DiffClassification
from squadron.benchmark.fix_discovery import FixCandidate
from squadron.benchmark.qualify_types import QualifyDeps, QualifyResult, record_outcome
from squadron.codehost.errors import GitHubCliMissingError
from squadron.codehost.github_cli import GitHubCli
from squadron.codehost.models import IssueComment, IssueSnapshot, RepositoryLocator
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import (
    BenchmarkCase,
    CandidateRejection,
    CaseKind,
    CaseProvenance,
    GraderCommand,
    GraderCommandKind,
    HiddenTestVerdict,
    HiddenTestVerdictKind,
    QualificationOutcome,
)
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.errors import MetrologyIdentityError, MetrologyStoreError
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.snapshot_models import SourceLanguage
from squadron.metrology.store import MetrologyStore
from tests.benchmark.support import ClosingCommitRepo, closing_commit_repo, hermetic_git
from tests.codehost.fake_runner import FakeProcessRunner

PROJECT = ProjectId(value="closing", source=ProjectIdSource.RECORDED)
LOCATOR = RepositoryLocator("github.com", "acme", "widgets", "origin")
ENVIRONMENT = EnvironmentIdentity(
    language=SourceLanguage.PYTHON,
    lockfile_path="uv.lock",
    lockfile_sha256="l" * 64,
    interpreter_version="3.12.1",
    installer_version="uv 0.5",
    platform="darwin-arm64",
    scrub_spec_version=1,
)
#: Candidate commit names: how the fake sandbox stages treat each one.
QUALIFIES = ("body_line", "colon_form")
REJECTED_AT_SANDBOX = ("same_twice",)
EVERY_CLOSING_COMMIT = (
    "body_line",
    "two_issues",
    "split_one",
    "split_two",
    "same_twice",
    "cross_repo",
    "colon_form",
    "merge",
)


class ScriptedHost(GitHubCli):
    def __init__(self, failure: Exception | None = None) -> None:
        super().__init__(FakeProcessRunner([]), frozenset({"github.com"}))
        self._failure = failure

    def get_issue(self, locator: RepositoryLocator, number: int) -> IssueSnapshot:
        if self._failure is not None:
            raise self._failure
        return IssueSnapshot(
            locator=locator,
            number=number,
            title="t",
            body="b",
            created_at=datetime(2000, 1, 1, tzinfo=UTC),
            last_edited_at=None,
            comments=(IssueComment("ann", "c", datetime(2000, 1, 2, tzinfo=UTC), None),),
            title_renamed_at=(),
        )


def fake_sandbox_stages(
    candidate: FixCandidate, classification: DiffClassification, task_text: str, deps: QualifyDeps
) -> QualifyResult:
    """Stands in for the sandbox pipeline: qualifies two commits, rejects one, honours reuse."""
    existing = deps.store.get_fix_qualification(
        deps.project_id, candidate.sha, ENVIRONMENT.identity_digest
    )
    if existing is not None:
        return QualifyResult(existing, reused=True)
    if candidate.sha in rejected_shas:
        return record_outcome(
            deps,
            candidate,
            QualificationOutcome.REJECTED,
            rejection=CandidateRejection.NO_QUALIFYING_HIDDEN_TEST,
            environment=ENVIRONMENT,
        )
    case = BenchmarkCase.build(
        project_id=deps.project_id,
        kind=CaseKind.FIX,
        start_sha=candidate.parent_sha,
        reference_sha=candidate.sha,
        task_text=task_text,
        hidden_tests=(f"tests/test_{candidate.sha[:6]}.py::test_it",),
        hidden_fixtures=(),
        superseded_tests=(),
        excluded_tests=(),
        grader_commands=(GraderCommand(kind=GraderCommandKind.SUITE, argv=("pytest",)),),
        provenance=CaseProvenance(
            source_ref=candidate.issue_ref, created_at=datetime.now(UTC), built_by="t"
        ),
    )
    deps.store.write_case(case)
    verdict = HiddenTestVerdict(node_id=case.hidden_tests[0], kind=HiddenTestVerdictKind.QUALIFIED)
    return record_outcome(
        deps,
        candidate,
        QualificationOutcome.QUALIFIED,
        case_id=case.case_id,
        hidden_verdicts=(verdict,),
        environment=ENVIRONMENT,
    )


rejected_shas: set[str] = set()


@pytest.fixture
def repo(tmp_path: Path) -> ClosingCommitRepo:
    built = closing_commit_repo(tmp_path)
    hermetic_git(built.path, "remote", "add", "origin", "git@github.com:acme/widgets.git")
    rejected_shas.clear()
    rejected_shas.update(built.shas[name] for name in REJECTED_AT_SANDBOX)
    return built


class FailingCaseSets(BenchmarkRecordStore):
    def write_case_set(self, name: str, case_ids: tuple[str, ...] | list[str]):  # type: ignore[no-untyped-def]
        raise MetrologyStoreError("disk full")


def deps_for(
    tmp_path: Path,
    *,
    host: GitHubCli | None = None,
    store: BenchmarkRecordStore | None = None,
    project: ProjectId | Exception = PROJECT,
) -> BuildDeps:
    def derive(cwd: str) -> ProjectId:
        if isinstance(project, Exception):
            raise project
        return project

    def no_sandbox(start_sha: str):  # type: ignore[no-untyped-def]
        raise AssertionError("the fake sandbox stages never build a sandbox")

    return BuildDeps(
        host=host or ScriptedHost(),
        store=store or BenchmarkRecordStore(MetrologyStore(store_dir=tmp_path / "store")),
        runner=SubprocessRunner(),
        sandbox_stages=fake_sandbox_stages,
        sandbox_factory=no_sandbox,
        derive_project_id=derive,
        repeats=2,
        git_timeout_seconds=60,
    )


def build(
    repo: ClosingCommitRepo,
    deps: BuildDeps,
    commits: tuple[str, ...] = (),
    set_name: str = "fix-closing",
) -> tuple[BuildResult, list[str]]:
    lines: list[str] = []
    return build_fix_cases(repo.path, set_name, commits, deps, lines.append), lines


def test_the_store_holds_exactly_one_record_per_closing_commit(
    repo: ClosingCommitRepo, tmp_path: Path
) -> None:
    deps = deps_for(tmp_path)
    result, lines = build(repo, deps)
    stored = deps.store.list_fix_qualifications(PROJECT)
    assert sorted(r.commit_sha for r in stored) == sorted(
        repo.shas[name] for name in EVERY_CLOSING_COMMIT
    )
    assert len(result.records) == len(stored) == len(lines) == 8


def test_each_candidate_prints_its_outcome(repo: ClosingCommitRepo, tmp_path: Path) -> None:
    result, lines = build(repo, deps_for(tmp_path))
    by_sha = {line.split()[0]: line for line in lines}

    def line(name: str) -> str:
        return by_sha[repo.shas[name][:8]]

    for name in QUALIFIES:
        assert " qualified case-" in line(name) and "(1 hidden)" in line(name)
    assert line("same_twice").endswith("rejected no_qualifying_hidden_test")
    assert line("cross_repo").endswith("rejected no_issue_host")
    assert line("merge").endswith("rejected merge_commit")
    assert line("two_issues").endswith("rejected multiple_issues_closed")
    assert line("split_one").endswith("rejected multiple_closing_commits")
    assert result.case_set is not None


def test_the_case_set_holds_the_qualified_cases(repo: ClosingCommitRepo, tmp_path: Path) -> None:
    deps = deps_for(tmp_path)
    result, _ = build(repo, deps)
    assert result.case_set is not None
    assert result.case_set.name == "fix-closing" and result.case_set.version == 1
    assert result.case_set.case_ids == tuple(sorted(result.qualified_case_ids))
    assert len(result.case_set.case_ids) == 2


def test_commit_limits_the_run_by_sha_prefix(repo: ClosingCommitRepo, tmp_path: Path) -> None:
    deps = deps_for(tmp_path)
    prefix = repo.shas["body_line"][:10]
    result, lines = build(repo, deps, commits=(prefix,))
    assert len(result.records) == 1 and len(lines) == 1
    assert result.records[0].commit_sha == repo.shas["body_line"]
    assert result.case_set is not None and len(result.case_set.case_ids) == 1


def test_commit_can_name_a_discovery_rejected_commit(repo: ClosingCommitRepo, tmp_path: Path) -> None:
    result, _ = build(repo, deps_for(tmp_path), commits=(repo.shas["merge"][:10],))
    assert [r.rejection for r in result.records] == [CandidateRejection.MERGE_COMMIT]
    assert result.case_set is None


def test_an_unknown_prefix_halts_with_an_error_log(
    repo: ClosingCommitRepo, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    deps = deps_for(tmp_path)
    with caplog.at_level(logging.ERROR), pytest.raises(BuildHalted, match="deadbeef"):
        build(repo, deps, commits=("deadbeef",))
    assert any(record.levelno == logging.ERROR for record in caplog.records)
    assert deps.store.list_fix_qualifications() == []


def test_a_second_run_reports_reused_and_creates_no_new_case_set_version(
    repo: ClosingCommitRepo, tmp_path: Path
) -> None:
    deps = deps_for(tmp_path)
    first, _ = build(repo, deps)
    second, lines = build(repo, deps)
    reused = [line for line in lines if " reused (" in line]
    assert len(reused) == 3, "the three candidates that reached the sandbox stage"
    assert second.case_set == first.case_set
    assert deps.store.get_case_set("fix-closing", 2) is None


def test_zero_qualified_cases_write_no_case_set(repo: ClosingCommitRepo, tmp_path: Path) -> None:
    rejected_shas.update(repo.shas[name] for name in QUALIFIES)
    deps = deps_for(tmp_path)
    result, _ = build(repo, deps)
    assert result.case_set is None
    assert result.qualified_case_ids == ()
    assert deps.store.get_case_set("fix-closing") is None


def test_a_missing_gh_halts_the_build(repo: ClosingCommitRepo, tmp_path: Path) -> None:
    deps = deps_for(tmp_path, host=ScriptedHost(GitHubCliMissingError("gh is not on PATH")))
    with pytest.raises(BuildHalted, match="gh is not available"):
        build(repo, deps)


def test_a_failing_case_set_write_halts_with_an_error_log(
    repo: ClosingCommitRepo, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = FailingCaseSets(MetrologyStore(store_dir=tmp_path / "store"))
    with caplog.at_level(logging.ERROR), pytest.raises(BuildHalted, match="could not write case set"):
        build(repo, deps_for(tmp_path, store=store))
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_a_repository_without_an_identity_halts(repo: ClosingCommitRepo, tmp_path: Path) -> None:
    deps = deps_for(tmp_path, project=MetrologyIdentityError("no stable identity"))
    with pytest.raises(BuildHalted, match="cannot identify the project"):
        build(repo, deps)
