"""Tests for the scratch-worktree lifecycle (slice 382, design D3).

Against FakeProcessRunner throughout — no real git or ps invocation. The lock file itself
is real (written to a real tmp_path), since sweep_orphans reads it straight off disk.
"""

from __future__ import annotations

import fcntl
import json
import os
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pytest

from squadron.codehost import metadata_lock, worktree
from squadron.codehost.models import PullRequestRecord
from squadron.codehost.refs import GIT_FETCH_TIMEOUT_SECONDS
from squadron.codehost.worktree import (
    ProcessIdentityUnresolvableError,
    ScratchWorktree,
    SubmoduleTimeoutError,
    SubmoduleUnfetchableError,
    WorktreeCreationError,
    WorktreeLock,
    _current_process_start_time,
    _worktree_root,
    sweep_orphans,
)
from squadron.core.process_runner import ProcessResult, ProcessTimedOutError
from tests.codehost.fake_runner import FakeProcessRunner, UnscriptedCallError

CHECKOUT_CWD = "/repo"
_LSTART = "Mon Sep 14 06:27:18 2026"


def _lstart_epoch() -> float:
    """The epoch seconds ``_process_start_time`` derives from ``_LSTART``.

    Parsed rather than hardcoded, and at call time rather than import: the parse is
    local-time, so it must run under the same ``TZ`` the code under test sees.
    """
    return datetime.strptime(_LSTART, "%a %b %d %H:%M:%S %Y").timestamp()


def _record(number: int = 83) -> PullRequestRecord:
    return PullRequestRecord(
        host="github.com",
        owner="acme",
        repository="widgets",
        number=number,
        base_ref="main",
        head_ref="feature/x",  # remote-side name — never used by worktree.py directly
        head_sha="b67cf55495f01bc2da843d8f96c767a11770e330",
        url=f"https://github.com/acme/widgets/pull/{number}",
    )


def _ps_ok(lstart: str = _LSTART) -> ProcessResult:
    return ProcessResult(argv=(), returncode=0, stdout=lstart, stderr="")


def _worktree_add_ok() -> ProcessResult:
    return ProcessResult(argv=(), returncode=0, stdout="", stderr="")


def _write_lock(path: Path, *, pid: int, started_at: float) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "lock.json").write_text(json.dumps({"pid": pid, "started_at": started_at}))


# ---------------------------------------------------------------------------
# PullRequestRecord.path_key / _worktree_root
# ---------------------------------------------------------------------------


def test_path_key_replaces_path_hostile_characters() -> None:
    """The flattening moved onto the record (383, D3); the result is unchanged.

    This literal is what ``_flatten_key`` produced before the collapse, so it
    doubles as the assertion that existing worktree directory names did not
    move — the name a running worktree was created under must still be the
    name a later sweep computes for it.
    """
    record = _record(number=83)

    # key stays deliberately unflattened: it reads the way a PR is written.
    assert record.key == "github.com/acme/widgets#83"
    assert record.path_key == "github.com-acme-widgets-83"


def test_path_key_carries_no_character_a_path_cannot() -> None:
    """The property's whole reason for existing, asserted rather than assumed.

    ``key``'s docstring claimed to be filesystem-safe while returning a string
    with ``/`` and ``#`` in it. Two consumers build names from this — the
    scratch worktree directory and the review artifact filename — so the
    guarantee is pinned here rather than trusted.
    """
    record = _record(number=83)

    assert "/" not in record.path_key
    assert "#" not in record.path_key


def test_worktree_root_is_under_config_squadron() -> None:
    assert _worktree_root() == Path.home() / ".config" / "squadron" / "worktrees"


# ---------------------------------------------------------------------------
# _current_process_start_time
# ---------------------------------------------------------------------------


def test_current_process_start_time_parses_ps_output() -> None:
    runner = FakeProcessRunner([(["ps", "-o", "lstart=", "-p", str(os.getpid())], _ps_ok())])
    result = _current_process_start_time(runner)
    assert result > 0


def test_current_process_start_time_raises_when_ps_cannot_resolve_it() -> None:
    runner = FakeProcessRunner([(["ps", "-o", "lstart=", "-p", str(os.getpid())], _ps_ok(lstart=""))])
    with pytest.raises(ProcessIdentityUnresolvableError):
        _current_process_start_time(runner)


