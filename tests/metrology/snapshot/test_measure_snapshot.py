"""``measure_snapshot``: measuring a tree without writing a record (slice 425, D12)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from squadron.metrology.snapshot.files import effective_exclusions, resolve_files
from squadron.metrology.snapshot.preflight import read_snapshot_config
from squadron.metrology.snapshot.registry import default_registry
from squadron.metrology.snapshot.take import measure_snapshot
from squadron.metrology.snapshot_models import SourceLanguage
from squadron.metrology.store import MetrologyStore, snapshot_record_id
from tests.metrology.snapshot.builders import make_project_id
from tests.metrology.snapshot.conftest import FakeToolRunner, SnapshotRepoFactory

FILES = {"a.py": "x = 1\n\n\ndef f():\n    return x\n", "b.ts": "const y = 1;\n"}


@pytest.fixture(autouse=True)
def only_git_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PATH holds git and nothing else, so no real linter or type checker can run."""
    git = shutil.which("git")
    assert git is not None, "git is required for these tests"
    bin_dir = tmp_path / "git-only-bin"
    bin_dir.mkdir()
    (bin_dir / "git").symlink_to(git)
    monkeypatch.setenv("PATH", str(bin_dir))


def _store_files(store_root: Path) -> list[Path]:
    return sorted(path for path in store_root.rglob("*") if path.is_file())


def test_returns_a_snapshot_for_the_given_project_and_commit_and_writes_nothing(
    snapshot_git_repo: SnapshotRepoFactory, snapshot_store: MetrologyStore, tmp_path: Path
) -> None:
    repo = snapshot_git_repo(FILES)
    registry = default_registry()
    config = read_snapshot_config(repo)
    files = resolve_files(repo, effective_exclusions(config.project_exclusions, registry.values()))
    project_id = make_project_id("github.com/manta/sandbox-project")
    commit_sha = "d" * 40
    before = _store_files(tmp_path)

    snapshot = measure_snapshot(
        repo, repo, config, registry, FakeToolRunner(), project_id, commit_sha, files
    )

    assert snapshot.project_id == project_id
    assert snapshot.commit_sha == commit_sha
    assert snapshot.snapshot_id == snapshot_record_id(project_id, commit_sha)
    python = next(entry for entry in snapshot.languages if entry.language is SourceLanguage.PYTHON)
    assert python.file_count == 1
    assert snapshot_store.list_snapshots(project_id) == []
    assert _store_files(tmp_path) == before


def test_measures_exactly_the_files_it_is_given(
    snapshot_git_repo: SnapshotRepoFactory,
) -> None:
    repo = snapshot_git_repo(FILES)
    registry = default_registry()
    config = read_snapshot_config(repo)

    snapshot = measure_snapshot(
        repo,
        repo,
        config,
        registry,
        FakeToolRunner(),
        make_project_id(),
        "e" * 40,
        ["a.py"],
    )

    assert [entry.language for entry in snapshot.languages] == [SourceLanguage.PYTHON]
