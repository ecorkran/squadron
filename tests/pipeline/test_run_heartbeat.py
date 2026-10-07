"""RunHeartbeat (slice 174 D6, D13): claim, beats, cancel and failure handling."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path

import pytest

from squadron.pipeline.executor import ExecutionStatus, PipelineResult
from squadron.pipeline.run_heartbeat import RunHeartbeat
from squadron.pipeline.state import RUNNING_STATUS, RunOwner, StateManager

INTERVAL = 0.05


def _paused_run(mgr: StateManager) -> str:
    run_id = mgr.init_run("p", {})
    mgr.finalize(
        run_id, PipelineResult(pipeline_name="p", status=ExecutionStatus.PAUSED, step_results=[])
    )
    return run_id


async def _until(condition: Callable[[], bool]) -> None:
    """Poll *condition* until true; fail the test after 5 s."""
    async with asyncio.timeout(5.0):
        # Polls the state file on disk, which no asyncio.Event can signal.
        while not condition():  # noqa: ASYNC110
            await asyncio.sleep(INTERVAL / 5)


class TestRunHeartbeat:
    async def test_claim_on_enter(self, tmp_path: Path) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        run_id = _paused_run(mgr)

        async with RunHeartbeat(mgr, run_id, INTERVAL, claim=True):
            state = mgr.load(run_id)

        assert state.status == RUNNING_STATUS
        assert state.owner is not None

    async def test_heartbeats_advance_and_stop_on_exit(self, tmp_path: Path) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        run_id = mgr.init_run("p", {}, owner=RunOwner.current(1))
        seen: set[object] = set()

        def two_beats() -> bool:
            seen.add(mgr.load(run_id).heartbeat_at)
            return len(seen) >= 3  # the init_run value plus two heartbeats

        heartbeat = RunHeartbeat(mgr, run_id, INTERVAL, claim=False)
        async with heartbeat:
            await _until(two_beats)
            task = heartbeat._task  # pyright: ignore[reportPrivateUsage]

        assert task is not None and task.done()
        after_exit = mgr.load(run_id).heartbeat_at
        await asyncio.sleep(INTERVAL * 3)
        assert mgr.load(run_id).heartbeat_at == after_exit

    async def test_write_oserror_logs_warning_and_keeps_beating(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        run_id = mgr.init_run("p", {}, owner=RunOwner.current(1))

        def fail(self: StateManager, path: Path, data: str) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(StateManager, "_write_atomic", fail)
        heartbeat = RunHeartbeat(mgr, run_id, INTERVAL, claim=False)
        with caplog.at_level(logging.WARNING):
            async with heartbeat:
                await _until(lambda: sum("disk full" in r.getMessage() for r in caplog.records) >= 2)
                task = heartbeat._task  # pyright: ignore[reportPrivateUsage]
                assert task is not None and not task.done()

        assert all(
            r.levelno == logging.WARNING for r in caplog.records if "disk full" in r.getMessage()
        )

    async def test_unexpected_error_is_logged_and_heartbeat_stops(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        run_id = mgr.init_run("p", {}, owner=RunOwner.current(1))

        def broken(self: StateManager, run_id: str) -> None:
            raise TypeError("defect")

        monkeypatch.setattr(StateManager, "heartbeat", broken)
        heartbeat = RunHeartbeat(mgr, run_id, INTERVAL, claim=False)
        with caplog.at_level(logging.ERROR, logger="squadron.pipeline.run_heartbeat"):
            async with heartbeat:
                task = heartbeat._task  # pyright: ignore[reportPrivateUsage]
                assert task is not None
                await _until(task.done)
        await asyncio.sleep(0)  # done-callbacks run on the next loop iteration

        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) == 1
        assert run_id in errors[0].getMessage()
        assert errors[0].exc_info is not None


class TestCancellation:
    async def test_cancelling_the_enclosing_task_is_not_swallowed(self, tmp_path: Path) -> None:
        mgr = StateManager(runs_dir=tmp_path)
        run_id = mgr.init_run("p", {}, owner=RunOwner.current(1))

        async def body() -> None:
            async with RunHeartbeat(mgr, run_id, INTERVAL, claim=False):
                await asyncio.sleep(60)

        task = asyncio.create_task(body())
        await asyncio.sleep(INTERVAL * 2)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task
