"""Orchestrator tests with fake adapters and a fake runner (slice 400, Data Flow)."""

from __future__ import annotations

import logging
from collections.abc import Sequence

import pytest

from squadron.metrology.errors import (
    MetrologyIdentityError,
    SnapshotAdapterContractError,
    SnapshotIntegrityError,
    SnapshotPreflightError,
)
from squadron.metrology.snapshot.contract import AdapterContext
from squadron.metrology.snapshot.take import take_snapshot
from squadron.metrology.snapshot_models import (
    AbsenceReason,
    EnvironmentIdentity,
    Measurement,
    RuleSetIdentity,
    SnapshotMetric,
    SourceLanguage,
    ToolIdentity,
)
from squadron.metrology.store import MetrologyStore
from tests.metrology.snapshot.builders import make_project_id
from tests.metrology.snapshot.conftest import FakeToolRunner, SnapshotRepoFactory

TOOL = ToolIdentity(name="fake", version="1.0", counting="fake counting")


def present(metric: SnapshotMetric, language: SourceLanguage) -> Measurement:
    return Measurement(
        metric=metric,
        language=language,
        tool=TOOL,
        rule_set=RuleSetIdentity(source="fake.toml", content_hash="a" * 64),
        environment=EnvironmentIdentity(
            lockfile_path="uv.lock", lockfile_sha256="b" * 64, interpreter_version="3.12"
        ),
    )


class FakeAdapter:
    """Declares ``metrics``; returns ``reports`` (default: one present measurement each)."""

    def __init__(
        self,
        language: SourceLanguage,
        metrics: frozenset[SnapshotMetric],
        *,
        reports: list[SnapshotMetric] | None = None,
        convention_exclusions: tuple[str, ...] = (),
        write_into_repo: str | None = None,
    ) -> None:
        self.language = language
        self.metrics = metrics
        self.convention_exclusions = convention_exclusions
        self._reports = reports if reports is not None else sorted(metrics, key=lambda m: m.value)
        self._write_into_repo = write_into_repo
        self.calls: list[tuple[AdapterContext, list[str]]] = []

    def measure(self, ctx: AdapterContext, files: Sequence[str]) -> list[Measurement]:
        self.calls.append((ctx, list(files)))
        if self._write_into_repo is not None:
            (ctx.repo_root / self._write_into_repo).write_text("written\n", encoding="utf-8")
        return [present(metric, self.language) for metric in self._reports]


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
