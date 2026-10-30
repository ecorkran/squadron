"""run_audit_series: the shared variance loop, driven by a fake audit callable."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from squadron.metrology.audit import (
    AuditPreflightError,
    AuditProgress,
    AuditRunFailure,
    AuditRunResult,
)
from squadron.metrology.audit_series import (
    AuditSeriesRequest,
    NoFloorReason,
    run_audit_series,
)
from squadron.metrology.store import MetrologyStore
from tests.metrology.conftest import make_audit_finding, make_audit_run

PINNED_SHA = "c" * 40


@dataclass
class RecordingObserver:
    events: list[str] = field(default_factory=lambda: [])

    def on_run_start(self, run_number: int) -> None:
        self.events.append(f"start:{run_number}")

    def on_cooldown(self, run_number: int, cooldown_s: int) -> None:
        self.events.append(f"cooldown:{run_number}:{cooldown_s}")

    def on_outcome(self, run_number: int, outcome: AuditRunResult) -> None:
        self.events.append(f"outcome:{run_number}:{'ok' if outcome.succeeded else 'failed'}")

    def progress_callback(self, run_number: int) -> Callable[[AuditProgress], None] | None:
        return None


@dataclass
class FakeAudit:
    """Scripted audit: ``script[i]`` is 'ok', a failure, or an exception for call i."""

    store: MetrologyStore
    script: list[AuditRunFailure | Exception | None]
    expected_shas: list[str | None] = field(default_factory=lambda: [])

    async def __call__(self, project_path: Path, **kwargs: object) -> AuditRunResult:
        call_index = len(self.expected_shas)
        self.expected_shas.append(kwargs.get("expected_sha"))  # type: ignore[arg-type]
        assert kwargs["independent_run"] is True
        assert kwargs["require_clean"] is True
        step = self.script[call_index]
        if isinstance(step, Exception):
            raise step
        if step is not None:
            return AuditRunResult(project_path=project_path, failure=step, detail="scripted")
        run = make_audit_run(
            run_id=f"audit-20260726-{call_index:08d}",
            commit_sha=PINNED_SHA,
            findings=[make_audit_finding(finding_id=f"F{i:03d}") for i in range(call_index + 3)],
        )
        self.store.write_audit_run(run)
        return AuditRunResult(project_path=project_path, run=run)


@pytest.fixture
def store(tmp_path: Path) -> MetrologyStore:
    return MetrologyStore(store_dir=tmp_path / "store")


def _request(tmp_path: Path, *, runs: int = 3, expected_sha: str | None = None) -> AuditSeriesRequest:
    return AuditSeriesRequest(
        project_path=tmp_path,
        runs=runs,
        cooldown_s=0,
        profile=None,
        model=None,
        expected_sha=expected_sha,
        config_cwd=str(tmp_path),
    )


def test_success_writes_one_floor_and_pins_sha_from_run_one(
    store: MetrologyStore, tmp_path: Path
) -> None:
    audit = FakeAudit(store, [None, None, None])
    observer = RecordingObserver()

    result = run_audit_series(
        _request(tmp_path, expected_sha=PINNED_SHA), store=store, observer=observer, audit=audit
    )

    assert result.floor is not None
    assert result.floor.n_runs == 3
    assert result.failed == 0
    assert result.no_floor_reason is None
    assert audit.expected_shas == [PINNED_SHA] * 3
    assert len(store.list_noise_floors()) == 1
    assert observer.events == [
        "start:1",
        "outcome:1:ok",
        "start:2",
        "outcome:2:ok",
        "start:3",
        "outcome:3:ok",
    ]


def test_unpinned_series_pins_to_the_first_successful_run(
    store: MetrologyStore, tmp_path: Path
) -> None:
    audit = FakeAudit(store, [None, None])

    run_audit_series(_request(tmp_path, runs=2), store=store, observer=RecordingObserver(), audit=audit)

    assert audit.expected_shas == [None, PINNED_SHA]


def test_failed_run_in_the_middle_is_counted_and_floor_uses_the_rest(
    store: MetrologyStore, tmp_path: Path
) -> None:
    audit = FakeAudit(store, [None, AuditRunFailure.STREAM_ERROR, None])

    result = run_audit_series(
        _request(tmp_path), store=store, observer=RecordingObserver(), audit=audit
    )

    assert result.failed == 1
    assert len(result.runs) == 2
    assert result.floor is not None
    assert result.floor.n_runs == 2


def test_rate_limit_stops_the_series(store: MetrologyStore, tmp_path: Path) -> None:
    audit = FakeAudit(store, [None, AuditRunFailure.RATE_LIMITED, None])

    result = run_audit_series(
        _request(tmp_path), store=store, observer=RecordingObserver(), audit=audit
    )

    assert result.rate_limited is True
    assert len(audit.expected_shas) == 2, "run 3 must not start after a rate limit"
    assert result.failed == 1
    assert result.floor is None
    assert result.no_floor_reason is NoFloorReason.TOO_FEW_RUNS


def test_too_few_runs_gives_no_floor_and_keeps_the_runs(store: MetrologyStore, tmp_path: Path) -> None:
    audit = FakeAudit(store, [None, AuditRunFailure.TIMEOUT, AuditRunFailure.TIMEOUT])

    result = run_audit_series(
        _request(tmp_path), store=store, observer=RecordingObserver(), audit=audit
    )

    assert result.floor is None
    assert result.no_floor_reason is NoFloorReason.TOO_FEW_RUNS
    assert result.failed == 2
    assert store.list_noise_floors() == []
    assert len(store.list_audit_runs()) == 1, "the usable run stays persisted"


def test_moved_head_sets_stop_error_and_never_calls_run_three(
    store: MetrologyStore, tmp_path: Path
) -> None:
    audit = FakeAudit(store, [None, AuditPreflightError("HEAD moved: a != b"), None])

    result = run_audit_series(
        _request(tmp_path), store=store, observer=RecordingObserver(), audit=audit
    )

    assert result.stop_error == "HEAD moved: a != b"
    assert len(audit.expected_shas) == 2
    assert result.failed == 2, "the failed run and the unattempted run 3 both count"
    assert result.floor is None


def test_cooldown_is_announced_between_runs_not_before_the_first(
    store: MetrologyStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slept: list[float] = []
    monkeypatch.setattr("squadron.metrology.audit_series.time.sleep", slept.append)
    request = AuditSeriesRequest(
        project_path=tmp_path,
        runs=2,
        cooldown_s=7,
        profile=None,
        model=None,
        expected_sha=None,
        config_cwd=str(tmp_path),
    )
    observer = RecordingObserver()

    run_audit_series(request, store=store, observer=observer, audit=FakeAudit(store, [None, None]))

    assert slept == [7]
    assert observer.events[:3] == ["start:1", "outcome:1:ok", "cooldown:2:7"]