# ---------------------------------------------------------------------------
# sweep_orphans
# ---------------------------------------------------------------------------


def test_sweep_orphans_no_root_directory_is_a_noop(tmp_path: Path) -> None:
    """No worktrees directory yet (first-ever run) — nothing to sweep, no error."""
    runner = FakeProcessRunner([])
    sweep_orphans(runner, CHECKOUT_CWD, root=tmp_path / "does-not-exist")
    assert runner.calls == []


def test_sweep_orphans_leaves_live_owner_alone(tmp_path: Path) -> None:
    root = tmp_path / "worktrees"
    entry = root / "github.com-acme-widgets-83-run1"
    my_pid = os.getpid()
    my_start = _lstart_epoch()
    _write_lock(entry, pid=my_pid, started_at=my_start)

    runner = FakeProcessRunner(
        [
            (["ps", "-o", "lstart=", "-p", str(my_pid)], _ps_ok(_LSTART)),
            (["git", "worktree", "prune"], _worktree_add_ok()),
        ]
    )
    sweep_orphans(runner, CHECKOUT_CWD, root=root)

    assert entry.exists()  # not removed
    assert not any(
        call.argv[:2] == ("git", "worktree") and "remove" in call.argv for call in runner.calls
    )


def test_sweep_orphans_removes_dead_owner_with_one_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root = tmp_path / "worktrees"
    entry = root / "github.com-acme-widgets-83-run1"
    dead_pid = 999999  # ps returns nothing for a pid that isn't running
    _write_lock(entry, pid=dead_pid, started_at=_lstart_epoch())

    runner = FakeProcessRunner(
        [
            (["ps", "-o", "lstart=", "-p", str(dead_pid)], _ps_ok(lstart="")),
            (["git", "worktree", "remove", "--force", str(entry)], _worktree_add_ok()),
            (["git", "worktree", "prune"], _worktree_add_ok()),
        ]
    )
    with caplog.at_level("WARNING"):
        sweep_orphans(runner, CHECKOUT_CWD, root=root)

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert str(entry) in warnings[0].message


def test_sweep_leaves_unlocked_worktree_with_a_live_claim_alone(tmp_path: Path) -> None:
    """F002: a worktree mid-creation has no lock yet — its live claim must protect it.

    Without the claim the sweep reads "directory exists, no lock" as an orphan and removes
    a worktree another run is still setting up.
    """
    root = tmp_path / "worktrees"
    entry = root / "github.com-acme-widgets-83-run1"
    entry.mkdir(parents=True)  # created by 'git worktree add', lock not yet written
    my_pid = os.getpid()
    (root / "github.com-acme-widgets-83-run1.claim").write_text(
        json.dumps({"pid": my_pid, "started_at": _lstart_epoch()})
    )

    runner = FakeProcessRunner(
        [
            (["ps", "-o", "lstart=", "-p", str(my_pid)], _ps_ok(_LSTART)),
            (["git", "worktree", "prune"], _worktree_add_ok()),
        ]
    )
    sweep_orphans(runner, CHECKOUT_CWD, root=root)

    assert entry.exists()
    assert not any("remove" in call.argv for call in runner.calls)


def test_sweep_removes_unlocked_worktree_whose_claim_owner_is_gone(tmp_path: Path) -> None:
    """The claim narrows the orphan rule, it does not retire it: a dead claimant is swept."""
    root = tmp_path / "worktrees"
    entry = root / "github.com-acme-widgets-83-run1"
    entry.mkdir(parents=True)
    dead_pid = 999999
    (root / "github.com-acme-widgets-83-run1.claim").write_text(
        json.dumps({"pid": dead_pid, "started_at": _lstart_epoch()})
    )

    runner = FakeProcessRunner(
        [
            (["ps", "-o", "lstart=", "-p", str(dead_pid)], _ps_ok(lstart="")),
            (["git", "worktree", "remove", "--force", str(entry)], _worktree_add_ok()),
            (["git", "worktree", "prune"], _worktree_add_ok()),
        ]
    )
    sweep_orphans(runner, CHECKOUT_CWD, root=root)

    assert not entry.exists()


