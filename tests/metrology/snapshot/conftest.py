"""Fixtures for the code-snapshot tests (slice 400)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from squadron.metrology.store import MetrologyStore
from tests.conftest import run_test_git

SnapshotRepoFactory = Callable[[Mapping[str, str]], Path]


@pytest.fixture
def snapshot_git_repo(tmp_path: Path) -> SnapshotRepoFactory:
    """Factory: build a committed git repo under ``tmp_path`` from ``{path: content}``.

    Identity and the default branch come from the hermetic git config, so the
    developer's own git settings never reach a test.
    """

    def build(files: Mapping[str, str]) -> Path:
        repo = tmp_path / "snapshot-repo"
        repo.mkdir()
        run_test_git(repo, "init", "-q", "-b", "main")
        for relative, content in files.items():
            target = repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        run_test_git(repo, "add", "-A")
        run_test_git(repo, "commit", "-q", "-m", "snapshot fixture")
        return repo

    return build


@pytest.fixture
def snapshot_store(tmp_path: Path) -> MetrologyStore:
    """An isolated MetrologyStore rooted under ``tmp_path``."""
    return MetrologyStore(store_dir=tmp_path / "snapshot-store")
