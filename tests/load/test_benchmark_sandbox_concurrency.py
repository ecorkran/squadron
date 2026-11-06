"""Load test: concurrent benchmark sandboxes sharing a root and the uv cache (slice 421).

Required by the load-test tier: the sandbox install is a network and environment path, and
sandboxes can run concurrently. Three sandboxes enter at once under one root, while the
orphan sweep runs against that root. The sweep must treat each live lock as live, every
install must finish inside ``benchmark.install_timeout_s``, and exit must leave nothing.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from squadron.benchmark.python_adapter import PythonBenchmarkAdapter
from squadron.benchmark.sandbox import BenchmarkSandbox, sweep_benchmark_orphans
from squadron.config.keys import BENCHMARK_INSTALL_TIMEOUT_KEY, get_default
from squadron.core.process_runner import SubprocessRunner
from tests.benchmark.support import git_tree

pytestmark = pytest.mark.network

SANDBOX_COUNT = 3
SWEEP_INTERVAL_S = 0.2


def _head(tree: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(tree), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def test_three_concurrent_sandboxes_survive_a_concurrent_sweep(tmp_path: Path) -> None:
    install_timeout_s = float(get_default(BENCHMARK_INSTALL_TIMEOUT_KEY))
    root = tmp_path / "root"
    trees = [git_tree("env_ok", tmp_path / f"src{index}") for index in range(SANDBOX_COUNT)]
    for tree in trees:
        assert tree.is_dir()
    stop_sweeping = threading.Event()

    def sweep_loop() -> None:
        while not stop_sweeping.is_set():
            sweep_benchmark_orphans(SubprocessRunner(), root)
            time.sleep(SWEEP_INTERVAL_S)

    def enter_and_hold(index: int) -> float:
        started = time.monotonic()
        sandbox = BenchmarkSandbox(
            start_sha=_head(trees[index]),
            sandbox_id=f"load-{index}",
            repo_root=trees[index],
            runner=SubprocessRunner(),
            adapter=PythonBenchmarkAdapter(),
            harness_env=dict(os.environ),
            install_timeout_s=install_timeout_s,
            suite_timeout_s=60,
            root=root,
        )
        with sandbox:
            elapsed = time.monotonic() - started
            assert sandbox.tree.is_dir(), "the sweep removed a live sandbox"
            time.sleep(SWEEP_INTERVAL_S * 3)  # let at least one sweep run while all are live
            assert sandbox.tree.is_dir() and sandbox.home.is_dir() and sandbox.output_dir.is_dir()
        return elapsed

    sweeper = threading.Thread(target=sweep_loop)
    sweeper.start()
    try:
        with ThreadPoolExecutor(max_workers=SANDBOX_COUNT) as pool:
            elapsed = list(pool.map(enter_and_hold, range(SANDBOX_COUNT)))
    finally:
        stop_sweeping.set()
        sweeper.join()

    assert all(seconds < install_timeout_s for seconds in elapsed), elapsed
    assert sorted(path.name for path in root.iterdir()) == []