def test_sweep_spares_a_worktree_whose_claim_hands_off_to_its_lock_mid_sweep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """929 D8: the creator's claim-to-lock handoff can land between the sweep's two reads.

    ``__enter__`` writes ``lock.json`` and then unlinks the claim. A sweep that read the
    lock first and the claim second saw neither across that handoff and removed a live
    worktree. The handoff is injected right after the sweep's first read.
    """
    root = tmp_path / "worktrees"
    entry = root / "github.com-acme-widgets-83-run1"
    entry.mkdir(parents=True)  # 'git worktree add' done, lock not yet written
    claim = root / "github.com-acme-widgets-83-run1.claim"
    my_pid = os.getpid()
    owner = json.dumps({"pid": my_pid, "started_at": _lstart_epoch()})
    claim.write_text(owner)

    real_read_lock = worktree._read_lock  # pyright: ignore[reportPrivateUsage]
    reads: list[Path] = []

    def _read_then_hand_off(path: Path) -> WorktreeLock | None:
        result = real_read_lock(path)
        reads.append(path)
        if len(reads) == 1:
            (entry / "lock.json").write_text(owner)
            claim.unlink()
        return result

    monkeypatch.setattr(worktree, "_read_lock", _read_then_hand_off)
    runner = FakeProcessRunner(
        [
            (["ps", "-o", "lstart=", "-p", str(my_pid)], _ps_ok(_LSTART)),
            (["git", "worktree", "remove"], _worktree_add_ok()),
            (["git", "worktree", "prune"], _worktree_add_ok()),
        ]
    )
    sweep_orphans(runner, CHECKOUT_CWD, root=root)

    assert entry.exists()
    assert not any("remove" in call.argv for call in runner.calls)


def test_claim_is_removed_once_the_real_lock_lands(tmp_path: Path) -> None:
    """The claim is scaffolding: once the lock speaks for the worktree, it is gone."""
    root = tmp_path / "worktrees"
    record = _record(number=83)
    head_ref = "refs/squadron/pr/origin/83/head"
    my_pid = os.getpid()
    expected_path = root / "github.com-acme-widgets-83-run1"

    runner = _FakeRunnerCreatingWorktreeDir(
        _full_happy_script(expected_path, head_ref, my_pid, removal=_worktree_add_ok()),
        created_dir=expected_path,
    )

    with ScratchWorktree(runner, record, head_ref, "run1", CHECKOUT_CWD, root=root) as entered:
        assert (entered.path / "lock.json").exists()
        assert not (root / "github.com-acme-widgets-83-run1.claim").exists()


def test_claim_is_removed_when_worktree_creation_fails(tmp_path: Path) -> None:
    """A failed 'git worktree add' must not leave its claim behind as litter."""
    root = tmp_path / "worktrees"
    record = _record(number=83)
    head_ref = "refs/squadron/pr/origin/83/head"
    my_pid = os.getpid()

    runner = FakeProcessRunner(
        [
            (["git", "worktree", "prune"], _worktree_add_ok()),
            (["ps", "-o", "lstart=", "-p", str(my_pid)], _ps_ok()),
            (
                ["git", "worktree", "add", "--detach"],
                ProcessResult(argv=(), returncode=128, stdout="", stderr="fatal: bad ref"),
            ),
        ]
    )

    with pytest.raises(WorktreeCreationError):
        with ScratchWorktree(runner, record, head_ref, "run1", CHECKOUT_CWD, root=root):
            pass

    assert not (root / "github.com-acme-widgets-83-run1.claim").exists()


@pytest.mark.parametrize(
    "corrupt",
    [
        pytest.param(lambda p: p.write_text("{"), id="truncated-json"),
        pytest.param(lambda p: p.write_text("not json at all"), id="non-json"),
        pytest.param(lambda p: p.write_text(json.dumps({"started_at": 1.0})), id="missing-pid"),
        pytest.param(lambda p: p.write_text(json.dumps({"pid": 123})), id="missing-started_at"),
        pytest.param(lambda p: None, id="absent-entirely"),
    ],
)
def test_sweep_orphans_malformed_lock_table(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, corrupt
) -> None:
    root = tmp_path / "worktrees"
    entry = root / "github.com-acme-widgets-83-run1"
    entry.mkdir(parents=True)
    lock_path = entry / "lock.json"
    corrupt(lock_path)

    runner = FakeProcessRunner(
        [
            (["git", "worktree", "remove", "--force", str(entry)], _worktree_add_ok()),
            (["git", "worktree", "prune"], _worktree_add_ok()),
        ]
    )
    with caplog.at_level("WARNING"):
        sweep_orphans(runner, CHECKOUT_CWD, root=root)  # must not raise

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1


