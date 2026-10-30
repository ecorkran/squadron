"""Throwaway-repo builders for the slice-range resolver tests (slice 403, Task 8).

One function per history shape. Each builds a repo on ``main`` under *tmp_path* and
returns the repo path with the shas the tests assert on. Identity and the default
branch come from the hermetic git config (``tests/conftest.py``).
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from tests.conftest import run_test_git


class LandingShas(NamedTuple):
    """The shas one landing must resolve to. ``merge`` is None for a fast-forward."""

    fork: str
    before: str
    tip: str
    after: str
    merge: str | None


class TwoLandingShas(NamedTuple):
    """Both landings of a slice merged twice, oldest first."""

    first: LandingShas
    second: LandingShas


def _head(repo: Path, ref: str = "HEAD") -> str:
    return run_test_git(repo, "rev-parse", ref).strip()


def _commit(repo: Path, label: str) -> str:
    """Commit a new file named after *label* on the current branch; return the sha."""
    (repo / f"{label}.txt").write_text(f"{label}\n")
    run_test_git(repo, "add", f"{label}.txt")
    run_test_git(repo, "commit", "-q", "-m", label)
    return _head(repo)


def _init_repo(tmp_path: Path) -> tuple[Path, str]:
    """A repo on ``main`` with one commit; returns the repo and that commit."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    run_test_git(repo, "init", "-q", "-b", "main")
    return repo, _commit(repo, "init")


def _merge_no_ff(repo: Path, branch: str, message: str) -> str:
    run_test_git(repo, "merge", "-q", "--no-ff", "-m", message, branch)
    return _head(repo)


def clone_repo(source: Path, tmp_path: Path) -> Path:
    """Clone *source*; the clone has no local slice branches and no reflog history."""
    destination = tmp_path / "clone"
    run_test_git(tmp_path, "clone", "-q", str(source), str(destination))
    return destination


def no_landing(tmp_path: Path) -> Path:
    """A repo with no slice branch and no merge."""
    repo, _ = _init_repo(tmp_path)
    _commit(repo, "main-work")
    return repo


def no_ff_landing(tmp_path: Path) -> tuple[Path, LandingShas]:
    """Slice 401 forked from main, main moves, then a ``--no-ff`` merge lands it."""
    repo, fork = _init_repo(tmp_path)
    run_test_git(repo, "checkout", "-q", "-b", "401-slice.x")
    tip = _commit(repo, "slice-work")
    run_test_git(repo, "checkout", "-q", "main")
    before = _commit(repo, "main-moves")
    merge = _merge_no_ff(repo, "401-slice.x", "Merge slice 401: x")
    return repo, LandingShas(fork=fork, before=before, tip=tip, after=merge, merge=merge)


def fast_forward_landing(tmp_path: Path) -> tuple[Path, LandingShas]:
    """Slice 402 created with ``git checkout -b`` and fast-forwarded into main."""
    repo, fork = _init_repo(tmp_path)
    run_test_git(repo, "checkout", "-q", "-b", "402-slice.y")
    _commit(repo, "slice-work-1")
    tip = _commit(repo, "slice-work-2")
    run_test_git(repo, "checkout", "-q", "main")
    run_test_git(repo, "merge", "-q", "--ff-only", "402-slice.y")
    return repo, LandingShas(fork=fork, before=fork, tip=tip, after=tip, merge=None)


def sync_merge(tmp_path: Path) -> tuple[Path, LandingShas]:
    """Main is merged into slice 403 (a sync merge naming the branch), then the slice lands."""
    repo, _ = _init_repo(tmp_path)
    run_test_git(repo, "checkout", "-q", "-b", "403-slice.z")
    _commit(repo, "slice-work-1")
    run_test_git(repo, "checkout", "-q", "main")
    _commit(repo, "main-moves-1")
    run_test_git(repo, "checkout", "-q", "403-slice.z")
    _merge_no_ff(repo, "main", "Merge branch 'main' into 403-slice.z")
    tip = _commit(repo, "slice-work-2")
    run_test_git(repo, "checkout", "-q", "main")
    before = _commit(repo, "main-moves-2")
    merge = _merge_no_ff(repo, "403-slice.z", "Merge slice 403: z")
    # The fork is where main and the slice last agreed, which the sync merge moved forward.
    fork = run_test_git(repo, "merge-base", before, tip).strip()
    return repo, LandingShas(fork=fork, before=before, tip=tip, after=merge, merge=merge)


