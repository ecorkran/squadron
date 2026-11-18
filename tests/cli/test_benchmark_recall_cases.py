"""``sq benchmark recall cases add|list`` (slice 430 D1, D8)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.core.process_runner import ProcessResult, SubprocessRunner
from tests.benchmark.recall.fixtures.bug_repo.build import BUG_FILE, BuiltBugRepo, build
from tests.benchmark.recall.support import fake_services, invoke_recall
from tests.benchmark.support import RunnerCall, ScriptedRunner, failed


@pytest.fixture
def bug_repo(tmp_path: Path) -> BuiltBugRepo:
    return build(tmp_path / "bug_repo")


def test_happy_path_then_list(bug_repo: BuiltBugRepo, tmp_path: Path) -> None:
    services = fake_services(tmp_path)
    result = invoke_recall(services, "cases", "add", str(bug_repo.case_file), "--set", "fixture")
    assert result.exit_code == 0, result.output
    assert "set fixture v1 with 1 cases" in result.output
    listing = invoke_recall(services, "cases", "list", "--set", "fixture")
    assert listing.exit_code == 0, listing.output
    assert "fixture v1: 1 cases" in listing.output
    assert "fixture-bug-repo" in listing.output
    assert BUG_FILE in listing.output
    assert "repo=present" in listing.output


def test_rerun_keeps_v1(bug_repo: BuiltBugRepo, tmp_path: Path) -> None:
    services = fake_services(tmp_path)
    invoke_recall(services, "cases", "add", str(bug_repo.case_file), "--set", "fixture")
    again = invoke_recall(services, "cases", "add", str(bug_repo.case_file), "--set", "fixture")
    assert again.exit_code == 0
    assert "(0 new); set fixture v1" in again.output
    assert [s.version for s in services.store.list_case_sets()] == [1]


def test_two_bad_files_listed_nothing_written(
    bug_repo: BuiltBugRepo, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    folder = tmp_path / "cases"
    folder.mkdir()
    (folder / "a.yaml").write_text(bug_repo.case_file.read_text())
    (folder / "b.yaml").write_text("name: b\nkind: code\n")
    (folder / "c.yaml").write_text(
        bug_repo.case_file.read_text().replace("status: verified", "status: x")
    )
    services = fake_services(tmp_path)
    with caplog.at_level(logging.ERROR):
        result = invoke_recall(services, "cases", "add", str(folder), "--set", "s")
    assert result.exit_code == 1
    assert "b.yaml" in result.output and "c.yaml" in result.output
    assert services.store.list_cases() == [] and services.store.list_case_sets() == []
    assert sum(r.levelno == logging.ERROR for r in caplog.records) == 2


def test_git_show_failure_refused_naming_commit(
    bug_repo: BuiltBugRepo, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def handler(call: RunnerCall) -> ProcessResult:
        if "show" in call.argv:
            return failed(call.argv, stderr="fatal: bad object")
        return SubprocessRunner().run(call.argv, cwd=call.cwd, timeout=call.timeout)

    services = fake_services(tmp_path, ScriptedRunner(handler))
    with caplog.at_level(logging.ERROR):
        result = invoke_recall(services, "cases", "add", str(bug_repo.case_file), "--set", "s")
    assert result.exit_code == 1
    assert f"proof commit {bug_repo.fix} failed" in result.output
    assert services.store.list_cases() == []
    assert any(bug_repo.fix in r.getMessage() for r in caplog.records if r.levelno == logging.ERROR)
