"""``sq benchmark fix-cases build|show`` and ``sq benchmark yield`` (slice 422).

The build function is patched at the CLI's boundary; the store lives under ``tmp_path``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from squadron.benchmark.build_errors import BuildHalted
from squadron.benchmark.case_build import BuildDeps, BuildResult
from squadron.cli.app import app
from squadron.cli.commands import benchmark_fix_cases as cli_module
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
    TestRejection,
)
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.store import MetrologyStore
from tests.benchmark.support import hermetic_git
from tests.benchmark.test_yield_report import environment, record

runner = CliRunner()
PROJECT = ProjectId(value="alpha", source=ProjectIdSource.RECORDED)
Q, R = QualificationOutcome.QUALIFIED, QualificationOutcome.REJECTED


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "checkout"
    path.mkdir()
    hermetic_git(path, "init", "-q", "-b", "main")
    return path


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> BenchmarkRecordStore:
    directory = tmp_path / "store"
    monkeypatch.setattr(cli_module, "resolve_store_dir", lambda cwd: directory)
    monkeypatch.setattr(cli_module, "derive_project_id", lambda cwd: PROJECT)
    monkeypatch.setattr(cli_module, "sweep_benchmark_orphans", lambda runner: None)
    monkeypatch.setattr(cli_module, "build_github_host", lambda runner: object())
    return BenchmarkRecordStore(MetrologyStore(store_dir=directory))


def invoke(*args: str) -> Any:
    return runner.invoke(app, ["benchmark", *args])


# --- build ---------------------------------------------------------------------------------


class BuildSpy:
    def __init__(self, result: BuildResult | Exception) -> None:
        self.result = result
        self.calls: list[tuple[Path, str, tuple[str, ...], BuildDeps]] = []

    def __call__(
        self,
        repo_root: Path,
        set_name: str,
        commits: tuple[str, ...],
        deps: BuildDeps,
        on_candidate: Callable[[str], None],
    ) -> BuildResult:
        self.calls.append((repo_root, set_name, commits, deps))
        on_candidate("aaaaaaaa qualified case-0123456789abcdef (1 hidden)")
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def fake_build(monkeypatch: pytest.MonkeyPatch, result: BuildResult | Exception) -> BuildSpy:
    spy = BuildSpy(result)
    monkeypatch.setattr(cli_module, "build_fix_cases", spy)
    return spy


def test_build_prints_each_candidate_then_the_report_and_exits_zero(
    repo: Path, store: BenchmarkRecordStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    store.write_fix_qualification(
        record("alpha", "a", Q, case_id="case-0123456789abcdef", env=environment())
    )
    spy = fake_build(monkeypatch, BuildResult(PROJECT, (), None))
    result = invoke("fix-cases", "build", "--set", "fix-alpha", "--repo", str(repo))
    assert result.exit_code == 0, result.output
    assert "aaaaaaaa qualified case-0123456789abcdef (1 hidden)" in result.output
    assert "no qualified cases: no case set written" in result.output
    assert "project  candidates  qualified  top rejections" in result.output
    assert "separability alpha" in result.output
    assert spy.calls[0][1] == "fix-alpha"


def test_build_reports_the_case_set_it_wrote(
    repo: Path, store: BenchmarkRecordStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    from squadron.metrology.benchmark_models import CaseSet

    case_set = CaseSet(name="fix-alpha", version=3, case_ids=(), created_at=datetime.now(UTC))
    fake_build(monkeypatch, BuildResult(PROJECT, (), case_set))
    result = invoke("fix-cases", "build", "--set", "fix-alpha", "--repo", str(repo))
    assert "case set fix-alpha v3" in result.output


def test_an_invalid_report_setting_exits_one_before_the_build_runs(
    repo: Path, store: BenchmarkRecordStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    def invalid(key: str, cwd: str = ".") -> float:
        raise ValueError(f"{key} must be greater than 0 and less than 1, got 1.5")

    monkeypatch.setattr(cli_module, "get_open_unit_interval_config", invalid)
    spy = fake_build(monkeypatch, BuildResult(PROJECT, (), None))
    result = invoke("fix-cases", "build", "--set", "s", "--repo", str(repo))
    assert result.exit_code == 1
    assert "must be greater than 0" in result.output
    assert spy.calls == [], "the build wrote nothing before the config error"


def test_commit_is_repeatable_and_reaches_the_build(
    repo: Path, store: BenchmarkRecordStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = fake_build(monkeypatch, BuildResult(PROJECT, (), None))
    invoke(
        "fix-cases", "build", "--set", "s", "--repo", str(repo), "--commit", "abc", "--commit", "def"
    )
    assert spy.calls[0][2] == ("abc", "def")
    invoke("fix-cases", "build", "--set", "s", "--repo", str(repo))
    assert spy.calls[1][2] == ()


class FakeSandbox:
    created: list[FakeSandbox] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.kept = False
        FakeSandbox.created.append(self)

    def keep(self) -> None:
        self.kept = True


@pytest.mark.parametrize(("flag", "kept"), [(["--keep"], True), ([], False)])
def test_keep_reaches_the_sandbox_factory(
    repo: Path,
    store: BenchmarkRecordStore,
    monkeypatch: pytest.MonkeyPatch,
    flag: list[str],
    kept: bool,
) -> None:
    FakeSandbox.created = []
    monkeypatch.setattr(cli_module, "BenchmarkSandbox", FakeSandbox)
    spy = fake_build(monkeypatch, BuildResult(PROJECT, (), None))
    invoke("fix-cases", "build", "--set", "s", "--repo", str(repo), *flag)
    factory = spy.calls[0][3].sandbox_factory
    factory("a" * 40)
    sandbox = FakeSandbox.created[0]
    assert sandbox.kept is kept
    assert sandbox.kwargs["start_sha"] == "a" * 40
    # The root is what ``git rev-parse --show-toplevel`` prints: the symlink-resolved path.
    assert sandbox.kwargs["repo_root"] == repo.resolve()


def test_a_halted_build_exits_one_with_the_reason(
    repo: Path, store: BenchmarkRecordStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_build(monkeypatch, BuildHalted("gh is not available: not on PATH"))
    result = invoke("fix-cases", "build", "--set", "s", "--repo", str(repo))
    assert result.exit_code == 1
    assert "gh is not available" in result.output


def test_an_unresolvable_repository_exits_one(tmp_path: Path, store: BenchmarkRecordStore) -> None:
    result = invoke("fix-cases", "build", "--set", "s", "--repo", str(tmp_path / "missing"))
    assert result.exit_code == 1
    assert "failed" in result.output


# --- show ----------------------------------------------------------------------------------


def a_case(sha: str) -> BenchmarkCase:
    return BenchmarkCase.build(
        project_id=PROJECT,
        kind=CaseKind.FIX,
        start_sha="0" * 40,
        reference_sha=sha * 40,
        task_text="# Crash\n\nIt crashes.",
        hidden_tests=("tests/test_a.py::t",),
        hidden_fixtures=(),
        superseded_tests=("tests/test_old.py::gone",),
        excluded_tests=("tests/test_old.py::flaky",),
        grader_commands=(GraderCommand(kind=GraderCommandKind.SUITE, argv=("pytest",)),),
        provenance=CaseProvenance(source_ref="#1", created_at=datetime.now(UTC), built_by="t"),
    )


def store_a_qualified_case(store: BenchmarkRecordStore, sha: str = "a") -> BenchmarkCase:
    case = a_case(sha)
    store.write_case(case)
    qualified = record("alpha", sha, Q, case_id=case.case_id, env=environment())
    verdict = HiddenTestVerdict(node_id="tests/test_a.py::t", kind=HiddenTestVerdictKind.QUALIFIED)
    with_detail = qualified.model_copy(
        update={
            "hidden_verdicts": (verdict,),
            "excluded_with_reasons": (("tests/test_old.py::flaky", TestRejection.FLAKY),),
        }
    )
    store.write_fix_qualification(with_detail)
    return case


def test_show_by_commit_prefix_prints_the_record_and_the_case(
    store: BenchmarkRecordStore, repo: Path
) -> None:
    case = store_a_qualified_case(store)
    result = invoke("fix-cases", "show", "aaaaaa", "--repo", str(repo))
    assert result.exit_code == 0, result.output
    out = result.output
    assert environment().identity_digest in out
    assert "qualified  tests/test_a.py::t" in out
    assert "flaky  tests/test_old.py::flaky" in out
    assert "tests/test_old.py::gone" in out
    assert "It crashes." in out
    assert case.case_id in out


def test_show_by_case_id(store: BenchmarkRecordStore, repo: Path) -> None:
    case = store_a_qualified_case(store)
    result = invoke("fix-cases", "show", case.case_id, "--repo", str(repo))
    assert result.exit_code == 0 and "commit: " + "a" * 40 in result.output


def test_show_of_a_rejected_candidate_prints_its_verdicts_and_no_environment(
    store: BenchmarkRecordStore, repo: Path
) -> None:
    rejected = record(
        "alpha",
        "b",
        R,
        CandidateRejection.NO_QUALIFYING_HIDDEN_TEST,
        verdicts=(TestRejection.PATCHES_PROJECT_CODE,),
    )
    store.write_fix_qualification(rejected)
    result = invoke("fix-cases", "show", "bbbb", "--repo", str(repo))
    assert result.exit_code == 0
    assert "none (decided before the sandbox)" in result.output
    assert "rejected patches_project_code  t.py::t0" in result.output


def test_show_with_an_ambiguous_prefix_exits_one_listing_the_matches(
    store: BenchmarkRecordStore, repo: Path
) -> None:
    store.write_fix_qualification(record("alpha", "a", R, CandidateRejection.NO_TEST_CHANGE))
    store.write_fix_qualification(
        record("alpha", "a", R, CandidateRejection.NO_TEST_CHANGE).model_copy(
            update={"commit_sha": "a" * 8 + "b" * 32}
        )
    )
    result = invoke("fix-cases", "show", "aaaa", "--repo", str(repo))
    assert result.exit_code == 1
    assert "matches several commits" in result.output
    assert "a" * 40 in result.output and "a" * 8 + "b" * 32 in result.output


def test_show_with_no_record_exits_one(store: BenchmarkRecordStore, repo: Path) -> None:
    result = invoke("fix-cases", "show", "feedface", "--repo", str(repo))
    assert result.exit_code == 1
    assert "no qualification record matches feedface" in result.output


# --- yield ---------------------------------------------------------------------------------


def test_yield_without_repo_reads_every_project(
    store: BenchmarkRecordStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    store.write_fix_qualification(record("alpha", "a", R, CandidateRejection.NO_TEST_CHANGE))
    store.write_fix_qualification(record("beta", "b", R, CandidateRejection.MERGE_COMMIT))
    result = invoke("yield")
    assert result.exit_code == 0, result.output
    assert "alpha" in result.output and "beta" in result.output and "pooled" in result.output


def test_yield_with_repo_limits_to_that_project(store: BenchmarkRecordStore, repo: Path) -> None:
    store.write_fix_qualification(record("alpha", "a", R, CandidateRejection.NO_TEST_CHANGE))
    store.write_fix_qualification(record("beta", "b", R, CandidateRejection.MERGE_COMMIT))
    result = invoke("yield", "--repo", str(repo))
    assert "alpha" in result.output and "beta" not in result.output


def test_yield_json_prints_json_only_and_names_the_case_set(
    store: BenchmarkRecordStore, repo: Path
) -> None:
    case = store_a_qualified_case(store)
    store.write_case_set("fix-alpha", (case.case_id,))
    result = invoke("yield", "--repo", str(repo), "--json")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["case_sets"] == [{"name": "fix-alpha", "version": 1}]
    assert payload["rows"][0]["project"] == "alpha"


def test_yield_with_no_records_says_so(
    store: BenchmarkRecordStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = invoke("yield")
    assert result.exit_code == 0
    assert "no fix qualification records" in result.output


def test_the_new_commands_are_listed_in_help() -> None:
    top = invoke("--help").output
    assert "fix-cases" in top and "yield" in top
    assert (
        "build" in invoke("fix-cases", "--help").output
        and "show" in invoke("fix-cases", "--help").output
    )
