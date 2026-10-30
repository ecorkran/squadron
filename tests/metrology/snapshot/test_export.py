"""Commit export to a temp tree (slice 403, D5, criterion 4)."""

from __future__ import annotations

import io
import logging
import subprocess
import tarfile
from pathlib import Path

import pytest

from squadron.metrology.errors import SnapshotExportError
from squadron.metrology.snapshot.export import export_commit, resolve_commit
from tests.conftest import run_test_git
from tests.metrology.snapshot.conftest import SnapshotRepoFactory

FILES = {"src/a.py": "a = 1\n", "docs/x.md": "# x\n", "vendor/v.py": "v = 1\n"}


@pytest.fixture
def repo(snapshot_git_repo: SnapshotRepoFactory) -> Path:
    """A repo whose HEAD~1 holds FILES and whose HEAD adds src/b.py."""
    root = snapshot_git_repo(FILES)
    (root / "src" / "b.py").write_text("b = 1\n", encoding="utf-8")
    run_test_git(root, "add", "-A")
    run_test_git(root, "commit", "-q", "-m", "add b")
    return root


@pytest.fixture
def export_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Where export temp directories are created, so a test can see that none is left."""
    directory = tmp_path / "export-tmp"
    directory.mkdir()
    monkeypatch.setattr("tempfile.tempdir", str(directory))
    return directory


@pytest.fixture
def environment(tmp_path: Path) -> Path:
    root = tmp_path / "live"
    root.mkdir()
    return root


def git_state(repo: Path) -> tuple[list[tuple[str, int, int]], str]:
    """``git status --porcelain`` and the ``.git`` listing (path, size, mtime).

    ``--no-optional-locks`` stops status from refreshing ``.git/index`` itself, so a
    difference between two calls can only come from what ran between them.
    """
    status = run_test_git(repo, "--no-optional-locks", "status", "--porcelain")
    listing = [
        (str(path.relative_to(repo)), path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted((repo / ".git").rglob("*"))
        if path.is_file()
    ]
    return listing, status


def errors_logged(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]


def archive_that_writes(tar_bytes: bytes):
    """A fake ``run_git`` whose ``archive`` call writes *tar_bytes* to the ``-o`` path."""

    def fake(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str]:
        Path(args[args.index("-o") + 1]).write_bytes(tar_bytes)
        return subprocess.CompletedProcess(args, 0, "", "")

    return fake


def test_export_lists_the_commits_tracked_files_minus_exclusions(repo: Path, environment: Path) -> None:
    sha = resolve_commit(repo, "HEAD~1")

    with export_commit(repo, sha, ["vendor/**"], environment) as exported:
        assert exported.files == ["docs/x.md", "src/a.py"]
        assert (exported.root / "src" / "a.py").read_text(encoding="utf-8") == "a = 1\n"
        assert not (exported.root / "src" / "b.py").exists()
        assert not (exported.root / "vendor").exists()


def test_export_leaves_the_repository_untouched(repo: Path, environment: Path) -> None:
    before = git_state(repo)

    with export_commit(repo, resolve_commit(repo, "HEAD"), [], environment):
        pass

    assert git_state(repo) == before


def test_temp_directory_is_removed_after_a_normal_exit_and_after_an_exception(
    repo: Path, environment: Path, export_tmp: Path
) -> None:
    sha = resolve_commit(repo, "HEAD")
    with export_commit(repo, sha, [], environment) as exported:
        assert exported.root.parent.parent == export_tmp
        assert list(export_tmp.iterdir())
    assert list(export_tmp.iterdir()) == []

    with pytest.raises(RuntimeError, match="boom"), export_commit(repo, sha, [], environment):
        raise RuntimeError("boom")
    assert list(export_tmp.iterdir()) == []


def test_a_link_outside_the_tree_is_refused_naming_the_member(
    repo: Path,
    environment: Path,
    export_tmp: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as crafted:
        link = tarfile.TarInfo("evil-link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside"
        crafted.addfile(link)
    monkeypatch.setattr(
        "squadron.metrology.snapshot.export.run_git", archive_that_writes(buffer.getvalue())
    )

    with caplog.at_level(logging.ERROR), pytest.raises(SnapshotExportError, match="evil-link"):
        with export_commit(repo, "a" * 40, [], environment):
            pass

    assert any("evil-link" in line for line in errors_logged(caplog))
    assert list(export_tmp.iterdir()) == []


def test_unknown_revision_raises_naming_it(repo: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR), pytest.raises(SnapshotExportError, match="no-such-rev"):
        resolve_commit(repo, "no-such-rev")

    assert any("no-such-rev" in line for line in errors_logged(caplog))


def test_archive_that_cannot_answer_names_the_timeout_and_cleans_up(
    repo: Path,
    environment: Path,
    export_tmp: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr("squadron.metrology.snapshot.export.run_git", lambda args, *, cwd: None)

    with caplog.at_level(logging.ERROR), pytest.raises(SnapshotExportError, match="timeout"):
        with export_commit(repo, "a" * 40, [], environment):
            pass

    assert any("git archive" in line for line in errors_logged(caplog))
    assert list(export_tmp.iterdir()) == []


def test_extraction_failure_raises_and_cleans_up(
    repo: Path,
    environment: Path,
    export_tmp: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def disk_full(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("tarfile.TarFile.extractall", disk_full)

    with caplog.at_level(logging.ERROR), pytest.raises(SnapshotExportError, match="disk full"):
        with export_commit(repo, resolve_commit(repo, "HEAD"), [], environment):
            pass

    assert any("disk full" in line for line in errors_logged(caplog))
    assert list(export_tmp.iterdir()) == []


def test_node_modules_is_linked_only_when_the_live_one_exists(repo: Path, environment: Path) -> None:
    sha = resolve_commit(repo, "HEAD")
    with export_commit(repo, sha, [], environment) as exported:
        assert not (exported.root / "node_modules").exists()

    live = environment / "node_modules"
    live.mkdir()
    with export_commit(repo, sha, [], environment) as exported:
        link = exported.root / "node_modules"
        assert link.is_symlink()
        assert link.resolve() == live.resolve()


def test_failed_symlink_raises_and_cleans_up(
    repo: Path,
    environment: Path,
    export_tmp: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    (environment / "node_modules").mkdir()

    def refuse(*args: object, **kwargs: object) -> None:
        raise OSError("operation not permitted")

    monkeypatch.setattr("squadron.metrology.snapshot.export.os.symlink", refuse)

    with caplog.at_level(logging.ERROR), pytest.raises(SnapshotExportError, match="node_modules"):
        with export_commit(repo, resolve_commit(repo, "HEAD"), [], environment):
            pass

    assert any("operation not permitted" in line for line in errors_logged(caplog))
    assert list(export_tmp.iterdir()) == []