# ---------------------------------------------------------------------------
# ScratchWorktree: creation happy path
# ---------------------------------------------------------------------------


class _FakeRunnerCreatingWorktreeDir(FakeProcessRunner):
    """FakeProcessRunner that also creates the worktree directory on a scripted 'add'.

    Real ``git worktree add`` creates the directory as a side effect; the fake only
    records the call, so tests that write into the resulting path (the lock file) must
    make that side effect real to match what production code observes.
    """

    def __init__(self, script, *, created_dir: Path) -> None:
        super().__init__(script)
        self._created_dir = created_dir

    def run(self, argv, *, cwd, timeout, env=None, stdin=None):
        result = super().run(argv, cwd=cwd, timeout=timeout, env=env, stdin=stdin)
        if tuple(argv[:3]) == ("git", "worktree", "add"):
            self._created_dir.mkdir(parents=True, exist_ok=True)
        return result


def test_scratch_worktree_create_produces_expected_path_and_lock(tmp_path: Path) -> None:
    root = tmp_path / "worktrees"
    record = _record(number=83)
    head_ref = "refs/squadron/pr/origin/83/head"
    my_pid = os.getpid()
    expected_path = root / "github.com-acme-widgets-83-run1"

    runner = _FakeRunnerCreatingWorktreeDir(
        [
            (["git", "worktree", "prune"], _worktree_add_ok()),  # from the internal sweep
            # 'ps' first: the pre-creation claim (F002) carries this process's start time.
            (["ps", "-o", "lstart=", "-p", str(my_pid)], _ps_ok()),
            (
                ["git", "worktree", "add", "--detach", str(expected_path), head_ref],
                _worktree_add_ok(),
            ),
            # Submodule init (Task C.5) is not covered by this test — script a no-op.
            (["git", "submodule", "update", "--init", "--recursive"], _worktree_add_ok()),
            (["git", "worktree", "remove", "--force"], _worktree_add_ok()),
        ],
        created_dir=expected_path,
    )

    sw = ScratchWorktree(runner, record, head_ref, "run1", CHECKOUT_CWD, root=root)
    with sw as entered:
        assert entered.path == expected_path
        lock_data = json.loads((expected_path / "lock.json").read_text())
        assert lock_data["pid"] == my_pid
        assert isinstance(lock_data["started_at"], float)


def test_scratch_worktree_add_failure_raises_creation_error(tmp_path: Path) -> None:
    root = tmp_path / "worktrees"
    record = _record(number=83)
    head_ref = "refs/squadron/pr/origin/83/head"

    runner = FakeProcessRunner(
        [
            (["git", "worktree", "prune"], _worktree_add_ok()),
            # 'ps' first: the pre-creation claim (F002) resolves this process's start time.
            (["ps", "-o", "lstart=", "-p", str(os.getpid())], _ps_ok()),
            (
                ["git", "worktree", "add", "--detach"],
                ProcessResult(argv=(), returncode=128, stdout="", stderr="fatal: bad ref"),
            ),
        ]
    )

    sw = ScratchWorktree(runner, record, head_ref, "run1", CHECKOUT_CWD, root=root)
    with pytest.raises(WorktreeCreationError):
        with sw:
            pass


# ---------------------------------------------------------------------------
# Submodule init (Task C.7): happy path and both failure modes
# ---------------------------------------------------------------------------


def _create_and_lock_script(
    expected_path: Path, head_ref: str, my_pid: int
) -> list[tuple[list[str], ProcessResult | Exception]]:
    """The scripted calls through 'worktree created, lock written' — before submodule init.

    The 'ps' call precedes 'git worktree add': the claim written before creation (F002)
    carries this process's start time, so the identity lookup happens first.
    """
    return [
        (["git", "worktree", "prune"], _worktree_add_ok()),
        (["ps", "-o", "lstart=", "-p", str(my_pid)], _ps_ok()),
        (
            ["git", "worktree", "add", "--detach", str(expected_path), head_ref],
            _worktree_add_ok(),
        ),
    ]


