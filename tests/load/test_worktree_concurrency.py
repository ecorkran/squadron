"""Load tests for the scratch-worktree lifecycle's concurrency and network paths.

Required by ``.claude/rules/python.md``'s load-test tier: ``ScratchWorktree`` is both
concurrency code (the lock/orphan-sweep race across processes) and network code (bounded
submodule fetch), and ``tests/codehost/test_worktree.py`` only proves functional
correctness against ``FakeProcessRunner`` — a scripted fake can never observe whether the
real OS-level subprocess timeout actually fires. These tests use the real
``SubprocessRunner``, real git subprocesses, and a real throwaway repository.

Case 2 (submodule timeout) does not wait out the real ``GIT_FETCH_TIMEOUT_SECONDS``
(300s) — that would make this file, which runs unconditionally in every test invocation,
add five minutes to every run. Instead it patches ``worktree.GIT_FETCH_TIMEOUT_SECONDS``
down to a few seconds for the duration of one test, the same way
``test_grep_timeout.py``'s sibling unit test patches its budget down — production code is
untouched; only this test's read of the module constant changes. What is being proven is
the mechanism (a real hung subprocess is really cut off, not just that the right exception
type comes back against a scripted fake), not the specific 300s figure.
"""

from __future__ import annotations

import socket
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from squadron.codehost import worktree
from squadron.codehost.models import PullRequestRecord
from squadron.codehost.worktree import ScratchWorktree, SubmoduleTimeoutError
from squadron.core.process_runner import SubprocessRunner

# Generous multiple of the (possibly patched-down) bound — absorbs process-spawn and CI
# scheduling jitter while still failing loudly if the real subprocess timeout stopped
# holding (an unbounded wait would blow well past this).
BUDGET_TOLERANCE = 5.0


def _run_git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def real_checkout(tmp_path: Path) -> Path:
    """A real, throwaway git repository with one commit — the 'trusted checkout.'"""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    _run_git(["init", "-q"], checkout)
    _run_git(["config", "user.email", "test@example.com"], checkout)
    _run_git(["config", "user.name", "Test"], checkout)
    (checkout / "README.md").write_text("load test fixture\n")
    _run_git(["add", "-A"], checkout)
    _run_git(["commit", "-q", "-m", "init"], checkout)
    return checkout


def _record(number: int) -> PullRequestRecord:
    return PullRequestRecord(
        host="github.com",
        owner="acme",
        repository="widgets",
        number=number,
        base_ref="main",
        head_ref="feature/x",
        head_sha="0" * 40,
        url=f"https://github.com/acme/widgets/pull/{number}",
    )


# ---------------------------------------------------------------------------
# Case 1: concurrent real worktree creation, non-colliding paths
# ---------------------------------------------------------------------------


