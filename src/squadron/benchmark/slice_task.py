"""The task text of a slice case: its design and task files as they stood at the fork
(slice 426 D3).

The files are found with ``git ls-tree`` at the fork commit and read with ``git show``;
nothing is read from the working tree. The fork's slice plans are written to a temporary
directory so ``plan_file_for`` can check that a plan lists the slice, as cf registration
will need (D9).
"""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from squadron.benchmark.slice_git import run_git
from squadron.core.process_runner import ProcessRunner
from squadron.integrations.context_forge import ARCHITECTURE_DIR
from squadron.metrology.replay_models import ReplayPhase
from squadron.metrology.slice_case_models import SliceCandidateRejection
from squadron.replay.start_point import ARTIFACT_KINDS, artifact_pattern, suffix_order
from squadron.stats.git_history import path_matches
from squadron.stats.planning_docs import SLICE_PLAN_GLOB, UnknownSliceError, plan_file_for

FILE_HEADING = "## File: {path}"


@dataclass(frozen=True)
class TaskText:
    """The case's ``task_text`` and where it came from."""

    text: str
    slice_name: str
    design_path: str
    task_paths: tuple[str, ...]


@dataclass(frozen=True)
class TaskTextRejection:
    """A slice whose fork lacks something P6 needs."""

    rejection: SliceCandidateRejection
    detail: str


def task_text_at(
    fork_sha: str, index: int, repo: Path, runner: ProcessRunner, timeout_s: float
) -> TaskText | TaskTextRejection:
    """The design then the task files at ``fork_sha``, or why the slice cannot be a case.

    The runner reads text with universal newlines, so line endings are as it returns them;
    the same fork always gives the same string. A failed ``git`` call raises
    ``SliceHarnessError``.
    """
    designs = _files_at(fork_sha, ReplayPhase.DESIGN, index, repo, runner, timeout_s)
    if not designs:
        return TaskTextRejection(
            SliceCandidateRejection.NO_DESIGN_AT_FORK,
            f"no {artifact_pattern(ReplayPhase.DESIGN, index)} at {fork_sha[:12]}",
        )
    tasks = _files_at(fork_sha, ReplayPhase.TASKS, index, repo, runner, timeout_s)
    if not tasks:
        return TaskTextRejection(
            SliceCandidateRejection.NO_TASKS_AT_FORK,
            f"no {artifact_pattern(ReplayPhase.TASKS, index)} at {fork_sha[:12]}",
        )
    if not _plan_lists(fork_sha, index, repo, runner, timeout_s):
        return TaskTextRejection(
            SliceCandidateRejection.NO_SLICE_PLAN_AT_FORK,
            f"no slice plan at {fork_sha[:12]} lists slice {index}",
        )
    files = [*designs, *tasks]
    sections = [_section(fork_sha, path, repo, runner, timeout_s) for path in files]
    return TaskText(
        text="".join(sections),
        slice_name=_slice_name(designs[0], index),
        design_path=designs[0],
        task_paths=tuple(tasks),
    )


def _files_at(
    fork_sha: str,
    phase: ReplayPhase,
    index: int,
    repo: Path,
    runner: ProcessRunner,
    timeout_s: float,
) -> list[str]:
    """The artifact's files directly in its directory at ``fork_sha``, in suffix order."""
    directory = ARTIFACT_KINDS[phase].directory
    pattern = artifact_pattern(phase, index)
    listing = _ls_tree(fork_sha, directory, repo, runner, timeout_s)
    return sorted((path for path in listing if path_matches(path, pattern)), key=suffix_order)


def _ls_tree(
    fork_sha: str, directory: str, repo: Path, runner: ProcessRunner, timeout_s: float
) -> list[str]:
    """The paths directly inside ``directory`` at ``fork_sha`` (an archive subdirectory is not
    listed as a file); empty when the directory does not exist there."""
    out = run_git(runner, repo, ("ls-tree", "-z", "--name-only", fork_sha, f"{directory}/"), timeout_s)
    return [path for path in out.split("\0") if path]


def _section(fork_sha: str, path: str, repo: Path, runner: ProcessRunner, timeout_s: float) -> str:
    """``## File: <path>`` and the file's content verbatim, ending in a newline."""
    content = run_git(runner, repo, ("show", f"{fork_sha}:{path}"), timeout_s)
    separator = "" if content.endswith("\n") else "\n"
    return f"{FILE_HEADING.format(path=path)}\n{content}{separator}"


def _plan_lists(fork_sha: str, index: int, repo: Path, runner: ProcessRunner, timeout_s: float) -> bool:
    """Whether a slice plan at ``fork_sha`` lists ``index``, checked by ``plan_file_for`` on a
    temporary copy of the fork's plans (removed afterwards, also on error)."""
    plans = [
        path
        for path in _ls_tree(fork_sha, ARCHITECTURE_DIR, repo, runner, timeout_s)
        if path_matches(PurePosixPath(path).name, SLICE_PLAN_GLOB)
    ]
    with tempfile.TemporaryDirectory(prefix="slice-plans-") as scratch:
        root = Path(scratch)
        _write_plans(fork_sha, plans, root, repo, runner, timeout_s)
        try:
            plan_file_for(index, root)
        except UnknownSliceError:
            return False
    return True


def _write_plans(
    fork_sha: str,
    plans: Sequence[str],
    root: Path,
    repo: Path,
    runner: ProcessRunner,
    timeout_s: float,
) -> None:
    for path in plans:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(run_git(runner, repo, ("show", f"{fork_sha}:{path}"), timeout_s))


def _slice_name(design_path: str, index: int) -> str:
    """The name in ``{index}-slice.{name}.md``."""
    stem = ARTIFACT_KINDS[ReplayPhase.DESIGN].stem
    return PurePosixPath(design_path).stem.removeprefix(f"{index}-{stem}.")
