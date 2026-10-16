"""Where a replay starts: the commit before an artifact first existed (slice 177 D2).

The start point is the first parent of the commit that first added the original
artifact. The artifact's content at the adding commit is the original producer's
first draft, which later becomes the ``original`` pairwise contestant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from squadron.integrations.context_forge import DOCS_ROOT
from squadron.metrology.replay_models import ReplayPhase
from squadron.stats.git_history import STATUS_ADDED, Commit, GitHistory, path_matches

#: A split task file is ``{name}-1.md``, ``{name}-2.md``, ...; the suffix is not part of the name.
_SPLIT_SUFFIX = re.compile(r"-(\d+)$")


@dataclass(frozen=True)
class _ArtifactKind:
    directory: str
    stem: str  # the file-name segment after the index: ``{index}-{stem}.{name}.md``


_KINDS: dict[ReplayPhase, _ArtifactKind] = {
    ReplayPhase.DESIGN: _ArtifactKind(f"{DOCS_ROOT}/user/slices", "slice"),
    ReplayPhase.TASKS: _ArtifactKind(f"{DOCS_ROOT}/user/tasks", "tasks"),
}


class StartPointError(Exception):
    """The original artifact's history cannot give a start point; nothing is run."""


class ArtifactNotFoundError(StartPointError):
    """No commit added a file matching the artifact pattern."""

    def __init__(self, pattern: str) -> None:
        super().__init__(f"no commit added a file matching {pattern}")
        self.pattern = pattern


class RootCommitError(StartPointError):
    """The adding commit has no parent, so there is no earlier state to start from."""

    def __init__(self, sha: str) -> None:
        super().__init__(f"commit {sha} added the artifact and has no parent")
        self.sha = sha


class ArtifactUnreadableError(StartPointError):
    """git could not show the artifact at its adding commit."""

    def __init__(self, path: str, sha: str) -> None:
        super().__init__(f"cannot read {path} at commit {sha}")
        self.path = path
        self.sha = sha


@dataclass(frozen=True)
class StartPoint:
    phase: ReplayPhase
    slice_index: int
    slice_name: str
    artifact_path: str  # the first file, for a split task breakdown
    original_sha: str  # the commit that first added the artifact
    start_sha: str  # its first parent
    original_first_draft: str


def resolve_start_point(phase: ReplayPhase, index: int, history: GitHistory) -> StartPoint:
    """The start point for replaying ``phase`` of slice ``index``; ``history`` must be loaded."""
    kind = _KINDS[phase]
    pattern = f"{kind.directory}/{index}-{kind.stem}.*.md"
    adding = _adding_commit(history, pattern, kind.directory)
    if not adding.parents:
        raise RootCommitError(adding.sha)
    paths = _added_paths(adding, pattern, kind.directory)
    text = "\n".join(_show(history, adding.sha, path) for path in paths)
    return StartPoint(
        phase=phase,
        slice_index=index,
        slice_name=_slice_name(paths, index, kind.stem),
        artifact_path=paths[0],
        original_sha=adding.sha,
        start_sha=adding.parents[0],
        original_first_draft=text,
    )


def artifact_files(phase: ReplayPhase, index: int, root: Path) -> list[Path]:
    """The artifact's files in the working tree under ``root``, split files in suffix order."""
    kind = _KINDS[phase]
    found = (root / kind.directory).glob(f"{index}-{kind.stem}.*.md")
    return sorted(found, key=lambda path: _suffix_order(path.as_posix()))


def _adding_commit(history: GitHistory, pattern: str, directory: str) -> Commit:
    """The earliest commit adding a matching file directly in ``directory``.

    Matching is by exact directory, so a copy under ``archive/`` never counts.
    """
    for commit in reversed(history.commits_touching(pattern)):
        if _added_paths(commit, pattern, directory):
            return commit
    raise ArtifactNotFoundError(pattern)


def _added_paths(commit: Commit, pattern: str, directory: str) -> list[str]:
    """Files the commit added that match ``pattern`` directly in ``directory``, in suffix order."""
    paths = [
        change.path
        for change in commit.changes
        if change.status == STATUS_ADDED
        and PurePosixPath(change.path).parent.as_posix() == directory
        and path_matches(change.path, pattern)
    ]
    return sorted(paths, key=_suffix_order)


def _suffix_order(path: str) -> tuple[str, int]:
    """Sort split files numerically (``-2`` before ``-10``), not lexically."""
    stem = PurePosixPath(path).stem
    match = _SPLIT_SUFFIX.search(stem)
    if match is None:
        return stem, 0
    return stem[: match.start()], int(match.group(1))


def _show(history: GitHistory, sha: str, path: str) -> str:
    text = history.show(sha, path)
    if text is None:
        raise ArtifactUnreadableError(path, sha)
    return text


def _slice_name(paths: list[str], index: int, stem: str) -> str:
    """The slice name from the file name; a split artifact drops its ``-N`` suffix."""
    name = PurePosixPath(paths[0]).stem.removeprefix(f"{index}-{stem}.")
    if len(paths) > 1:
        name = _SPLIT_SUFFIX.sub("", name)
    return name
