"""Liveness assessment (slice 174 D3) and the process check."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta

import pytest

from squadron.pipeline.run_liveness import (
    STALE_HEARTBEAT_INTERVALS,
    RunLiveness,
    assess_liveness,
    process_alive,
)
from squadron.pipeline.state import RUNNING_STATUS, RunOwner, RunState
from tests.pipeline.liveness_support import exited_pid

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
HOST = "this-host"
INTERVAL_S = 30
OVERDUE = timedelta(seconds=STALE_HEARTBEAT_INTERVALS * INTERVAL_S + 1)


def _state(
    *,
    owner_host: str | None = HOST,
    heartbeat_age: timedelta = timedelta(seconds=5),
    status: str = RUNNING_STATUS,
) -> RunState:
    owner = (
        None
        if owner_host is None
        else RunOwner(
            pid=4242,
            hostname=owner_host,
            claimed_at=NOW - timedelta(hours=1),
            heartbeat_interval_s=INTERVAL_S,
        )
    )
    return RunState(
        run_id="run-x",
        pipeline="p",
        params={},
        started_at=NOW - timedelta(hours=2),
        updated_at=NOW,
        status=status,
        owner=owner,
        heartbeat_at=NOW - heartbeat_age,
        progress_at=NOW - timedelta(seconds=40),
    )


def _assess(state: RunState, alive: bool | None) -> RunLiveness | None:
    result = assess_liveness(state, now=NOW, hostname=HOST, process_alive=lambda _pid: alive)
    return None if result is None else result.liveness


class TestAssessLiveness:
    def test_same_host_process_gone_is_orphaned(self) -> None:
        assert _assess(_state(), alive=False) is RunLiveness.ORPHANED

    def test_orphaned_wins_over_overdue_heartbeat(self) -> None:
        assert _assess(_state(heartbeat_age=OVERDUE), alive=False) is RunLiveness.ORPHANED

    def test_process_alive_with_overdue_heartbeat_is_stale(self) -> None:
        assert _assess(_state(heartbeat_age=OVERDUE), alive=True) is RunLiveness.STALE

    def test_process_alive_with_fresh_heartbeat_is_live(self) -> None:
        assert _assess(_state(), alive=True) is RunLiveness.LIVE

    def test_other_host_fresh_heartbeat_is_live_without_a_process_check(self) -> None:
        checked: list[int] = []

        def check(pid: int) -> bool:
            checked.append(pid)
            return False

        result = assess_liveness(
            _state(owner_host="other-host"), now=NOW, hostname=HOST, process_alive=check
        )

        assert result is not None and result.liveness is RunLiveness.LIVE
        assert checked == []

    def test_other_host_overdue_heartbeat_is_stale(self) -> None:
        state = _state(owner_host="other-host", heartbeat_age=OVERDUE)
        assert _assess(state, alive=False) is RunLiveness.STALE

    def test_no_owner_is_unowned(self) -> None:
        assert _assess(_state(owner_host=None), alive=False) is RunLiveness.UNOWNED

    def test_unknown_process_falls_through_to_heartbeat(self) -> None:
        assert _assess(_state(), alive=None) is RunLiveness.LIVE
        assert _assess(_state(heartbeat_age=OVERDUE), alive=None) is RunLiveness.STALE

    def test_not_running_is_not_assessed(self) -> None:
        assert _assess(_state(status="paused"), alive=False) is None

    def test_durations(self) -> None:
        result = assess_liveness(_state(), now=NOW, hostname=HOST, process_alive=lambda _: True)

        assert result is not None
        assert result.elapsed == timedelta(hours=1)
        assert result.progress_age == timedelta(seconds=40)
        assert result.heartbeat_age == timedelta(seconds=5)


class TestProcessAlive:
    def test_exited_process_is_gone(self) -> None:
        assert process_alive(exited_pid()) is False

    def test_own_process_is_alive(self) -> None:
        assert process_alive(os.getpid()) is True

    @pytest.mark.parametrize("pid", [0, -1])
    def test_non_positive_pid_is_unknown(self, pid: int, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="squadron.pipeline.run_liveness"):
            assert process_alive(pid) is None
        assert any(str(pid) in r.getMessage() for r in caplog.records)
