"""wait_for_run: block until a run leaves ``running`` (slice 199 D13)."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

import pytest

from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.run_wait import WAIT_EXIT_CODES, WaitOutcome, WaitResult, wait_for_run
from squadron.pipeline.state import StateManager
from tests.pipeline.run_listing_support import begin, end, warned

_LOGGER = "squadron.pipeline.run_wait"


@pytest.fixture
def sm(tmp_path: Path) -> StateManager:
    return StateManager(runs_dir=tmp_path / "runs")


class _FakeTime:
    """A clock that only moves when the waiter sleeps; *on_sleep* runs at each sleep."""

    def __init__(self, on_sleep: Callable[[int], None] | None = None) -> None:
        self.now = 0.0
        self.sleeps = 0
        self._on_sleep = on_sleep

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps += 1
        self.now += seconds
        if self._on_sleep is not None:
            self._on_sleep(self.sleeps)


def _wait(sm: StateManager, run_id: str, fake: _FakeTime, timeout: float | None) -> WaitResult:
    return wait_for_run(
        sm, run_id, timeout=timeout, poll_interval=2.0, clock=fake.clock, sleep=fake.sleep
    )


def _rewrite_state(sm: StateManager, run_id: str, **fields: object) -> None:
    path = sm.runs_dir / f"{run_id}.json"
    data = json.loads(path.read_text())
    data.update(fields)
    path.write_text(json.dumps(data))


def _corrupt_json(path: Path) -> None:
    path.write_text("{not json")


def _unsupported_schema(path: Path) -> None:
    path.write_text(json.dumps({**json.loads(path.read_text()), "schema_version": 99}))


def _schema_invalid(path: Path) -> None:
    path.write_text(json.dumps({"schema_version": 4}))


class TestWaitForRun:
    @pytest.mark.parametrize(
        ("status", "outcome"),
        [
            (ExecutionStatus.COMPLETED, WaitOutcome.COMPLETED),
            (ExecutionStatus.FAILED, WaitOutcome.FAILED),
            (ExecutionStatus.PAUSED, WaitOutcome.PAUSED),
        ],
    )
    def test_run_leaves_running_mid_wait(
        self,
        sm: StateManager,
        caplog: pytest.LogCaptureFixture,
        status: ExecutionStatus,
        outcome: WaitOutcome,
    ) -> None:
        run_id = begin(sm, "steps")
        fake = _FakeTime(lambda n: end(sm, run_id, status) if n == 2 else None)

        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            result = _wait(sm, run_id, fake, timeout=None)

        assert result.outcome is outcome
        assert result.state is not None and result.state.status == status.value

        assert fake.sleeps == 2
        assert warned(caplog, _LOGGER, run_id, str(outcome)) is (outcome is not WaitOutcome.COMPLETED)

    def test_timeout_while_running(self, sm: StateManager, caplog: pytest.LogCaptureFixture) -> None:
        run_id = begin(sm, "steps")
        fake = _FakeTime()

        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            assert _wait(sm, run_id, fake, timeout=5).outcome is WaitOutcome.TIMED_OUT

        assert fake.now == 5  # the last sleep is cut to the deadline
        assert warned(caplog, _LOGGER, run_id, "timed_out")

    def test_missing_run(self, sm: StateManager, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            assert _wait(sm, "no-such-run", _FakeTime(), timeout=None).outcome is WaitOutcome.NOT_FOUND
        assert warned(caplog, _LOGGER, "no-such-run", "not_found")

    @pytest.mark.parametrize(
        "corrupt",
        [_corrupt_json, _unsupported_schema, _schema_invalid],
        ids=["corrupt-json", "unsupported-schema", "schema-invalid"],
    )
    def test_unreadable_state_on_first_poll(
        self,
        sm: StateManager,
        caplog: pytest.LogCaptureFixture,
        corrupt: Callable[[Path], None],
    ) -> None:
        run_id = begin(sm, "steps")
        corrupt(sm.runs_dir / f"{run_id}.json")
        fake = _FakeTime()

        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            result = _wait(sm, run_id, fake, timeout=None)

        assert (result.outcome, result.state) == (WaitOutcome.UNREADABLE, None)

        assert fake.sleeps == 0  # no retry
        assert warned(caplog, _LOGGER, run_id, "unreadable")

    def test_unknown_status(self, sm: StateManager, caplog: pytest.LogCaptureFixture) -> None:
        run_id = begin(sm, "steps")
        _rewrite_state(sm, run_id, status="exploded")

        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            assert _wait(sm, run_id, _FakeTime(), timeout=None).outcome is WaitOutcome.UNKNOWN_STATUS

        assert warned(caplog, _LOGGER, run_id, "unknown_status")

    def test_exit_codes(self) -> None:
        assert set(WAIT_EXIT_CODES) == set(WaitOutcome)
        assert WAIT_EXIT_CODES[WaitOutcome.COMPLETED] == 0
        assert 2 not in WAIT_EXIT_CODES.values()
        assert len(set(WAIT_EXIT_CODES.values())) == len(WaitOutcome)
