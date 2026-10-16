"""Whole-history git reads for the effort reports (slice 176 D5, D6).

The only ``stats/`` module that runs git. ``GitHistory.load()`` makes exactly two calls
(branch tips, then one history pass) and builds an in-memory commit graph; every query
below reads that graph. The one other call a report makes is ``show``, once per review
artifact version. All calls go through the injected runner, so each has ``run_git``'s
timeout and WARNING.
"""

from __future__ import annotations

import fnmatch
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from subprocess import CompletedProcess
from typing import NamedTuple

from squadron.review.git_utils import run_git

_logger = logging.getLogger(__name__)

GitRunner = Callable[..., "CompletedProcess[str] | None"]

BRANCH_REF_PREFIX = "refs/heads/"
#: `git add` status letter for a path first appearing in a commit.
STATUS_ADDED = "A"
STATUS_DELETED = "D"

# The history pass: a header line per commit, then its `--raw` change lines. \x01 starts
# a header and \x1f separates its fields, so no subject text can be mistaken for either.
_HEADER_START = "\x01"
_FIELD_SEP = "\x1f"
_LOG_ARGS = [
    "-c",
    "core.quotepath=off",
    "log",
    "--all",
    "--raw",
    "--no-abbrev",
    "--no-renames",
    f"--format={_HEADER_START}%H{_FIELD_SEP}%P{_FIELD_SEP}%aI{_FIELD_SEP}%s",
]
_REFS_ARGS = ["for-each-ref", "--format=%(refname) %(objectname)", "refs/heads"]


class WindowSource(StrEnum):
    """Where a slice's commit window came from (D5)."""

    BRANCH = "branch"
    NONE = "none"


@dataclass(frozen=True)
class ReviewRound:
    review_type: str
    sha: str
    authored_at: datetime
    verdict: str | None
    model: str | None
    run_id: str | None


class FileChange(NamedTuple):
    status: str  # first letter of git's status: A, M, D, T
    path: str
    blob_id: str  # the file's blob after the commit (all zeros for a delete)


@dataclass(frozen=True)
class Commit:
    sha: str
    parents: tuple[str, ...]
    authored_at: datetime
    subject: str
    changes: tuple[FileChange, ...]


class GitHistoryError(Exception):
    """git could not answer a whole-history call; no partial graph is ever returned."""

    def __init__(self, message: str, *, command: str, cwd: Path) -> None:
        super().__init__(message)
        self.command = command
        self.cwd = cwd


class GitHistory:
    """The repo's commit graph and branch tips, loaded once per report."""

    def __init__(self, project_root: Path, run: GitRunner = run_git) -> None:
        self._root = project_root
        self._run = run
        self._commits: dict[str, Commit] | None = None
        self._ordered: list[Commit] = []  # newest first, as `git log` prints
        self._branches: dict[str, str] = {}

    def load(self) -> None:
        """Run the two whole-history git calls and build the graph."""
        self._branches = _parse_refs(self._git(_REFS_ARGS))
        self._ordered = _parse_log(self._git(_LOG_ARGS), self._root)
        self._commits = {commit.sha: commit for commit in self._ordered}

    def show(self, sha: str, path: str) -> str | None:
        """``git show <sha>:<path>``; ``None`` when git cannot produce it (WARNING logged)."""
        args = ["show", f"{sha}:{path}"]
        result = self._run(args, cwd=str(self._root))
        if result is None or result.returncode != 0:
            detail = "git could not run" if result is None else result.stderr.strip()
            _logger.warning("git %s failed in %s: %s", " ".join(args), self._root, detail)
            return None
        return result.stdout

    def commit(self, sha: str) -> Commit:
        """The loaded commit ``sha``; ``KeyError`` when the history has no such commit."""
        return self._graph()[sha]

    def branch_tip(self, index: int) -> Commit | None:
        """The tip of the local branch ``{index}-slice.*``; the first by name when several."""
        prefix = f"{BRANCH_REF_PREFIX}{index}-slice."
        names = sorted(name for name in self._branches if name.startswith(prefix))
        if not names:
            return None
        if len(names) > 1:
            _logger.warning("Multiple branches for slice %d, using %s", index, names[0])
        return self._graph()[self._branches[names[0]]]

    def first_parent_chain(self, tip: Commit) -> list[Commit]:
        """``tip`` and its first-parent ancestors, newest first."""
        graph = self._graph()
        chain: list[Commit] = []
        current: Commit | None = tip
        while current is not None:
            chain.append(current)
            current = graph.get(current.parents[0]) if current.parents else None
        return chain

    def commits_touching(self, pattern: str) -> list[Commit]:
        """Commits changing any path matching the glob ``pattern``, newest first."""
        self._graph()
        return [c for c in self._ordered if any(path_matches(ch.path, pattern) for ch in c.changes)]

    def first_added(self, pattern: str) -> Commit | None:
        """The earliest commit that added a path matching ``pattern``."""
        self._graph()
        for commit in reversed(self._ordered):
            if any(
                ch.status == STATUS_ADDED and path_matches(ch.path, pattern) for ch in commit.changes
            ):
                return commit
        return None

    def _graph(self) -> dict[str, Commit]:
        if self._commits is None:
            raise RuntimeError("GitHistory.load() must run before any query")
        return self._commits

    def _git(self, args: list[str]) -> str:
        command = "git " + " ".join(args)
        result = self._run(args, cwd=str(self._root))
        if result is None:
            raise GitHistoryError(
                f"{command} could not run in {self._root}; see the preceding warning",
                command=command,
                cwd=self._root,
            )
        if result.returncode != 0:
            raise GitHistoryError(
                f"{command} failed in {self._root}: {result.stderr.strip()}",
                command=command,
                cwd=self._root,
            )
        return result.stdout


def path_matches(path: str, pattern: str) -> bool:
    """Whether ``path`` matches the glob ``pattern`` (``*`` also crosses ``/``)."""
    return fnmatch.fnmatchcase(path, pattern)


def _parse_refs(text: str) -> dict[str, str]:
    branches: dict[str, str] = {}
    for line in text.splitlines():
        name, _, sha = line.rpartition(" ")
        branches[name] = sha
    return branches


def _parse_log(text: str, cwd: Path) -> list[Commit]:
    commits: list[Commit] = []
    header: list[str] | None = None
    changes: list[FileChange] = []

    def close() -> None:
        if header is not None:
            commits.append(_commit(header, changes, cwd))

    for line in text.splitlines():
        if line.startswith(_HEADER_START):
            close()
            header, changes = line[len(_HEADER_START) :].split(_FIELD_SEP, 3), []
        elif line.startswith(":") and header is not None:
            changes.append(_change(line, cwd))
    close()
    return commits


def _commit(header: list[str], changes: list[FileChange], cwd: Path) -> Commit:
    if len(header) != 4:
        raise GitHistoryError(f"unreadable git log header {header!r}", command="git log", cwd=cwd)
    sha, parents, authored_at, subject = header
    return Commit(
        sha=sha,
        parents=tuple(parents.split()),
        authored_at=datetime.fromisoformat(authored_at),
        subject=subject,
        changes=tuple(changes),
    )


def _change(line: str, cwd: Path) -> FileChange:
    meta, tab, path = line.partition("\t")
    fields = meta.split()
    if not tab or len(fields) < 5:
        raise GitHistoryError(f"unreadable git log change line {line!r}", command="git log", cwd=cwd)
    return FileChange(status=fields[-1][0], path=path, blob_id=fields[-2])