def two_landings(tmp_path: Path) -> tuple[Path, TwoLandingShas]:
    """Slice 404 merged twice with ``--no-ff``: the slice, then a follow-up."""
    repo, fork = _init_repo(tmp_path)
    run_test_git(repo, "checkout", "-q", "-b", "404-slice.w")
    first_tip = _commit(repo, "slice-work-1")
    run_test_git(repo, "checkout", "-q", "main")
    first_before = _commit(repo, "main-moves-1")
    first_merge = _merge_no_ff(repo, "404-slice.w", "Merge slice 404: w")
    run_test_git(repo, "checkout", "-q", "404-slice.w")
    second_tip = _commit(repo, "slice-work-2")
    run_test_git(repo, "checkout", "-q", "main")
    second_before = _commit(repo, "main-moves-2")
    second_merge = _merge_no_ff(repo, "404-slice.w", "Merge slice 404: w follow-up")
    return repo, TwoLandingShas(
        first=LandingShas(fork, first_before, first_tip, first_merge, first_merge),
        second=LandingShas(first_tip, second_before, second_tip, second_merge, second_merge),
    )


def rebased_branch(tmp_path: Path) -> tuple[Path, str]:
    """Slice 405 created at a commit the rebase then drops, so its reflog fork isn't an
    ancestor of the tip; main fast-forwards to the tip. Returns the repo and the tip."""
    repo, _ = _init_repo(tmp_path)
    run_test_git(repo, "checkout", "-q", "-b", "scratch")
    _commit(repo, "scratch-work")
    run_test_git(repo, "checkout", "-q", "-b", "405-slice.r")
    _commit(repo, "slice-work")
    run_test_git(repo, "checkout", "-q", "main")
    _commit(repo, "main-moves")
    run_test_git(repo, "checkout", "-q", "405-slice.r")
    run_test_git(repo, "rebase", "-q", "--onto", "main", "scratch", "405-slice.r")
    run_test_git(repo, "checkout", "-q", "main")
    run_test_git(repo, "merge", "-q", "--ff-only", "405-slice.r")
    return repo, _head(repo, "405-slice.r")


def empty_branch(tmp_path: Path) -> Path:
    """Slice 406 branched from main with no commits of its own, 'merged' while main moves on."""
    repo, _ = _init_repo(tmp_path)
    run_test_git(repo, "branch", "406-slice.e")
    _commit(repo, "main-moves")
    run_test_git(repo, "merge", "-q", "406-slice.e")
    return repo


def landed_elsewhere(tmp_path: Path) -> Path:
    """Slice 407 merged into a side branch, which is then merged into main."""
    repo, _ = _init_repo(tmp_path)
    run_test_git(repo, "checkout", "-q", "-b", "side")
    run_test_git(repo, "checkout", "-q", "-b", "407-slice.l")
    _commit(repo, "slice-work")
    run_test_git(repo, "checkout", "-q", "side")
    _merge_no_ff(repo, "407-slice.l", "Merge slice 407: l")
    run_test_git(repo, "checkout", "-q", "main")
    _commit(repo, "main-moves")
    _merge_no_ff(repo, "side", "Merge branch 'side' into main")
    return repo


def not_landed(tmp_path: Path) -> Path:
    """Slice 408 has commits and was never merged."""
    repo, _ = _init_repo(tmp_path)
    run_test_git(repo, "checkout", "-q", "-b", "408-slice.n")
    _commit(repo, "slice-work")
    run_test_git(repo, "checkout", "-q", "main")
    _commit(repo, "main-moves")
    return repo
