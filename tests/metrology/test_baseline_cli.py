"""``sq metrology baseline`` CLI tests (slice 404). No real audit agent, no user store."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.metrology.audit import AuditPreflightError, AuditRunFailure, AuditRunResult
from squadron.metrology.errors import MetrologyStoreError, SnapshotIntegrityError
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.snapshot.contract import AdapterRegistry
from squadron.metrology.snapshot_models import SnapshotMetric, SourceLanguage
from squadron.metrology.store import MetrologyStore
from tests.conftest import run_test_git
from tests.metrology.conftest import make_audit_finding, make_audit_run
from tests.metrology.snapshot.builders import FakeAdapter

runner = CliRunner()

UserConfigWriter = Callable[[dict[str, object]], Path]

CONFIG: dict[str, object] = {
    "metrology.audit_model": "model-x",
    "metrology.audit_profile": "profile-x",
    "metrology.audit_run_cooldown_s": 0,
}
PROJECT = ProjectId(value="github.com/manta/example-repo", source=ProjectIdSource.REMOTE)
MARKER = "FAKE-AUDIT-STARTED"


def fake_registry() -> AdapterRegistry:
    return {
        SourceLanguage.PYTHON: FakeAdapter(
            SourceLanguage.PYTHON, frozenset({SnapshotMetric.FILE_LENGTH})
        )
    }


@dataclass
class FakeAudit:
    """Scripted ``run_audit``: each call takes the next step (None = success)."""

    store: MetrologyStore
    repo: Path
    script: list[AuditRunFailure | BaseException | None]
    analysis_file: str | None = None
    calls: int = 0
    shas: list[str | None] = field(default_factory=lambda: [])

    async def __call__(self, project_path: Path, **kwargs: object) -> AuditRunResult:
        if self.calls == 0:
            typer.echo(MARKER)
            if self.analysis_file is not None:
                target = self.repo / self.analysis_file
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("# audit\n", encoding="utf-8")
        step = self.script[self.calls] if self.calls < len(self.script) else None
        self.calls += 1
        self.shas.append(str(kwargs.get("expected_sha")))
        if isinstance(step, BaseException):
            raise step
        if step is not None:
            return AuditRunResult(
                project_path=project_path, failure=step, detail=f"scripted {step.value}"
            )
        run = make_audit_run(
            run_id=f"audit-20261030-{self.calls:08d}",
            commit_sha=_head(self.repo),
            findings=[make_audit_finding(finding_id=f"F{i:03d}") for i in range(self.calls + 2)],
        )
        self.store.write_audit_run(run)
        return AuditRunResult(project_path=project_path, run=run)


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


@dataclass
class Harness:
    store_dir: Path
    store: MetrologyStore

    def audit(
        self,
        repo: Path,
        *script: AuditRunFailure | BaseException | None,
        analysis_file: str | None = None,
    ) -> FakeAudit:
        return FakeAudit(self.store, repo, list(script), analysis_file=analysis_file)

    def is_empty(self) -> bool:
        return not self.store_dir.exists() or not any(self.store_dir.iterdir())


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    store_dir = tmp_path / "baseline-store"
    with (
        patch("squadron.cli.commands.metrology_baseline.resolve_store_dir", return_value=store_dir),
        patch("squadron.cli.commands.metrology_baseline.default_registry", fake_registry),
    ):
        yield Harness(store_dir, MetrologyStore(store_dir=store_dir))


def _invoke(repo: Path, audit: FakeAudit, *extra: str) -> tuple[int, str]:
    with patch("squadron.cli.commands.metrology_baseline.run_audit", audit):
        result = runner.invoke(app, ["metrology", "baseline", str(repo), *extra])
    return result.exit_code, " ".join(result.output.split())


def test_success_snapshots_then_runs_three_audits_and_writes_one_floor(
    audited_repo: Path, harness: Harness, write_user_config: UserConfigWriter
) -> None:
    write_user_config(CONFIG)
    assert not (audited_repo / ".squadron.toml").exists()
    assert not (audited_repo / "project-documents").exists()
    audit = harness.audit(audited_repo)

    code, output = _invoke(audited_repo, audit)

    assert code == 0, output
    head = _head(audited_repo)
    snapshots = harness.store.list_snapshots(PROJECT)
    assert [snapshot.commit_sha for snapshot in snapshots] == [head]
    runs = harness.store.list_audit_runs()
    assert len(runs) == 3
    assert {run.project_id.value for run in runs} == {PROJECT.value}
    assert {run.commit_sha for run in runs} == {head}
    floors = harness.store.list_noise_floors()
    assert len(floors) == 1
    assert floors[0][1].commit_sha == head
    assert audit.shas == [head] * 3, "every run is pinned to the snapshot's commit"
    assert output.index("Scope:") < output.index(MARKER), "scope is printed before any audit"
    assert output.index("Snapshot") < output.index(MARKER)
    assert "3 succeeded, 0 failed, 1 floor(s) written" in output
    assert f"Next: sq metrology report baseline --project {PROJECT.value}" in output


def _break_no_model(_: Path, config: UserConfigWriter) -> None:
    config({"metrology.audit_profile": "profile-x"})


def _break_no_profile(_: Path, config: UserConfigWriter) -> None:
    config({"metrology.audit_model": "model-x"})


def _break_one_run(_: Path, config: UserConfigWriter) -> None:
    config({**CONFIG, "metrology.audit_variance_runs": 1})


def _break_dirty_tree(repo: Path, config: UserConfigWriter) -> None:
    config(CONFIG)
    (repo / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")


@pytest.mark.parametrize(
    ("break_setup", "cause"),
    [
        (_break_no_model, "metrology.audit_model"),
        (_break_no_profile, "provider profile"),
        (_break_one_run, "metrology.audit_variance_runs"),
        (_break_dirty_tree, "scratch.txt"),
    ],
)
def test_preflight_failure_exits_one_naming_the_cause_and_touches_nothing(
    audited_repo: Path,
    harness: Harness,
    write_user_config: UserConfigWriter,
    break_setup: Callable[[Path, UserConfigWriter], None],
    cause: str,
) -> None:
    break_setup(audited_repo, write_user_config)
    audit = harness.audit(audited_repo)

    code, output = _invoke(audited_repo, audit)

    assert code == 1
    assert cause in output
    assert harness.is_empty()
    assert audit.calls == 0


def test_no_remote_exits_one_naming_the_identity_fix(
    repo_no_remote: Path, harness: Harness, write_user_config: UserConfigWriter
) -> None:
    write_user_config(CONFIG)
    (repo_no_remote / "README.md").write_text("# x\n", encoding="utf-8")
    run_test_git(repo_no_remote, "add", "-A")
    run_test_git(repo_no_remote, "commit", "-q", "-m", "initial")
    audit = harness.audit(repo_no_remote)

    code, output = _invoke(repo_no_remote, audit)

    assert code == 1
    assert "metrology.project_id" in output
    assert harness.is_empty()
    assert audit.calls == 0


def test_snapshot_failure_exits_one_before_any_audit(
    audited_repo: Path, harness: Harness, write_user_config: UserConfigWriter
) -> None:
    write_user_config(CONFIG)
    audit = harness.audit(audited_repo)
    failure = SnapshotIntegrityError("repo changed during measurement")

    with patch("squadron.cli.commands.metrology_baseline.take_snapshot", side_effect=failure):
        code, output = _invoke(audited_repo, audit)

    assert code == 1
    assert "repo changed during measurement" in output
    assert audit.calls == 0
    assert harness.is_empty()


def test_timed_out_run_is_printed_with_detail_and_the_floor_is_still_written(
    audited_repo: Path, harness: Harness, write_user_config: UserConfigWriter
) -> None:
    write_user_config(CONFIG)
    audit = harness.audit(audited_repo, None, AuditRunFailure.TIMEOUT, None)

    code, output = _invoke(audited_repo, audit)

    assert code == 0, output
    assert "timeout: scripted timeout" in output
    assert "2 succeeded, 1 failed, 1 floor(s) written" in output
    assert len(harness.store.list_noise_floors()) == 1


def test_rate_limit_stops_the_series_without_a_floor(
    audited_repo: Path, harness: Harness, write_user_config: UserConfigWriter
) -> None:
    write_user_config(CONFIG)
    audit = harness.audit(audited_repo, None, AuditRunFailure.RATE_LIMITED, None)

    code, output = _invoke(audited_repo, audit)

    assert code == 1
    assert audit.calls == 2, "no run starts after a rate limit"
    assert "provider is rate limiting" in output
    assert f"sq metrology audit variance {audited_repo}" in output
    assert harness.store.list_noise_floors() == []
    assert len(harness.store.list_snapshots(PROJECT)) == 1, "the snapshot is kept"
    assert len(harness.store.list_audit_runs()) == 1, "the completed run is kept"


def test_moved_head_fails_the_remaining_runs_and_names_the_error(
    audited_repo: Path, harness: Harness, write_user_config: UserConfigWriter
) -> None:
    write_user_config(CONFIG)
    moved = AuditPreflightError("HEAD moved from aaa to bbb")
    audit = harness.audit(audited_repo, None, moved, None)

    code, output = _invoke(audited_repo, audit)

    assert code == 1
    assert audit.calls == 2
    assert "Error: HEAD moved from aaa to bbb" in output
    assert f"sq metrology audit variance {audited_repo}" in output
    assert harness.store.list_noise_floors() == []


def test_floor_written_beside_a_stop_error_still_names_the_cause(
    audited_repo: Path, harness: Harness, write_user_config: UserConfigWriter
) -> None:
    """Runs 1-2 succeed and run 3 finds HEAD moved: the floor stands, the cause is shown."""
    write_user_config(CONFIG)
    audit = harness.audit(audited_repo, None, None, AuditPreflightError("HEAD moved from a to b"))

    code, output = _invoke(audited_repo, audit)

    assert code == 0, output
    assert "Error: HEAD moved from a to b" in output
    assert "2 succeeded, 1 failed, 1 floor(s) written" in output
    assert len(harness.store.list_noise_floors()) == 1


def test_floor_written_beside_a_rate_limit_still_says_so(
    audited_repo: Path, harness: Harness, write_user_config: UserConfigWriter
) -> None:
    write_user_config(CONFIG)
    audit = harness.audit(audited_repo, None, None, AuditRunFailure.RATE_LIMITED)

    code, output = _invoke(audited_repo, audit)

    assert code == 0, output
    assert "provider is rate limiting" in output
    assert len(harness.store.list_noise_floors()) == 1


def test_too_few_usable_runs_exits_one_and_keeps_them(
    audited_repo: Path, harness: Harness, write_user_config: UserConfigWriter
) -> None:
    write_user_config(CONFIG)
    audit = harness.audit(
        audited_repo, None, AuditRunFailure.STREAM_ERROR, AuditRunFailure.STREAM_ERROR
    )

    code, output = _invoke(audited_repo, audit)

    assert code == 1
    assert "No floor: 1 usable run(s); 2 are required" in output
    assert f"sq metrology audit variance {audited_repo}" in output
    assert len(harness.store.list_audit_runs()) == 1
    assert harness.store.list_noise_floors() == []


ANALYSIS_FILE = "analysis/940-analysis.example-repo.md"


def test_success_names_the_analysis_file_to_remove_or_commit(
    audited_repo: Path, harness: Harness, write_user_config: UserConfigWriter
) -> None:
    write_user_config(CONFIG)
    audit = harness.audit(audited_repo, analysis_file=ANALYSIS_FILE)

    code, output = _invoke(audited_repo, audit)

    assert code == 0, output
    assert f"The audit wrote {ANALYSIS_FILE}. Remove or commit it before the next snapshot." in output


def test_interrupt_on_run_two_keeps_what_was_measured_and_exits_130(
    audited_repo: Path, harness: Harness, write_user_config: UserConfigWriter
) -> None:
    write_user_config(CONFIG)
    audit = harness.audit(audited_repo, None, KeyboardInterrupt(), analysis_file=ANALYSIS_FILE)

    code, output = _invoke(audited_repo, audit)

    snapshot = harness.store.list_snapshots(PROJECT)[0]
    assert code == 130
    assert f"Snapshot {snapshot.snapshot_id} is kept; 1 run(s) completed." in output
    assert f"sq metrology audit variance {audited_repo}" in output
    assert ANALYSIS_FILE in output
    assert len(harness.store.list_audit_runs()) == 1
    assert harness.store.list_noise_floors() == []


def test_interrupt_during_the_snapshot_says_nothing_was_recorded(
    audited_repo: Path, harness: Harness, write_user_config: UserConfigWriter
) -> None:
    write_user_config(CONFIG)
    audit = harness.audit(audited_repo)

    with patch("squadron.cli.commands.metrology_baseline.take_snapshot", side_effect=KeyboardInterrupt):
        code, output = _invoke(audited_repo, audit)

    assert code == 130
    assert "Nothing was recorded or spent" in output
    assert audit.calls == 0
    assert harness.is_empty()


def test_floor_write_failure_logs_error_and_names_the_store_and_recovery(
    audited_repo: Path,
    harness: Harness,
    write_user_config: UserConfigWriter,
    caplog: pytest.LogCaptureFixture,
) -> None:
    write_user_config(CONFIG)
    audit = harness.audit(audited_repo, analysis_file=ANALYSIS_FILE)
    failure = MetrologyStoreError("disk full")

    with (
        caplog.at_level(logging.ERROR),
        patch.object(MetrologyStore, "write_noise_floor", side_effect=failure),
    ):
        code, output = _invoke(audited_repo, audit)

    assert code == 1
    assert "Store error: disk full" in output
    assert f"Store: {harness.store_dir}; 3 run(s) persisted this session." in output
    assert f"sq metrology audit variance {audited_repo}" in output
    assert ANALYSIS_FILE in output
    assert any(
        record.levelno == logging.ERROR and record.exc_info is not None for record in caplog.records
    )