def test_submodule_happy_path_populates_submodule_directory(tmp_path: Path) -> None:
    """The design's positive criterion: submodule paths exist and are populated afterward."""
    root = tmp_path / "worktrees"
    record = _record(number=83)
    head_ref = "refs/squadron/pr/origin/83/head"
    my_pid = os.getpid()
    expected_path = root / "github.com-acme-widgets-83-run1"

    class _FakeRunnerPopulatingSubmodule(_FakeRunnerCreatingWorktreeDir):
        def run(self, argv, *, cwd, timeout, env=None, stdin=None):
            result = super().run(argv, cwd=cwd, timeout=timeout, env=env, stdin=stdin)
            if tuple(argv[:4]) == ("git", "submodule", "update", "--init"):
                (expected_path / "vendor" / "lib").mkdir(parents=True, exist_ok=True)
                (expected_path / "vendor" / "lib" / "marker.txt").write_text("populated")
            return result

    runner = _FakeRunnerPopulatingSubmodule(
        [
            *_create_and_lock_script(expected_path, head_ref, my_pid),
            (["git", "submodule", "update", "--init", "--recursive"], _worktree_add_ok()),
            (["git", "worktree", "remove", "--force"], _worktree_add_ok()),
        ],
        created_dir=expected_path,
    )

    sw = ScratchWorktree(runner, record, head_ref, "run1", CHECKOUT_CWD, root=root)
    with sw:
        submodule_marker = expected_path / "vendor" / "lib" / "marker.txt"
        assert submodule_marker.is_file()
        assert submodule_marker.read_text() == "populated"


def test_submodule_unfetchable_raises_and_removes_worktree(tmp_path: Path) -> None:
    root = tmp_path / "worktrees"
    record = _record(number=83)
    head_ref = "refs/squadron/pr/origin/83/head"
    my_pid = os.getpid()
    expected_path = root / "github.com-acme-widgets-83-run1"

    runner = _FakeRunnerCreatingWorktreeDir(
        [
            *_create_and_lock_script(expected_path, head_ref, my_pid),
            (
                ["git", "submodule", "update", "--init", "--recursive"],
                ProcessResult(
                    argv=(),
                    returncode=1,
                    stdout="",
                    stderr="Failed to clone 'vendor/lib'. Retry scheduled",
                ),
            ),
            (["git", "worktree", "remove", "--force"], _worktree_add_ok()),
        ],
        created_dir=expected_path,
    )

    sw = ScratchWorktree(runner, record, head_ref, "run1", CHECKOUT_CWD, root=root)
    with pytest.raises(SubmoduleUnfetchableError) as excinfo:
        with sw:
            pass
    assert excinfo.value.submodule_path == "vendor/lib"
    assert not expected_path.exists()


def test_submodule_timeout_raises_and_removes_worktree(tmp_path: Path) -> None:
    root = tmp_path / "worktrees"
    record = _record(number=83)
    head_ref = "refs/squadron/pr/origin/83/head"
    my_pid = os.getpid()
    expected_path = root / "github.com-acme-widgets-83-run1"

    runner = _FakeRunnerCreatingWorktreeDir(
        [
            *_create_and_lock_script(expected_path, head_ref, my_pid),
            (
                ["git", "submodule", "update", "--init", "--recursive"],
                ProcessTimedOutError(
                    ["git", "submodule", "update", "--init", "--recursive"],
                    GIT_FETCH_TIMEOUT_SECONDS,
                ),
            ),
            (["git", "worktree", "remove", "--force"], _worktree_add_ok()),
        ],
        created_dir=expected_path,
    )

    sw = ScratchWorktree(runner, record, head_ref, "run1", CHECKOUT_CWD, root=root)
    with pytest.raises(SubmoduleTimeoutError) as excinfo:
        with sw:
            pass
    assert excinfo.value.seconds == GIT_FETCH_TIMEOUT_SECONDS
    assert not expected_path.exists()


# ---------------------------------------------------------------------------
# Removal (Task C.7): success, exception inside the block, and a removal failure
# ---------------------------------------------------------------------------


def _full_happy_script(
    expected_path: Path, head_ref: str, my_pid: int, *, removal: ProcessResult
) -> list[tuple[list[str], ProcessResult | Exception]]:
    return [
        *_create_and_lock_script(expected_path, head_ref, my_pid),
        (["git", "submodule", "update", "--init", "--recursive"], _worktree_add_ok()),
        (["git", "worktree", "remove", "--force", str(expected_path)], removal),
    ]