def test_concurrent_worktree_creation_succeeds_with_non_colliding_paths(
    real_checkout: Path, tmp_path: Path
) -> None:
    """Several real, concurrent ScratchWorktree creations against one throwaway repo.

    Unlike tests/codehost/test_worktree.py (scripted fake, sequential), this spawns real
    'git worktree add' processes from multiple threads at once against the same checkout —
    the actual race the lock and orphan sweep exist to survive.
    """
    worktrees_root = tmp_path / "worktrees"
    runner = SubprocessRunner()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=real_checkout, check=True, capture_output=True, text=True
    ).stdout.strip()

    concurrency = 8
    results: list[Path | BaseException] = [None] * concurrency  # type: ignore[list-item]

    def _create(index: int) -> None:
        sw = ScratchWorktree(
            runner,
            _record(number=index),
            head,
            f"run{index}",
            str(real_checkout),
            root=worktrees_root,
        )
        try:
            with sw as entered:
                results[index] = entered.path
        except BaseException as exc:  # noqa: BLE001 - captured for the assertion below, not swallowed
            results[index] = exc

    started = time.monotonic()
    threads = [threading.Thread(target=_create, args=(i,)) for i in range(concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=worktree.GIT_QUERY_TIMEOUT_SECONDS * BUDGET_TOLERANCE)
    elapsed = time.monotonic() - started

    failures = [r for r in results if isinstance(r, BaseException)]
    assert not failures, f"concurrent creation failed: {failures}"
    paths = [r for r in results if isinstance(r, Path)]
    assert len(paths) == concurrency
    assert len(set(paths)) == concurrency, "expected non-colliding paths, got a collision"
    assert elapsed < worktree.GIT_QUERY_TIMEOUT_SECONDS * BUDGET_TOLERANCE, (
        f"{concurrency} concurrent worktree creations took {elapsed:.2f}s"
    )


# ---------------------------------------------------------------------------
# Case 2: submodule fetch really gets cut off at the (patched-down) bound
# ---------------------------------------------------------------------------


@pytest.fixture
def hanging_listener() -> Iterator[str]:
    """A local TCP listener that accepts connections and never responds.

    Simulates a submodule remote that hangs mid-transfer — more reliable across CI
    networks than a non-routable IP, which can fail fast with "no route to host" instead
    of actually hanging, defeating the point of this test.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    stop = threading.Event()

    def _accept_and_stall() -> None:
        server.settimeout(0.5)
        while not stop.is_set():
            try:
                conn, _ = server.accept()
            except TimeoutError:
                continue
            # Accept and simply hold the connection open — never write a response, which is
            # exactly what a real hung git-over-http remote looks like from the client side.
            while not stop.is_set():
                time.sleep(0.1)
            conn.close()

    thread = threading.Thread(target=_accept_and_stall, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/hung-submodule.git"
    finally:
        stop.set()
        server.close()
        thread.join(timeout=2.0)


def test_submodule_fetch_is_cut_off_at_the_real_bound(
    real_checkout: Path, hanging_listener: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A submodule pointed at a hanging remote is really cut off, not merely raises on cue.

    tests/codehost/test_worktree.py::test_submodule_timeout_raises_and_removes_worktree
    already proves the exception type against a scripted ProcessTimedOutError; this proves
    the real subprocess.run(timeout=...) mechanism underneath actually enforces the bound
    against a genuinely stalled connection.
    """
    # Patched down from 300s so this test (in tests/load/, which runs on every invocation)
    # stays fast. Production code always reads the real GIT_FETCH_TIMEOUT_SECONDS — nothing
    # here changes what a real user waits.
    bound = 2.0
    monkeypatch.setattr(worktree, "GIT_FETCH_TIMEOUT_SECONDS", bound)

    # Register the submodule without 'git submodule add': that command clones eagerly at
    # add-time, on an unbounded plain subprocess.run() in the test's own setup (nothing to
    # do with the code under test) — which would hang this fixture forever against a
    # listener that never responds. A real submodule needs both .gitmodules *and* a gitlink
    # tree entry (mode 160000) — .gitmodules alone leaves 'git submodule status' seeing
    # nothing registered, and 'git submodule update' returns instantly with no clone
    # attempted at all. The gitlink's sha does not need to be real or resolvable; only the
    # clone step (which never gets far enough to need it) would fail on that separately —
    # this test only needs the clone itself to start and hang.
    (real_checkout / ".gitmodules").write_text(
        f'[submodule "vendor/hung"]\n\tpath = vendor/hung\n\turl = {hanging_listener}\n'
    )
    placeholder_sha = "0" * 39 + "1"
    _run_git(
        ["update-index", "--add", "--cacheinfo", f"160000,{placeholder_sha},vendor/hung"], real_checkout
    )
    _run_git(["add", ".gitmodules"], real_checkout)
    _run_git(["commit", "-q", "-m", "add hanging submodule config"], real_checkout)

    runner = SubprocessRunner()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=real_checkout, check=True, capture_output=True, text=True
    ).stdout.strip()

    sw = ScratchWorktree(
        runner, _record(number=1), head, "run1", str(real_checkout), root=tmp_path / "worktrees"
    )

    started = time.monotonic()
    with pytest.raises(SubmoduleTimeoutError):
        with sw:
            pass
    elapsed = time.monotonic() - started

    assert elapsed < bound * BUDGET_TOLERANCE, (
        f"submodule fetch took {elapsed:.2f}s against a {bound}s (patched) bound — "
        "the real subprocess timeout did not hold"
    )
    assert elapsed > bound * 0.5, (
        f"submodule fetch returned in {elapsed:.2f}s, suspiciously fast for a {bound}s bound "
        "— check the listener is actually stalling the connection"
    )
