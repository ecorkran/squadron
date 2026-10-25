"""Orchestrator tests with fake adapters and a fake runner (slice 400, Data Flow)."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from squadron.metrology.errors import (
    MetrologyIdentityError,
    SnapshotAdapterContractError,
    SnapshotIntegrityError,
    SnapshotPreflightError,
)
from squadron.metrology.snapshot.contract import ToolResult
from squadron.metrology.snapshot.registry import default_registry
from squadron.metrology.snapshot.take import take_snapshot
from squadron.metrology.snapshot_models import (
    AbsenceReason,
    CodeSnapshot,
    Measurement,
    SnapshotMetric,
    SourceLanguage,
)
from squadron.metrology.store import MetrologyStore
from tests.conftest import run_test_git
from tests.metrology.snapshot.builders import FakeAdapter, make_project_id
from tests.metrology.snapshot.conftest import FakeToolRunner, SnapshotRepoFactory

ALL_METRICS = frozenset(SnapshotMetric)
FILES = {"a.py": "x = 1\n", "b.ts": "const y = 1;\n", "run.sh": "echo hi\n"}


def test_language_without_an_adapter_gets_every_metric_absent(
    snapshot_git_repo: SnapshotRepoFactory, snapshot_store: MetrologyStore
) -> None:
    repo = snapshot_git_repo(FILES)

    snapshot = take_snapshot(repo, {}, FakeToolRunner(), snapshot_store)

    shell = next(entry for entry in snapshot.languages if entry.language is SourceLanguage.SHELL)
    assert shell.adapter is None
    assert shell.file_count == 1
    assert {m.metric for m in shell.measurements} == set(SnapshotMetric)
    assert all(m.absent is AbsenceReason.NO_ADAPTER for m in shell.measurements)


def test_adapter_declaring_a_subset_gets_metric_unsupported_for_the_rest(
    snapshot_git_repo: SnapshotRepoFactory, snapshot_store: MetrologyStore
) -> None:
    repo = snapshot_git_repo(FILES)
    subset = frozenset({SnapshotMetric.FILE_LENGTH, SnapshotMetric.LINT_COUNT})
    registry = {SourceLanguage.TYPESCRIPT: FakeAdapter(SourceLanguage.TYPESCRIPT, subset)}

    snapshot = take_snapshot(repo, registry, FakeToolRunner(), snapshot_store)

    typescript = next(e for e in snapshot.languages if e.language is SourceLanguage.TYPESCRIPT)
    by_metric = {m.metric: m for m in typescript.measurements}
    assert by_metric[SnapshotMetric.FILE_LENGTH].absent is None
    assert by_metric[SnapshotMetric.LINT_COUNT].absent is None
    for metric in (SnapshotMetric.FUNCTION_LENGTH, SnapshotMetric.TYPE_ERRORS):
        assert by_metric[metric].absent is AbsenceReason.METRIC_UNSUPPORTED
        assert by_metric[metric].absent_detail


def test_every_snapshot_metric_appears_for_every_language_present(
    snapshot_git_repo: SnapshotRepoFactory, snapshot_store: MetrologyStore
) -> None:
    """Guards 401: a new enum member shows up as metric_unsupported, not as a gap."""
    repo = snapshot_git_repo(FILES)
    registry = {
        SourceLanguage.PYTHON: FakeAdapter(
            SourceLanguage.PYTHON, frozenset({SnapshotMetric.FILE_LENGTH})
        )
    }

    snapshot = take_snapshot(repo, registry, FakeToolRunner(), snapshot_store)

    assert {e.language for e in snapshot.languages} == {
        SourceLanguage.PYTHON,
        SourceLanguage.TYPESCRIPT,
        SourceLanguage.SHELL,
    }
    for entry in snapshot.languages:
        assert {m.metric for m in entry.measurements} == set(SnapshotMetric)


@pytest.mark.parametrize(
    "reports",
    [
        [SnapshotMetric.FILE_LENGTH, SnapshotMetric.LINT_COUNT],  # undeclared metric
        [],  # omits the declared metric
        [SnapshotMetric.FILE_LENGTH, SnapshotMetric.FILE_LENGTH],  # duplicate
    ],
)
def test_adapter_breaking_the_contract_raises_and_writes_nothing(
    snapshot_git_repo: SnapshotRepoFactory,
    snapshot_store: MetrologyStore,
    reports: list[SnapshotMetric],
) -> None:
    repo = snapshot_git_repo({"a.py": "x = 1\n"})
    adapter = FakeAdapter(
        SourceLanguage.PYTHON, frozenset({SnapshotMetric.FILE_LENGTH}), reports=reports
    )

    with pytest.raises(SnapshotAdapterContractError):
        take_snapshot(repo, {SourceLanguage.PYTHON: adapter}, FakeToolRunner(), snapshot_store)

    assert not list(snapshot_store.store_dir.glob("*.json"))


def test_adapter_that_writes_into_the_repo_fails_integrity_and_writes_nothing(
    snapshot_git_repo: SnapshotRepoFactory, snapshot_store: MetrologyStore
) -> None:
    repo = snapshot_git_repo({"a.py": "x = 1\n"})
    adapter = FakeAdapter(
        SourceLanguage.PYTHON,
        frozenset({SnapshotMetric.FILE_LENGTH}),
        write_into_repo="scratch.cache",
    )

    with pytest.raises(SnapshotIntegrityError, match=r"scratch\.cache"):
        take_snapshot(repo, {SourceLanguage.PYTHON: adapter}, FakeToolRunner(), snapshot_store)

    assert not list(snapshot_store.store_dir.glob("*.json"))


def test_dirty_tree_is_refused_before_any_adapter_runs(
    snapshot_git_repo: SnapshotRepoFactory, snapshot_store: MetrologyStore
) -> None:
    repo = snapshot_git_repo({"a.py": "x = 1\n"})
    (repo / "untracked.txt").write_text("x\n", encoding="utf-8")
    adapter = FakeAdapter(SourceLanguage.PYTHON, frozenset({SnapshotMetric.FILE_LENGTH}))

    with pytest.raises(SnapshotPreflightError):
        take_snapshot(repo, {SourceLanguage.PYTHON: adapter}, FakeToolRunner(), snapshot_store)

    assert adapter.calls == []
    assert not list(snapshot_store.store_dir.glob("*.json"))


def test_two_runs_on_one_commit_leave_one_record_and_identical_json(
    snapshot_git_repo: SnapshotRepoFactory, snapshot_store: MetrologyStore
) -> None:
    repo = snapshot_git_repo(FILES)
    registry = {
        SourceLanguage.PYTHON: FakeAdapter(
            SourceLanguage.PYTHON, frozenset({SnapshotMetric.FILE_LENGTH})
        )
    }

    first = take_snapshot(repo, registry, FakeToolRunner(), snapshot_store)
    second = take_snapshot(repo, registry, FakeToolRunner(), snapshot_store)

    assert len(list(snapshot_store.store_dir.glob("*.json"))) == 1
    assert len(snapshot_store.list_snapshots(make_project_id("github.com/manta/example-repo"))) == 1
    dump_first = first.model_dump(mode="json", exclude={"measured_at"})
    dump_second = second.model_dump(mode="json", exclude={"measured_at"})
    assert dump_first == dump_second


def test_each_language_logs_an_info_line_before_measuring(
    snapshot_git_repo: SnapshotRepoFactory,
    snapshot_store: MetrologyStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    repo = snapshot_git_repo(FILES)

    with caplog.at_level(logging.INFO, logger="squadron.metrology.snapshot.take"):
        take_snapshot(repo, {}, FakeToolRunner(), snapshot_store)

    lines = [r.getMessage() for r in caplog.records if r.name.endswith("snapshot.take")]
    assert len(lines) == 3
    for language in ("python", "typescript", "shell"):
        assert any(language in line for line in lines)


def test_adapter_receives_only_its_language_files_less_exclusions(
    snapshot_git_repo: SnapshotRepoFactory, snapshot_store: MetrologyStore
) -> None:
    repo = snapshot_git_repo(
        {"a.py": "x\n", "gen/b_pb2.py": "y\n", "vendor/c.py": "z\n", "t.ts": "q\n"}
    )
    adapter = FakeAdapter(
        SourceLanguage.PYTHON,
        frozenset({SnapshotMetric.FILE_LENGTH}),
        convention_exclusions=("**/*_pb2.py",),
    )
    (repo / ".squadron.toml").write_text(
        '"metrology.snapshot_exclude" = "vendor/**"\n', encoding="utf-8"
    )

    snapshot = take_snapshot(repo, {SourceLanguage.PYTHON: adapter}, FakeToolRunner(), snapshot_store)

    assert adapter.calls[0][1] == ["a.py"]
    assert snapshot.exclusions == ["**/*_pb2.py", "vendor/**"]


def test_missing_project_identity_propagates_unchanged(
    snapshot_git_repo: SnapshotRepoFactory, snapshot_store: MetrologyStore
) -> None:
    repo = snapshot_git_repo({"a.py": "x\n"}, remote=None)

    with pytest.raises(MetrologyIdentityError, match="metrology.project_id"):
        take_snapshot(repo, {}, FakeToolRunner(), snapshot_store)


# --- 401: coverage through the real adapters -------------------------------------------

REPORT = "cov.xml"
COVERAGE_METRICS = (SnapshotMetric.COVERABLE_LINES, SnapshotMetric.COVERED_LINES)
COVERAGE_FILES = {
    "a.py": "x = 1\ny = 2\n",
    "b.ts": "const y = 1;\n",
    ".gitignore": f"{REPORT}\n",
}


class UnscriptedToolsFail:
    """A runner whose every tool call fails, so lint and type metrics are ``tool_failed``.

    These tests are about coverage, not lint: what matters is that the real adapters run.
    """

    def run(self, argv: Sequence[str], *, cwd: Path, timeout_s: int) -> ToolResult:
        return ToolResult(exit_code=2, stdout="", stderr="not available in this test", timed_out=False)


def cobertura(repo: Path) -> str:
    return (
        '<coverage version="9.9"><sources>'
        f"<source>{repo}</source></sources><packages><package><classes>"
        '<class filename="a.py"><lines><line number="1" hits="1"/>'
        '<line number="2" hits="0"/></lines></class>'
        '<class filename="b.ts"><lines><line number="1" hits="1"/></lines></class>'
        "</classes></package></packages></coverage>"
    )


def write_report_after_commit(repo: Path) -> Path:
    report = repo / REPORT
    report.write_text(cobertura(repo), encoding="utf-8")
    later = report.stat().st_mtime_ns + 10_000_000_000
    os.utime(report, ns=(later, later))
    return report


def real_snapshot(repo: Path, store: MetrologyStore) -> CodeSnapshot:
    return take_snapshot(repo, default_registry(), UnscriptedToolsFail(), store)


def coverage_of(snapshot: CodeSnapshot, language: SourceLanguage) -> dict[SnapshotMetric, Measurement]:
    entry = next(e for e in snapshot.languages if e.language is language)
    return {m.metric: m for m in entry.measurements if m.metric in COVERAGE_METRICS}


def test_fresh_report_gives_present_coverage_for_both_languages(
    snapshot_git_repo: SnapshotRepoFactory,
    snapshot_store: MetrologyStore,
    write_project_config: Callable[[Path, dict[str, object]], Path],
) -> None:
    repo = snapshot_git_repo(COVERAGE_FILES)
    write_project_config(repo, {"metrology.coverage_report": REPORT})
    write_report_after_commit(repo)

    snapshot = real_snapshot(repo, snapshot_store)

    python = coverage_of(snapshot, SourceLanguage.PYTHON)
    typescript = coverage_of(snapshot, SourceLanguage.TYPESCRIPT)
    assert python[SnapshotMetric.COVERABLE_LINES].per_file == {"a.py": 2}
    assert python[SnapshotMetric.COVERED_LINES].per_file == {"a.py": 1}
    assert typescript[SnapshotMetric.COVERABLE_LINES].per_file == {"b.ts": 1}
    assert typescript[SnapshotMetric.COVERED_LINES].per_file == {"b.ts": 1}


def test_missing_report_is_report_missing_with_one_warning_per_language(
    snapshot_git_repo: SnapshotRepoFactory,
    snapshot_store: MetrologyStore,
    write_project_config: Callable[[Path, dict[str, object]], Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    repo = snapshot_git_repo(COVERAGE_FILES)
    write_project_config(repo, {"metrology.coverage_report": "nope.xml"})

    with caplog.at_level(logging.WARNING):
        snapshot = real_snapshot(repo, snapshot_store)

    for language in (SourceLanguage.PYTHON, SourceLanguage.TYPESCRIPT):
        for measurement in coverage_of(snapshot, language).values():
            assert measurement.absent is AbsenceReason.REPORT_MISSING
    assert sum("nope.xml does not exist" in record.getMessage() for record in caplog.records) == 2


def test_stale_report_is_report_stale_on_both_languages(
    snapshot_git_repo: SnapshotRepoFactory,
    snapshot_store: MetrologyStore,
    write_project_config: Callable[[Path, dict[str, object]], Path],
) -> None:
    repo = snapshot_git_repo(COVERAGE_FILES)
    write_project_config(repo, {"metrology.coverage_report": REPORT})
    report = write_report_after_commit(repo)
    newer = report.stat().st_mtime_ns + 5_000_000_000
    os.utime(repo / "a.py", ns=(newer, newer))

    snapshot = real_snapshot(repo, snapshot_store)

    for language in (SourceLanguage.PYTHON, SourceLanguage.TYPESCRIPT):
        for measurement in coverage_of(snapshot, language).values():
            assert measurement.absent is AbsenceReason.REPORT_STALE
            assert measurement.absent_detail is not None
            assert "a.py" in measurement.absent_detail


def test_real_adapters_are_deterministic_read_only_and_complete(
    snapshot_git_repo: SnapshotRepoFactory,
    snapshot_store: MetrologyStore,
    write_project_config: Callable[[Path, dict[str, object]], Path],
) -> None:
    repo = snapshot_git_repo(COVERAGE_FILES)
    write_project_config(repo, {"metrology.coverage_report": REPORT})
    report = write_report_after_commit(repo)
    mtime_before = report.stat().st_mtime_ns

    first = real_snapshot(repo, snapshot_store)
    second = real_snapshot(repo, snapshot_store)

    assert first.model_dump(mode="json", exclude={"measured_at"}) == second.model_dump(
        mode="json", exclude={"measured_at"}
    )
    for entry in first.languages:
        assert {m.metric for m in entry.measurements} == set(SnapshotMetric)
    # Only the exempt project config the test wrote; the snapshot left nothing else behind.
    assert run_test_git(repo, "status", "--porcelain").strip() == "?? .squadron.toml"
    assert report.stat().st_mtime_ns == mtime_before