def test_removal_on_success(tmp_path: Path) -> None:
    root = tmp_path / "worktrees"
    record = _record(number=83)
    head_ref = "refs/squadron/pr/origin/83/head"
    my_pid = os.getpid()
    expected_path = root / "github.com-acme-widgets-83-run1"

    runner = _FakeRunnerCreatingWorktreeDir(
        _full_happy_script(expected_path, head_ref, my_pid, removal=_worktree_add_ok()),
        created_dir=expected_path,
    )

    with ScratchWorktree(runner, record, head_ref, "run1", CHECKOUT_CWD, root=root):
        pass

    remove_calls = [c for c in runner.calls if c.argv[:3] == ("git", "worktree", "remove")]
    assert len(remove_calls) == 1
    assert not expected_path.exists()


def test_removal_runs_even_when_exception_raised_inside_with_block(tmp_path: Path) -> None:
    root = tmp_path / "worktrees"
    record = _record(number=83)
    head_ref = "refs/squadron/pr/origin/83/head"
    my_pid = os.getpid()
    expected_path = root / "github.com-acme-widgets-83-run1"

    runner = _FakeRunnerCreatingWorktreeDir(
        _full_happy_script(expected_path, head_ref, my_pid, removal=_worktree_add_ok()),
        created_dir=expected_path,
    )

    class _Boom(Exception):
        pass

    with pytest.raises(_Boom):
        with ScratchWorktree(runner, record, head_ref, "run1", CHECKOUT_CWD, root=root):
            raise _Boom("something failed mid-review")

    remove_calls = [c for c in runner.calls if c.argv[:3] == ("git", "worktree", "remove")]
    assert len(remove_calls) == 1
    assert not expected_path.exists()


def test_removal_failure_warns_and_does_not_raise_from_exit(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root = tmp_path / "worktrees"
    record = _record(number=83)
    head_ref = "refs/squadron/pr/origin/83/head"
    my_pid = os.getpid()
    expected_path = root / "github.com-acme-widgets-83-run1"

    runner = _FakeRunnerCreatingWorktreeDir(
        _full_happy_script(
            expected_path,
            head_ref,
            my_pid,
            removal=ProcessResult(argv=(), returncode=1, stdout="", stderr="worktree is dirty"),
        ),
        created_dir=expected_path,
    )

    with caplog.at_level("WARNING"):
        with ScratchWorktree(runner, record, head_ref, "run1", CHECKOUT_CWD, root=root):
            pass  # __exit__ must not raise even though 'git worktree remove' failed

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert any("Failed to remove worktree" in r.message for r in warnings)
    # The fallback direct removal still ran, since 'git worktree remove' failing does not
    # mean the directory is gone.
    assert not expected_path.exists()


# ---------------------------------------------------------------------------
# Concurrency (Task C.7): two instances for the same PR, different run_id, don't collide
# ---------------------------------------------------------------------------


def test_two_concurrent_instances_same_pr_different_run_id_do_not_collide(
    tmp_path: Path,
) -> None:
    root = tmp_path / "worktrees"
    record = _record(number=83)
    head_ref = "refs/squadron/pr/origin/83/head"
    my_pid = os.getpid()

    path_a = root / "github.com-acme-widgets-83-runA"
    path_b = root / "github.com-acme-widgets-83-runB"

    runner_a = _FakeRunnerCreatingWorktreeDir(
        _full_happy_script(path_a, head_ref, my_pid, removal=_worktree_add_ok()),
        created_dir=path_a,
    )
    # sw_b's own sweep_orphans (run at the start of its __enter__) scans the shared root,
    # which by then contains sw_a's live lock — one extra 'ps' call confirms it's not an
    # orphan before sw_b proceeds to create its own worktree.
    runner_b = _FakeRunnerCreatingWorktreeDir(
        [
            (["ps", "-o", "lstart=", "-p", str(my_pid)], _ps_ok()),
            *_full_happy_script(path_b, head_ref, my_pid, removal=_worktree_add_ok()),
        ],
        created_dir=path_b,
    )

    sw_a = ScratchWorktree(runner_a, record, head_ref, "runA", CHECKOUT_CWD, root=root)
    sw_b = ScratchWorktree(runner_b, record, head_ref, "runB", CHECKOUT_CWD, root=root)

    with sw_a as entered_a, sw_b as entered_b:
        assert entered_a.path != entered_b.path
        assert entered_a.path == path_a
        assert entered_b.path == path_b


# ---------------------------------------------------------------------------
# Metadata serialization (slice 929, D6): no two 'git worktree' calls ever overlap
# ---------------------------------------------------------------------------

# Long enough that an unserialized overlap between threads is essentially certain, short
# enough to keep the test fast.
_GIT_WORKTREE_HOLD_SECONDS = 0.02


class _OverlapTrackingRunner:
    """A thread-safe fake runner that records peak concurrent 'git worktree' calls.

    ``FakeProcessRunner`` mutates its script without a lock and cannot be shared across
    threads. This one answers a fixed set of calls and holds each 'git worktree' call
    open briefly, so any two that are not serialized are caught in flight together.
    """

    def __init__(self, submodule_barrier: threading.Barrier | None = None) -> None:
        self._guard = threading.Lock()
        self._in_flight = 0
        self.max_in_flight = 0
        # When set, every 'git submodule' call waits here for all its siblings (D.6).
        self._submodule_barrier = submodule_barrier
        self.broken_barriers: list[threading.BrokenBarrierError] = []

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str | None,
        timeout: float,
        env: Mapping[str, str] | None = None,
        stdin: str | None = None,
    ) -> ProcessResult:
        argv = tuple(argv)
        if argv[:1] == ("ps",):
            return _ps_ok()
        if argv[:2] == ("git", "submodule"):
            if self._submodule_barrier is not None:
                try:
                    self._submodule_barrier.wait(timeout=5.0)
                except threading.BrokenBarrierError as exc:
                    # Recorded for the test's assertion, not swallowed.
                    with self._guard:
                        self.broken_barriers.append(exc)
            return _worktree_add_ok()
        if argv[:2] != ("git", "worktree"):
            raise UnscriptedCallError(f"unscripted call: {' '.join(argv)}")

        with self._guard:
            self._in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self._in_flight)
        time.sleep(_GIT_WORKTREE_HOLD_SECONDS)
        with self._guard:
            self._in_flight -= 1
        if argv[2] == "add":
            # Production writes lock.json into the new directory straight after 'add'.
            Path(argv[4]).mkdir(parents=True)
        return _worktree_add_ok()


