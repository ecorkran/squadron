"""Shared repository builders and assertions for the squash tests (slice 948)."""

from __future__ import annotations

from pathlib import Path

from squadron.pipeline.squash import SquashKind, SquashTarget
from tests.conftest import run_test_git
from tests.pipeline.commit_fixtures import DESIGN_FILE, SLICE, write_file

DEVLOG = "DEVLOG.md"
FOREIGN_FILE = "src/app.py"


def commit_files(repo: Path, message: str, *paths: str) -> str:
    """Change each path (appending a line) and commit them; returns the new sha."""
    for relative in paths:
        target = repo / relative
        previous = target.read_text() if target.is_file() else ""
        write_file(repo, relative, f"{previous}{message}\n")
    run_test_git(repo, "add", "-A")
    run_test_git(repo, "commit", "-q", "-m", message)
    return head(repo)


def planning_run(repo: Path, count: int, artifact: str = DESIGN_FILE) -> list[str]:
    """``count`` commits touching only ``artifact`` (every other one also DEVLOG); oldest first."""
    shas: list[str] = []
    for number in range(1, count + 1):
        paths = (artifact, DEVLOG) if number % 2 == 0 else (artifact,)
        shas.append(commit_files(repo, f"docs: planning round {number}", *paths))
    return shas


def head(repo: Path) -> str:
    return run_test_git(repo, "rev-parse", "HEAD").strip()


def history(repo: Path) -> tuple[str, str, str]:
    """HEAD, the full log and the tag list: what a refused or dry run must leave alone."""
    return head(repo), run_test_git(repo, "log", "--format=%H %s"), run_test_git(repo, "tag", "-l")


def assert_history_unchanged(repo: Path, before: tuple[str, str, str]) -> None:
    assert history(repo) == before


def squash_target(kind: SquashKind = SquashKind.SLICE, index: int = SLICE) -> SquashTarget:
    return SquashTarget(kind, index)
