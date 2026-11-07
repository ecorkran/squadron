"""BenchmarkSandbox lifecycle, orphan sweeping and scrubbed suite runs."""

from __future__ import annotations

import logging
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from squadron.benchmark.adapter import (
    EnvironmentFailureReason,
    EnvironmentResolutionError,
    NodeOutcome,
    SuiteSelection,
)
from squadron.benchmark.python_adapter import PythonBenchmarkAdapter
from squadron.benchmark.sandbox import (
    BenchmarkSandbox,
    benchmark_root,
    sweep_benchmark_orphans,
)
from squadron.core.process_lock import ProcessLock, current_process_lock
from squadron.core.process_runner import ProcessResult, SubprocessRunner
from squadron.replay.sandbox import sweep_orphans
from tests.benchmark.support import git_tree

SANDBOX_ID = "bench-1"


def head(tree: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(tree), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def sandbox_for(tree: Path, root: Path, sandbox_id: str = SANDBOX_ID) -> BenchmarkSandbox:
    return BenchmarkSandbox(
        start_sha=head(tree),
        sandbox_id=sandbox_id,
        repo_root=tree,
        runner=SubprocessRunner(),
        adapter=PythonBenchmarkAdapter(),
        harness_env=dict(os.environ),
        install_timeout_s=600,
        suite_timeout_s=300,
        root=root,
    )


def leftovers(root: Path) -> list[str]:
    return sorted(path.name for path in root.iterdir()) if root.exists() else []


def test_benchmark_root_is_a_sibling_of_replays() -> None:
    assert benchmark_root().parts[-3:] == (".config", "squadron", "benchmark")


@pytest.mark.network
def test_enter_exposes_paths_and_exit_removes_all_four(tmp_path: Path) -> None:
    root = tmp_path / "root"
    with sandbox_for(git_tree("env_ok", tmp_path), root) as sandbox:
        assert sandbox.identity.lockfile_sha256
        assert sandbox.tree.is_dir() and sandbox.home.is_dir() and sandbox.output_dir.is_dir()
        assert (root / f"{SANDBOX_ID}.lock").is_file()
        assert sandbox.process_env()["PATH"].split(":")[0] == str(sandbox.tree / ".venv" / "bin")
    assert leftovers(root) == []


@pytest.mark.network
def test_keep_leaves_everything(tmp_path: Path) -> None:
    root = tmp_path / "root"
    with sandbox_for(git_tree("env_ok", tmp_path), root) as sandbox:
        sandbox.keep()
    assert leftovers(root) == [
        SANDBOX_ID,
        f"{SANDBOX_ID}.home",
        f"{SANDBOX_ID}.lock",
        f"{SANDBOX_ID}.out",
    ]


def test_failed_resolution_leaves_nothing(tmp_path: Path) -> None:
    root = tmp_path / "root"
    with pytest.raises(EnvironmentResolutionError) as caught:
        with sandbox_for(git_tree("env_no_lock", tmp_path), root):
            pytest.fail("must not enter")
    assert caught.value.reason is EnvironmentFailureReason.NO_LOCKFILE
    assert leftovers(root) == []


@pytest.mark.network
def test_run_suite_runs_under_the_scrubbed_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GH_TOKEN", "leaked")
    tree = git_tree("env_ok", tmp_path)
    (tree / "test_scrub.py").write_text(
        "import os\n\n\ndef test_scrubbed() -> None:\n"
        "    assert 'GH_TOKEN' not in os.environ\n"
        "    assert os.environ['HOME'].endswith('.home')\n"
    )
    subprocess.run(["git", "-C", str(tree), "add", "-A"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tree),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t.invalid",
            "commit",
            "-qm",
            "x",
        ],
        check=True,
    )
    with sandbox_for(tree, tmp_path / "root") as sandbox:
        run = sandbox.run_suite(SuiteSelection.nodes(("test_scrub.py::test_scrubbed",)))
    assert [r.outcome for r in run.results] == [NodeOutcome.PASSED]


def _dead_pid() -> int:
    done = subprocess.Popen(["true"])
    done.wait()
    return done.pid


def plant(root: Path, name: str, lock: ProcessLock | None) -> None:
    for suffix in ("", ".home", ".out"):
        (root / f"{name}{suffix}").mkdir(parents=True)
    if lock is not None:
        (root / f"{name}.lock").write_text(lock.to_json())


class RecordingRunner:
    """Runs for real and records each argv, to prove no cf command ran."""

    def __init__(self) -> None:
        self.argvs: list[tuple[str, ...]] = []
        self._real = SubprocessRunner()

    def run(self, argv: Sequence[str], **kwargs: Any) -> ProcessResult:
        self.argvs.append(tuple(argv))
        return self._real.run(argv, **kwargs)


def test_sweep_without_cf_removes_orphan_and_runs_no_cf_command(tmp_path: Path) -> None:
    root = tmp_path / "root"
    plant(root, "dead", ProcessLock(pid=_dead_pid(), started_at=1.0))
    runner = RecordingRunner()
    sweep_orphans(runner, root, sweep_cf_projects=False)
    assert not (root / "dead").exists()
    assert runner.argvs
    assert all(argv[0] != "cf" for argv in runner.argvs)


def test_sweep_benchmark_orphans_removes_siblings_and_spares_live_owner(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root = tmp_path / "root"
    live = current_process_lock(SubprocessRunner())
    plant(root, "dead", ProcessLock(pid=_dead_pid(), started_at=live.started_at))
    plant(root, "alive", live)
    replays = tmp_path / "replays"
    plant(replays, "other", None)
    with caplog.at_level(logging.WARNING):
        sweep_benchmark_orphans(SubprocessRunner(), root)
    assert leftovers(root) == ["alive", "alive.home", "alive.lock", "alive.out"]
    assert "removing orphaned replay sandbox" in caplog.text
    assert (replays / "other").exists()


def test_sweep_removes_siblings_whose_owner_directory_is_missing(tmp_path: Path) -> None:
    root = tmp_path / "root"
    live = current_process_lock(SubprocessRunner())
    for name in ("gone.home", "gone.out", "kept.home"):
        (root / name).mkdir(parents=True)
    (root / "gone.lock").write_text(ProcessLock(pid=_dead_pid(), started_at=live.started_at).to_json())
    (root / "kept.lock").write_text(live.to_json())
    sweep_benchmark_orphans(SubprocessRunner(), root)
    assert leftovers(root) == ["kept.home", "kept.lock"]