def test_concurrent_call_sites_never_overlap_a_metadata_git_call(tmp_path: Path) -> None:
    """Every 'git worktree' add/remove/prune runs alone, across sweeps and full cycles."""
    root = tmp_path / "worktrees"
    # An orphan (no lock, no claim), so the sweep issues its remove and prune.
    (root / "stale-entry").mkdir(parents=True)
    runner = _OverlapTrackingRunner()
    head_ref = "refs/squadron/pr/origin/83/head"
    cycles = 5
    start = threading.Barrier(cycles + 1)
    errors: list[BaseException] = []

    def _capture(work: Callable[[], None]) -> Callable[[], None]:
        def _run() -> None:
            start.wait()
            try:
                work()
            except BaseException as exc:  # noqa: BLE001 - asserted empty below, not swallowed
                errors.append(exc)

        return _run

    def _sweep() -> None:
        sweep_orphans(runner, CHECKOUT_CWD, root)

    def _cycle(index: int) -> Callable[[], None]:
        def _work() -> None:
            with ScratchWorktree(runner, _record(), head_ref, f"run{index}", CHECKOUT_CWD, root=root):
                pass

        return _work

    threads = [threading.Thread(target=_capture(_sweep))]
    threads += [threading.Thread(target=_capture(_cycle(i))) for i in range(cycles)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10.0)
    assert not any(thread.is_alive() for thread in threads), "a worker thread hung"

    assert errors == []
    assert runner.max_in_flight == 1


def test_submodule_fetch_calls_still_overlap_unlike_worktree_metadata_calls(
    tmp_path: Path,
) -> None:
    """The lock covers 'git worktree' only; submodule fetches must still run side by side.

    Deterministic: every submodule call waits on one barrier sized to the thread count.
    If the lock ever grew to cover the fetch, the threads would reach it one at a time
    and the barrier would break.
    """
    root = tmp_path / "worktrees"
    cycles = 3
    runner = _OverlapTrackingRunner(submodule_barrier=threading.Barrier(cycles))
    head_ref = "refs/squadron/pr/origin/83/head"
    errors: list[BaseException] = []

    def _cycle(index: int) -> None:
        try:
            with ScratchWorktree(runner, _record(), head_ref, f"run{index}", CHECKOUT_CWD, root=root):
                pass
        except BaseException as exc:  # noqa: BLE001 - asserted empty below, not swallowed
            errors.append(exc)

    threads = [threading.Thread(target=_cycle, args=(i,)) for i in range(cycles)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15.0)
    assert not any(thread.is_alive() for thread in threads), "a worker thread hung"

    assert errors == []
    assert runner.broken_barriers == []


