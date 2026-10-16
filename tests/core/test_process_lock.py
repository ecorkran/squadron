"""The pid + start-time lock shared by the scratch worktree and the replay sandbox."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

import pytest

from squadron.core.process_lock import (
    ProcessIdentityUnresolvable,
    ProcessLock,
    current_process_lock,
    is_orphan,
    process_start_time,
    read_lock,
)
from squadron.core.process_runner import ProcessResult
from tests.codehost.fake_runner import FakeProcessRunner

_LSTART = "Mon Sep 14 06:27:18 2026"


def _epoch() -> float:
    return datetime.strptime(_LSTART, "%a %b %d %H:%M:%S %Y").timestamp()


def _ps(pid: int, stdout: str, returncode: int = 0) -> FakeProcessRunner:
    result = ProcessResult(argv=(), returncode=returncode, stdout=stdout, stderr="")
    return FakeProcessRunner([(["ps", "-o", "lstart=", "-p", str(pid)], result)])


def test_process_start_time_parses_ps_output() -> None:
    assert process_start_time(_ps(42, _LSTART), 42) == _epoch()


def test_process_start_time_is_none_when_the_process_is_gone() -> None:
    assert process_start_time(_ps(42, "", returncode=1), 42) is None


def test_unparseable_ps_output_is_none_with_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assert process_start_time(_ps(42, "not a date"), 42) is None
    assert "Could not parse 'ps' start-time output for pid 42" in caplog.text


def test_current_process_lock_names_this_process() -> None:
    lock = current_process_lock(_ps(os.getpid(), _LSTART))
    assert lock == ProcessLock(pid=os.getpid(), started_at=_epoch())


def test_current_process_lock_raises_when_ps_cannot_resolve_it() -> None:
    with pytest.raises(ProcessIdentityUnresolvable) as caught:
        current_process_lock(_ps(os.getpid(), ""))
    assert caught.value.pid == os.getpid()


def test_a_lock_round_trips_through_its_file(tmp_path: Path) -> None:
    path = tmp_path / "x.lock"
    path.write_text(ProcessLock(pid=7, started_at=12.5).to_json())
    assert read_lock(path) == ProcessLock(pid=7, started_at=12.5)


@pytest.mark.parametrize(
    "content",
    [
        None,
        "{not json",
        json.dumps([1, 2]),
        json.dumps({"started_at": 1.0}),
        json.dumps({"pid": 123}),
        json.dumps({"pid": "123", "started_at": 1.0}),
        json.dumps({"pid": 123, "started_at": "now"}),
    ],
    ids=["missing", "malformed", "not-a-mapping", "no-pid", "no-start", "str-pid", "str-start"],
)
def test_an_unusable_lock_file_reads_as_none(tmp_path: Path, content: str | None) -> None:
    path = tmp_path / "x.lock"
    if content is not None:
        path.write_text(content)
    assert read_lock(path) is None


def test_no_lock_is_an_orphan() -> None:
    assert is_orphan(FakeProcessRunner([]), None) is True


def test_a_lock_whose_process_is_gone_is_an_orphan() -> None:
    assert is_orphan(_ps(42, "", returncode=1), ProcessLock(pid=42, started_at=_epoch())) is True


def test_a_recycled_pid_is_an_orphan() -> None:
    lock = ProcessLock(pid=42, started_at=_epoch() - 3600)
    assert is_orphan(_ps(42, _LSTART), lock) is True


def test_a_live_owner_is_not_an_orphan() -> None:
    assert is_orphan(_ps(42, _LSTART), ProcessLock(pid=42, started_at=_epoch())) is False
