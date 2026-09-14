"""Tests for the scratch-worktree lifecycle (slice 382, design D3).

Against FakeProcessRunner throughout — no real git or ps invocation. The lock file itself
is real (written to a real tmp_path), since sweep_orphans reads it straight off disk.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from squadron.codehost.models import PullRequestRecord
from squadron.codehost.refs import GIT_FETCH_TIMEOUT_SECONDS
from squadron.codehost.worktree import (
    ProcessIdentityUnresolvableError,
    ScratchWorktree,
    SubmoduleTimeoutError,
    SubmoduleUnfetchableError,
    WorktreeCreationError,
    _current_process_start_time,
    _flatten_key,
    _worktree_root,
    sweep_orphans,
)
from squadron.core.process_runner import ProcessResult, ProcessTimedOutError
from tests.codehost.fake_runner import FakeProcessRunner

CHECKOUT_CWD = "/repo"
_LSTART = "Mon Sep 14 06:27:18 2026"


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
# _flatten_key / _worktree_root
# ---------------------------------------------------------------------------


def test_flatten_key_replaces_path_hostile_characters() -> None:
    record = _record(number=83)
    assert record.key == "github.com/acme/widgets#83"
    assert _flatten_key(record) == "github.com-acme-widgets-83"


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
    my_start = 1789388838.0
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
    _write_lock(entry, pid=dead_pid, started_at=1789388838.0)

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
            (
                ["git", "worktree", "add", "--detach", str(expected_path), head_ref],
                _worktree_add_ok(),
            ),
            (["ps", "-o", "lstart=", "-p", str(my_pid)], _ps_ok()),
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
    """The scripted calls through 'worktree created, lock written' — before submodule init."""
    return [
        (["git", "worktree", "prune"], _worktree_add_ok()),
        (
            ["git", "worktree", "add", "--detach", str(expected_path), head_ref],
            _worktree_add_ok(),
        ),
        (["ps", "-o", "lstart=", "-p", str(my_pid)], _ps_ok()),
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