# ---------------------------------------------------------------------------
# Metadata lock timeouts at each call site (slice 929, D4)
# ---------------------------------------------------------------------------

_PATCHED_LOCK_TIMEOUT_SECONDS = 0.2


@contextmanager
def _metadata_lock_held_elsewhere(root: Path) -> Iterator[Path]:
    """Hold the real metadata lock under *root* from this process, as a rival would."""
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".git-metadata.flock"
    with lock_path.open("a") as holder:
        fcntl.flock(holder, fcntl.LOCK_EX)
        try:
            yield lock_path
        finally:
            fcntl.flock(holder, fcntl.LOCK_UN)


@pytest.fixture
def short_lock_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metadata_lock, "METADATA_LOCK_TIMEOUT_SECONDS", _PATCHED_LOCK_TIMEOUT_SECONDS)


@pytest.mark.usefixtures("short_lock_timeout")
def test_enter_raises_worktree_creation_error_on_lock_timeout(tmp_path: Path) -> None:
    root = tmp_path / "worktrees"
    expected_path = root / "github.com-acme-widgets-83-run1"
    # 'ps' only: the lock times out before 'git worktree add' can run. The internal
    # sweep's prune times out too, and is logged rather than raised.
    runner = FakeProcessRunner([(["ps", "-o", "lstart=", "-p", str(os.getpid())], _ps_ok())])

    sw = ScratchWorktree(runner, _record(), "refs/x", "run1", CHECKOUT_CWD, root=root)
    with _metadata_lock_held_elsewhere(root) as lock_path:
        with pytest.raises(WorktreeCreationError) as excinfo:
            sw.__enter__()

    assert excinfo.value.fix_hint is not None
    assert str(lock_path) in excinfo.value.fix_hint
    assert "another squadron process" in excinfo.value.fix_hint.lower()
    assert not (root / f"{expected_path.name}.claim").exists()
    assert not any(call.argv[:3] == ("git", "worktree", "add") for call in runner.calls)


@pytest.mark.usefixtures("short_lock_timeout")
def test_sweep_orphans_logs_warning_and_skips_entry_on_remove_lock_timeout(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root = tmp_path / "worktrees"
    orphan = root / "stale-entry"  # no lock, no claim
    orphan.mkdir(parents=True)

    with _metadata_lock_held_elsewhere(root), caplog.at_level("WARNING"):
        sweep_orphans(FakeProcessRunner([]), CHECKOUT_CWD, root=root)

    assert orphan.exists()  # git still registers it; deleting it would corrupt metadata
    assert any(
        "remove orphaned worktree" in r.message and str(orphan) in r.message
        for r in caplog.records
        if r.levelname == "WARNING"
    )


@pytest.mark.usefixtures("short_lock_timeout")
def test_sweep_orphans_logs_warning_on_prune_lock_timeout(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root = tmp_path / "worktrees"  # exists, holds only the lock file: no entries to sweep

    with _metadata_lock_held_elsewhere(root), caplog.at_level("WARNING"):
        sweep_orphans(FakeProcessRunner([]), CHECKOUT_CWD, root=root)

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "git worktree prune" in warnings[0].message


@pytest.mark.usefixtures("short_lock_timeout")
def test_remove_logs_warning_and_falls_through_to_rmtree_on_lock_timeout(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root = tmp_path / "worktrees"
    path = root / "github.com-acme-widgets-83-run1"
    path.mkdir(parents=True)
    sw = ScratchWorktree(FakeProcessRunner([]), _record(), "refs/x", "run1", CHECKOUT_CWD, root=root)

    with _metadata_lock_held_elsewhere(root), caplog.at_level("WARNING"):
        sw._remove(path)  # pyright: ignore[reportPrivateUsage]

    assert not path.exists()
    assert any("remove worktree" in r.message and r.levelname == "WARNING" for r in caplog.records)
