"""Rewrite the history above a squashed run without touching the working tree (#271).

The squashed commit has the same tree as the run's newest commit, so every later
commit is recreated byte for byte with only its parents changed. Nothing is
re-applied or re-merged: nothing can conflict, and merges keep their exact resolution.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from squadron.pipeline.git_ops import GitEnvironmentError
from squadron.review.git_utils import run_git, run_git_bytes

# Header fields rewritten with new values on every recreated commit.
_REPLACED_FIELDS = (b"tree ", b"parent ")
# A signature covers the old object's bytes; it is invalid once the parents change.
_SIGNATURE_FIELDS = (b"gpgsig ", b"gpgsig-sha256 ")


@dataclass(frozen=True)
class Rewritten:
    """The objects a rewrite wrote; no ref points at them yet."""

    squashed: str  # the run collapsed into one commit
    head: str  # the recreated HEAD


def later_commits(newest: str, cwd: Path) -> list[tuple[str, list[str]]]:
    """Commits descending from ``newest`` up to HEAD, parents first, each with its parents."""
    lines = git_stdout(
        ["rev-list", "--reverse", "--topo-order", "--ancestry-path", "--parents", f"{newest}..HEAD"],
        cwd,
    ).splitlines()
    return [(sha, parents) for sha, *parents in (line.split() for line in lines)]


def fork_inside_run(run: list[str], cwd: Path) -> str | None:
    """A run commit other than the newest that a later commit is built on, if any.

    A branch forked from the middle of the run and merged above it would keep the
    run's old commits reachable, so the squash would not remove them.
    """
    inner = set(run[:-1])
    for line in git_stdout(["rev-list", "--parents", f"{run[-1]}..HEAD"], cwd).splitlines():
        for parent in line.split()[1:]:
            if parent in inner:
                return parent
    return None


def rewrite_run(survivor: str, newest: str, parent: str, head: str, cwd: Path) -> Rewritten:
    """Write the squashed commit and recreate every commit above the run onto it.

    The squashed commit keeps the survivor's author, committer and message with the
    newest run commit's tree. Raises ``GitEnvironmentError`` if git cannot write.
    """
    squashed = _rewrite_commit(survivor, [parent], cwd, tree=_tree_of(newest, cwd))
    mapping = {newest: squashed}
    for sha, parents in later_commits(newest, cwd):
        mapping[sha] = _rewrite_commit(sha, [mapping.get(p, p) for p in parents], cwd)
    return Rewritten(squashed, mapping[head])


def _rewrite_commit(sha: str, parents: list[str], cwd: Path, tree: str | None = None) -> str:
    """Write ``sha``'s commit object again with new parents (and optionally a new tree)."""
    raw = _git_bytes(["cat-file", "commit", sha], cwd)
    header, separator, message = raw.partition(b"\n\n")
    if not separator:
        raise GitEnvironmentError(f"git cat-file commit {sha}: no header/message separator")
    fields = _header_fields(header)
    tree_field = next(f for f in fields if f.startswith(b"tree "))
    if tree is not None:
        tree_field = b"tree " + tree.encode("ascii")
    kept = [f for f in fields if not f.startswith(_REPLACED_FIELDS + _SIGNATURE_FIELDS)]
    parent_fields = [b"parent " + p.encode("ascii") for p in parents]
    rebuilt = b"\n".join([tree_field, *parent_fields, *kept]) + separator + message
    written = _git_bytes(["hash-object", "-t", "commit", "-w", "--stdin"], cwd, stdin=rebuilt)
    return written.decode("ascii").strip()


def _header_fields(header: bytes) -> list[bytes]:
    """Header lines grouped into fields; a line starting with a space continues the last."""
    fields: list[bytes] = []
    for line in header.split(b"\n"):
        if line.startswith(b" ") and fields:
            fields[-1] += b"\n" + line
        else:
            fields.append(line)
    return fields


def _tree_of(sha: str, cwd: Path) -> str:
    return git_stdout(["rev-parse", f"{sha}^{{tree}}"], cwd).strip()


def git_stdout(args: list[str], cwd: Path) -> str:
    result = run_git(args, cwd=str(cwd))
    if result is None or result.returncode != 0:
        raise GitEnvironmentError(f"git {' '.join(args)} failed: {failure_text(result)}")
    return result.stdout


def _git_bytes(args: list[str], cwd: Path, stdin: bytes | None = None) -> bytes:
    result = run_git_bytes(args, cwd=str(cwd), stdin=stdin)
    if result is None or result.returncode != 0:
        raise GitEnvironmentError(f"git {' '.join(args)} failed: {failure_text(result)}")
    return result.stdout


def failure_text(
    result: subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes] | None,
) -> str:
    if result is None:
        return "git timed out or could not run"
    stderr = (
        result.stderr.decode("utf-8", "replace") if isinstance(result.stderr, bytes) else result.stderr
    )
    return stderr.strip() or f"exit {result.returncode}"
