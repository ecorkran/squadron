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
    RECALL_DIRS,
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


def test_sweep_leaves_the_recall_directories_alone(tmp_path: Path) -> None:
    # They have no lock of their own: the recall lock guards them, and a concurrent
    # fix-case build once deleted them under a running recall benchmark.
    root = tmp_path / "root"
    for name in RECALL_DIRS:
        (root / name / "inner").mkdir(parents=True)
    sweep_benchmark_orphans(SubprocessRunner(), root)
    assert leftovers(root) == sorted(RECALL_DIRS)


class _NoInstallAdapter:
    """Resolves nothing and installs nothing: for tests of the sandbox's own paths."""

    language = PythonBenchmarkAdapter.language

    def resolve_environment(self, ctx: Any) -> Any:
        from tests.metrology.test_benchmark_models import environment

        return environment()

    def path_entries(self, ctx: Any) -> tuple[Path, ...]:
        return ()

    def run_suite(self, ctx: Any, selection: Any) -> Any:
        raise AssertionError("no suite run in this test")


class TestProducerEnv:
    API_KEY_VARIABLE = "OPENAI_API_KEY"

    @pytest.fixture
    def real_home(self, tmp_path: Path) -> Path:
        home = tmp_path / "real-home"
        (home / ".codex").mkdir(parents=True)
        (home / ".codex" / "auth.json").write_text('{"token": "carried"}')
        return home

    def _sandbox(
        self, tmp_path: Path, real_home: Path, *, with_api_key: bool = True
    ) -> BenchmarkSandbox:
        harness_env = {
            **os.environ,
            "HOME": str(real_home),
            "GH_TOKEN": "must-not-reach-the-producer",
        }
        harness_env.pop(self.API_KEY_VARIABLE, None)
        if with_api_key:
            harness_env[self.API_KEY_VARIABLE] = "api-key-value"
        return BenchmarkSandbox(
            start_sha=head(git_tree("env_ok", tmp_path)),
            sandbox_id=SANDBOX_ID,
            repo_root=tmp_path / "env_ok",
            runner=SubprocessRunner(),
            adapter=_NoInstallAdapter(),  # type: ignore[arg-type]
            harness_env=harness_env,
            install_timeout_s=60,
            suite_timeout_s=60,
            root=tmp_path / "root",
        )

    def test_oauth_profile_gets_its_login_in_the_sandbox_home(
        self, tmp_path: Path, real_home: Path
    ) -> None:
        from squadron.providers.base import ProfileName

        with self._sandbox(tmp_path, real_home) as sandbox:
            env = sandbox.producer_env(ProfileName.OPENAI_OAUTH)
            carried = sandbox.home / ".codex" / "auth.json"
            assert carried.read_text() == '{"token": "carried"}'
            assert env["HOME"] == str(sandbox.home)
            assert "GH_TOKEN" not in env

    def test_the_producer_is_confined_to_the_sandbox_through_its_home_config(
        self, tmp_path: Path, real_home: Path
    ) -> None:
        import json
        import tomllib

        from squadron.benchmark.confinement import CLAUDE_SETTINGS_KEY
        from squadron.providers.base import ProfileName

        with self._sandbox(tmp_path, real_home) as sandbox:
            sandbox.producer_env(ProfileName.SDK)
            config = sandbox.home / ".config" / "squadron" / "config.toml"
            with config.open("rb") as handle:
                settings = json.loads(tomllib.load(handle)[CLAUDE_SETTINGS_KEY])

        filesystem = settings["sandbox"]["filesystem"]
        assert filesystem["denyRead"] == [str(real_home.resolve())]
        assert filesystem["allowRead"][:2] == [str(sandbox.tree.resolve()), str(sandbox.home.resolve())]

    def test_api_key_profile_gets_its_variable(self, tmp_path: Path, real_home: Path) -> None:
        from squadron.providers.base import ProfileName

        with self._sandbox(tmp_path, real_home) as sandbox:
            env = sandbox.producer_env(ProfileName.OPENAI)
            assert env[self.API_KEY_VARIABLE] == "api-key-value"
            assert "GH_TOKEN" not in env

    def test_a_second_call_changes_nothing_in_the_home(self, tmp_path: Path, real_home: Path) -> None:
        from squadron.providers.base import ProfileName

        with self._sandbox(tmp_path, real_home) as sandbox:
            sandbox.producer_env(ProfileName.OPENAI_OAUTH)
            carried = sandbox.home / ".codex" / "auth.json"
            carried.write_text('{"token": "refreshed by the tool"}')

            def snapshot() -> list[tuple[str, int, int]]:
                return sorted(
                    (str(p.relative_to(sandbox.home)), p.stat().st_mtime_ns, p.stat().st_size)
                    for p in sandbox.home.rglob("*")
                    if p.is_file() or p.is_symlink()
                )

            before = snapshot()
            sandbox.producer_env(ProfileName.OPENAI_OAUTH)
            assert snapshot() == before
            assert carried.read_text() == '{"token": "refreshed by the tool"}'

    def test_process_env_still_carries_no_grant(self, tmp_path: Path, real_home: Path) -> None:
        from squadron.providers.base import ProfileName

        with self._sandbox(tmp_path, real_home) as sandbox:
            sandbox.producer_env(ProfileName.OPENAI)
            assert self.API_KEY_VARIABLE not in sandbox.process_env()
            assert "GH_TOKEN" not in sandbox.process_env()

    def test_missing_credential_fails_explicitly(self, tmp_path: Path, real_home: Path) -> None:
        from squadron.benchmark.scrubbed_env import MissingCredentialError
        from squadron.providers.base import ProfileName

        with self._sandbox(tmp_path, real_home, with_api_key=False) as sandbox:
            with pytest.raises(MissingCredentialError):
                sandbox.producer_env(ProfileName.OPENAI)


class TestCheckoutBranch:
    """The tree starts detached; a committing producer needs a branch (slice 424)."""

    def _sandbox(self, tmp_path: Path) -> BenchmarkSandbox:
        source = git_tree("env_ok", tmp_path)
        return BenchmarkSandbox(
            start_sha=head(source),
            sandbox_id=SANDBOX_ID,
            repo_root=source,
            runner=SubprocessRunner(),
            adapter=_NoInstallAdapter(),  # type: ignore[arg-type]
            harness_env=dict(os.environ),
            install_timeout_s=60,
            suite_timeout_s=60,
            root=tmp_path / "root",
        )

    def _git(self, tree: Path, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(tree), *args], capture_output=True, text=True, check=True
        ).stdout.strip()

    def test_the_tree_starts_detached_and_ends_on_the_named_branch_at_the_start_commit(
        self, tmp_path: Path
    ) -> None:
        with self._sandbox(tmp_path) as sandbox:
            assert self._git(sandbox.tree, "branch", "--show-current") == ""
            start = head(sandbox.tree)
            sandbox.checkout_branch("benchmark-replay")
            assert self._git(sandbox.tree, "branch", "--show-current") == "benchmark-replay"
            assert head(sandbox.tree) == start

    def test_the_tree_stays_history_free(self, tmp_path: Path) -> None:
        with self._sandbox(tmp_path) as sandbox:
            sandbox.checkout_branch("benchmark-replay")
            assert self._git(sandbox.tree, "rev-list", "--all", "--count") == "1"

    def test_a_branch_that_cannot_be_made_raises_with_git_output(self, tmp_path: Path) -> None:
        from squadron.replay.history_free_sandbox import SandboxError

        with self._sandbox(tmp_path) as sandbox:
            with pytest.raises(SandboxError, match="not a valid branch name"):
                sandbox.checkout_branch("bad..name")
