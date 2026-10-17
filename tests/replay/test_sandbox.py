"""The history-free replay sandbox and its orphan sweep (slice 177 D3, D10)."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest

from squadron.core.process_lock import ProcessLock, current_process_lock
from squadron.core.process_runner import SubprocessRunner
from squadron.replay.sandbox import ReplaySandbox, SandboxError, replays_root, sweep_orphans
from tests.replay.sandbox_support import HybridRunner
from tests.stats.repo_support import StatsRepo

_T1 = "2026-10-01T10:00:00+00:00"
_T2 = "2026-10-02T10:00:00+00:00"
_PLAN = "project-documents/user/architecture/140-slices.pipeline-foundation.md"
_PLAN_TEXT = "# Plan\n\n1. [ ] **(176) Effort Calibration** — text. Effort: 4/5\n"
_LATER = "project-documents/user/slices/176-slice.later.md"
_REPLAY_ID = "replay-20261101-abcd1234"


@pytest.fixture
def repo(stats_repo: StatsRepo) -> StatsRepo:
    """A start commit holding the plan, and a later commit the sandbox must not see."""
    stats_repo.commit("init", {_PLAN: _PLAN_TEXT}, _T1)
    stats_repo.commit("docs: add design", {_LATER: "# the original\n"}, _T2)
    return stats_repo


@pytest.fixture
def start_sha(repo: StatsRepo) -> str:
    return repo.git("rev-parse", "HEAD~1")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "replays"


def _sandbox(
    repo: StatsRepo, sha: str, root: Path, runner: HybridRunner, **kw: object
) -> ReplaySandbox:
    return ReplaySandbox(
        start_sha=sha,
        replay_id=_REPLAY_ID,
        repo_root=repo.root,
        slice_index=176,
        runner=runner,
        root=root,
        **kw,  # type: ignore[arg-type]
    )


def _git(path: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _gone(root: Path) -> bool:
    return not (root / _REPLAY_ID).exists() and not (root / f"{_REPLAY_ID}.lock").exists()


def test_replays_root_is_under_config_squadron() -> None:
    assert replays_root().parts[-3:] == (".config", "squadron", "replays")


def test_sandbox_holds_one_commit_and_nothing_later(
    repo: StatsRepo, start_sha: str, root: Path
) -> None:
    runner = HybridRunner()
    with _sandbox(repo, start_sha, root, runner) as sandbox:
        assert _git(sandbox.path, "rev-list", "--all", "--count") == "1"
        assert _git(sandbox.path, "rev-parse", "HEAD") == start_sha
        assert _git(sandbox.path, "branch", "--show-current") == f"replay/{_REPLAY_ID}"
        assert (sandbox.path / _PLAN).is_file()
        assert not (sandbox.path / _LATER).exists()
        assert (root / f"{_REPLAY_ID}.lock").is_file()
    assert _gone(root)


def test_cf_is_set_up_for_the_slices_initiative(repo: StatsRepo, start_sha: str, root: Path) -> None:
    runner = HybridRunner()
    with _sandbox(repo, start_sha, root, runner):
        pass

    assert runner.cf_calls() == [
        ("init", "--lite", "--no-ide", "--name", f"replay-{_REPLAY_ID}"),
        ("config", "set", "git.integration_branch", f"replay/{_REPLAY_ID}"),
        ("set", "arch", "140"),
        ("project", "rm", f"replay-{_REPLAY_ID}", "--yes"),
    ]


def test_a_relative_repo_root_is_resolved(
    repo: StatsRepo, start_sha: str, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(repo.root)
    sandbox = ReplaySandbox(
        start_sha=start_sha,
        replay_id=_REPLAY_ID,
        repo_root=Path("."),
        slice_index=176,
        runner=HybridRunner(),
        root=root,
    )
    with sandbox:
        assert _git(sandbox.path, "rev-list", "--all", "--count") == "1"


def test_cleanup_runs_when_the_body_raises(repo: StatsRepo, start_sha: str, root: Path) -> None:
    runner = HybridRunner()
    with pytest.raises(ValueError, match="boom"):
        with _sandbox(repo, start_sha, root, runner):
            raise ValueError("boom")
    assert _gone(root)
    assert ("project", "rm", f"replay-{_REPLAY_ID}", "--yes") in runner.cf_calls()


def test_cleanup_runs_on_keyboard_interrupt(repo: StatsRepo, start_sha: str, root: Path) -> None:
    with pytest.raises(KeyboardInterrupt):
        with _sandbox(repo, start_sha, root, HybridRunner()):
            raise KeyboardInterrupt
    assert _gone(root)


def test_keep_leaves_the_sandbox_in_place(repo: StatsRepo, start_sha: str, root: Path) -> None:
    runner = HybridRunner()
    with _sandbox(repo, start_sha, root, runner) as sandbox:
        sandbox.keep()
    assert (root / _REPLAY_ID).is_dir()
    assert ("project", "rm", f"replay-{_REPLAY_ID}", "--yes") not in runner.cf_calls()


def test_a_start_point_declaring_submodules_is_refused(repo: StatsRepo, root: Path) -> None:
    repo.commit("add module", {".gitmodules": '[submodule "x"]\n\tpath = x\n\turl = ../x\n'}, _T2)
    sha = repo.git("rev-parse", "HEAD")

    with pytest.raises(SandboxError, match=r"\.gitmodules"):
        with _sandbox(repo, sha, root, HybridRunner()):
            pytest.fail("the sandbox should not have opened")
    assert _gone(root)


def test_an_empty_gitmodules_file_is_not_a_submodule(repo: StatsRepo, root: Path) -> None:
    repo.commit("empty gitmodules", {".gitmodules": ""}, _T2)
    sha = repo.git("rev-parse", "HEAD")

    with _sandbox(repo, sha, root, HybridRunner()) as sandbox:
        assert (sandbox.path / ".gitmodules").is_file()


def test_an_unreadable_gitmodules_is_a_sandbox_error_and_leaves_nothing(
    repo: StatsRepo, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo.commit("empty gitmodules", {".gitmodules": ""}, _T2)
    sha = repo.git("rev-parse", "HEAD")
    real_read_text = Path.read_text

    def read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".gitmodules":
            raise PermissionError("denied")
        return real_read_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", read_text)

    with pytest.raises(SandboxError, match=r"cannot read \.gitmodules"):
        with _sandbox(repo, sha, root, HybridRunner()):
            pytest.fail("the sandbox should not have opened")
    assert _gone(root)


def test_an_unwritable_lock_is_a_sandbox_error_and_leaves_nothing(
    repo: StatsRepo, start_sha: str, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_write_text = Path.write_text

    def write_text(self: Path, *args: object, **kwargs: object) -> int:
        if self.suffix == ".lock":
            raise OSError("disk full")
        return real_write_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "write_text", write_text)

    with pytest.raises(SandboxError, match="cannot write sandbox lock"):
        with _sandbox(repo, start_sha, root, HybridRunner()):
            pytest.fail("the sandbox should not have opened")
    assert _gone(root)


def test_a_failed_fetch_carries_stderr_and_leaves_nothing(repo: StatsRepo, root: Path) -> None:
    with pytest.raises(SandboxError, match="fetch") as caught:
        with _sandbox(repo, "0" * 40, root, HybridRunner()):
            pytest.fail("the sandbox should not have opened")
    assert "not our ref" in str(caught.value) or "fatal" in str(caught.value)
    assert _gone(root)


def test_a_slice_in_no_plan_names_the_slice_and_start_sha(
    repo: StatsRepo, start_sha: str, root: Path
) -> None:
    runner = HybridRunner()
    sandbox = ReplaySandbox(
        start_sha=start_sha,
        replay_id=_REPLAY_ID,
        repo_root=repo.root,
        slice_index=999,
        runner=runner,
        root=root,
    )
    with pytest.raises(SandboxError, match=f"slice 999.*{start_sha}"):
        with sandbox:
            pytest.fail("the sandbox should not have opened")
    assert _gone(root)
    assert runner.cf_calls() == []  # nothing was registered with cf


def test_a_failed_cf_init_carries_stderr_and_leaves_nothing(
    repo: StatsRepo, start_sha: str, root: Path
) -> None:
    runner = HybridRunner()
    runner.cf_failures[("init",)] = "cf exploded"
    with pytest.raises(SandboxError, match="cf exploded"):
        with _sandbox(repo, start_sha, root, runner):
            pytest.fail("the sandbox should not have opened")
    assert _gone(root)
    assert not any(call[:2] == ("project", "rm") for call in runner.cf_calls())


def test_a_failed_cf_project_rm_warns_and_does_not_raise(
    repo: StatsRepo, start_sha: str, root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    runner = HybridRunner()
    runner.cf_failures[("project", "rm")] = "no such project"
    with caplog.at_level(logging.WARNING):
        with _sandbox(repo, start_sha, root, runner):
            pass
    assert f"could not remove cf project replay-{_REPLAY_ID}" in caplog.text
    assert _gone(root)  # the directory is still removed


def _dead_pid() -> int:
    done = subprocess.Popen(["true"])
    done.wait()
    return done.pid


def _plant(root: Path, name: str, lock: ProcessLock | None) -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    if lock is not None:
        (root / f"{name}.lock").write_text(lock.to_json())
    return directory


def test_sweep_removes_dead_and_missing_locks_keeps_live_ones(
    root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    runner = SubprocessRunner()
    live = current_process_lock(runner)
    dead = _plant(root, "dead", ProcessLock(pid=_dead_pid(), started_at=live.started_at))
    unlocked = _plant(root, "unlocked", None)
    kept = _plant(root, "live", live)

    with caplog.at_level(logging.WARNING):
        sweep_orphans(HybridRunner(), root)

    assert not dead.exists() and not (root / "dead.lock").exists()
    assert not unlocked.exists()
    assert kept.is_dir() and (root / "live.lock").is_file()
    assert caplog.text.count("removing orphaned replay sandbox") == 2


def test_sweep_removes_only_replay_cf_projects_whose_directory_is_gone(
    root: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    existing = tmp_path / "exists"
    existing.mkdir()
    runner = HybridRunner()
    runner.cf_projects = [
        {"name": "replay-stale", "projectPath": str(tmp_path / "gone")},
        {"name": "replay-live", "projectPath": str(existing)},
        {"name": "squadron", "projectPath": str(tmp_path / "also-gone")},
        {"name": "replay-pathless"},
    ]

    with caplog.at_level(logging.WARNING):
        sweep_orphans(runner, root)

    assert [call for call in runner.cf_calls() if call[:2] == ("project", "rm")] == [
        ("project", "rm", "replay-stale", "--yes")
    ]
    assert "removing cf project replay-stale" in caplog.text


def test_sweep_never_raises_on_an_unusable_cf_listing(
    root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    runner = HybridRunner()
    runner.cf_failures[("project", "list")] = "cf is down"
    with caplog.at_level(logging.WARNING):
        sweep_orphans(runner, root)
    assert "could not list cf projects" in caplog.text
