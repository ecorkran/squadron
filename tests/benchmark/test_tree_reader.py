"""``GitTreeReader``: files and listings of a commit, read with git (slice 425 Task 11)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.benchmark.tree_reader import GitTreeReader, TreeReadError
from squadron.core.process_runner import ProcessResult, ProcessTimedOutError, SubprocessRunner
from tests.conftest import run_test_git


@pytest.fixture
def repo_sha(temp_git_repo: Path) -> tuple[Path, str]:
    (temp_git_repo / "pkg").mkdir()
    (temp_git_repo / "pkg" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    (temp_git_repo / "odd name.py").write_text("y = 2\n", encoding="utf-8")
    (temp_git_repo / "blob.bin").write_bytes(b"\xff\xfe\x00\x01")
    run_test_git(temp_git_repo, "add", "-A")
    run_test_git(temp_git_repo, "commit", "-q", "-m", "add files")
    return temp_git_repo, run_test_git(temp_git_repo, "rev-parse", "HEAD").strip()


def test_reads_a_file_at_the_commit_not_the_working_tree(repo_sha: tuple[Path, str]) -> None:
    repo, sha = repo_sha
    (repo / "pkg" / "mod.py").write_text("x = 2\n", encoding="utf-8")
    reader = GitTreeReader(SubprocessRunner(), repo, sha)
    assert reader.read("pkg/mod.py") == b"x = 1\n"


def test_lists_every_tracked_path_including_an_awkward_name(repo_sha: tuple[Path, str]) -> None:
    repo, sha = repo_sha
    paths = GitTreeReader(SubprocessRunner(), repo, sha).list_paths()
    assert {"pkg/mod.py", "odd name.py", "blob.bin"} <= set(paths)


def test_a_missing_path_raises_with_the_stderr_tail_and_logs_error(
    repo_sha: tuple[Path, str], caplog: pytest.LogCaptureFixture
) -> None:
    repo, sha = repo_sha
    reader = GitTreeReader(SubprocessRunner(), repo, sha)
    with caplog.at_level(logging.ERROR), pytest.raises(TreeReadError, match="does not exist"):
        reader.read("nope.py")
    assert any(r.levelno == logging.ERROR for r in caplog.records)


def test_an_unknown_commit_raises_on_listing(repo_sha: tuple[Path, str]) -> None:
    repo, _ = repo_sha
    with pytest.raises(TreeReadError):
        GitTreeReader(SubprocessRunner(), repo, "0" * 40).list_paths()


def test_content_that_is_not_utf8_raises_instead_of_being_replaced(
    repo_sha: tuple[Path, str], caplog: pytest.LogCaptureFixture
) -> None:
    repo, sha = repo_sha
    with caplog.at_level(logging.ERROR), pytest.raises(TreeReadError, match="UTF-8"):
        GitTreeReader(SubprocessRunner(), repo, sha).read("blob.bin")
    assert any(r.levelno == logging.ERROR for r in caplog.records)


class _HungRunner:
    """A runner whose every call outlives its timeout."""

    def run(self, argv: list[str], **kwargs: object) -> ProcessResult:
        raise ProcessTimedOutError(argv, 30.0)


def test_a_git_timeout_is_a_tree_read_error_and_logs_error(
    repo_sha: tuple[Path, str], caplog: pytest.LogCaptureFixture
) -> None:
    repo, sha = repo_sha
    reader = GitTreeReader(_HungRunner(), repo, sha)  # type: ignore[arg-type]
    with caplog.at_level(logging.ERROR), pytest.raises(TreeReadError, match="exceeded 30.0s"):
        reader.list_paths()
    assert any(r.levelno == logging.ERROR for r in caplog.records)
