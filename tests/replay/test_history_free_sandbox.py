"""The history-free checkout shared by replay and benchmark sandboxes (slice 421 D4)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from squadron.core.process_runner import SubprocessRunner
from squadron.replay.history_free_sandbox import HistoryFreeSandbox, SandboxError
from tests.stats.repo_support import StatsRepo

_T1 = "2026-10-01T10:00:00+00:00"
_T2 = "2026-10-02T10:00:00+00:00"
_LATER = "later.txt"
_ID = "hfs-1"


@pytest.fixture
def repo(stats_repo: StatsRepo) -> StatsRepo:
    stats_repo.commit("init", {"a.txt": "a\n"}, _T1)
    stats_repo.commit("later", {_LATER: "later\n"}, _T2)
    return stats_repo


@pytest.fixture
def start_sha(repo: StatsRepo) -> str:
    return repo.git("rev-parse", "HEAD~1")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "root"


def _sandbox(repo: StatsRepo, sha: str, root: Path) -> HistoryFreeSandbox:
    return HistoryFreeSandbox(
        start_sha=sha,
        sandbox_id=_ID,
        repo_root=repo.root,
        runner=SubprocessRunner(),
        root=root,
    )


def _git(path: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _gone(root: Path) -> bool:
    return not (root / _ID).exists() and not (root / f"{_ID}.lock").exists()


def test_one_commit_at_start_sha_and_no_later_history(
    repo: StatsRepo, start_sha: str, root: Path
) -> None:
    with _sandbox(repo, start_sha, root) as sandbox:
        assert _git(sandbox.path, "rev-list", "--all", "--count") == "1"
        assert _git(sandbox.path, "rev-parse", "HEAD") == start_sha
        assert (sandbox.path / "a.txt").is_file()
        assert not (sandbox.path / _LATER).exists()
        # No branch is created: HEAD is detached.
        assert _git(sandbox.path, "branch", "--show-current") == ""
    assert _gone(root)


def test_submodule_start_point_is_refused_and_cleaned(repo: StatsRepo, root: Path) -> None:
    repo.commit("add module", {".gitmodules": '[submodule "x"]\n\tpath = x\n\turl = ../x\n'}, _T2)
    with pytest.raises(SandboxError, match="submodules"):
        with _sandbox(repo, repo.git("rev-parse", "HEAD"), root):
            pytest.fail("must not enter")
    assert _gone(root)


def test_lock_is_written_before_the_directory_exists(
    repo: StatsRepo, start_sha: str, root: Path
) -> None:
    seen: list[bool] = []

    class Spy(SubprocessRunner):
        def run(self, argv, **kwargs):  # type: ignore[no-untyped-def,override]
            if tuple(argv[:2]) == ("git", "init"):
                seen.append((root / f"{_ID}.lock").is_file() and not (root / _ID).exists())
            return super().run(argv, **kwargs)

    sandbox = HistoryFreeSandbox(
        start_sha=start_sha, sandbox_id=_ID, repo_root=repo.root, runner=Spy(), root=root
    )
    with sandbox:
        pass
    assert seen == [True]


def test_failed_build_cleans_up(repo: StatsRepo, root: Path) -> None:
    with pytest.raises(SandboxError, match="fetch"):
        with _sandbox(repo, "0" * 40, root):
            pytest.fail("must not enter")
    assert _gone(root)


def test_cleanup_on_body_exception_and_keyboard_interrupt(
    repo: StatsRepo, start_sha: str, root: Path
) -> None:
    with pytest.raises(ValueError, match="boom"):
        with _sandbox(repo, start_sha, root):
            raise ValueError("boom")
    assert _gone(root)
    with pytest.raises(KeyboardInterrupt):
        with _sandbox(repo, start_sha, root):
            raise KeyboardInterrupt
    assert _gone(root)


def test_keep_leaves_directory_and_lock(repo: StatsRepo, start_sha: str, root: Path) -> None:
    with _sandbox(repo, start_sha, root) as sandbox:
        sandbox.keep()
    assert (root / _ID).is_dir()
    assert (root / f"{_ID}.lock").is_file()
