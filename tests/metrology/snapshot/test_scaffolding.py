"""Smoke test for the snapshot fixtures."""

from __future__ import annotations

from squadron.metrology.store import MetrologyStore
from tests.conftest import run_test_git
from tests.metrology.snapshot.conftest import SnapshotRepoFactory


def test_fixtures_build_a_committed_repo_and_an_empty_store(
    snapshot_git_repo: SnapshotRepoFactory, snapshot_store: MetrologyStore
) -> None:
    repo = snapshot_git_repo({"src/a.py": "x = 1\n"})

    assert run_test_git(repo, "ls-files").split() == ["src/a.py"]
    assert run_test_git(repo, "status", "--porcelain") == ""
    assert snapshot_store.store_dir.parent == repo.parent
