"""The task text at a slice's fork (slice 426, Task 14), on the fixture repositories."""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path

import pytest

from squadron.benchmark.slice_git import SliceHarnessError
from squadron.benchmark.slice_task import FILE_HEADING, TaskText, TaskTextRejection, task_text_at
from squadron.core.process_runner import ProcessResult, ProcessRunner, SubprocessRunner
from squadron.metrology.slice_case_models import SliceCandidateRejection
from tests.benchmark.slice_repos import (
    SLICE_NAME,
    SliceRepo,
    design_path,
    no_design_at_fork,
    no_slice_plan_at_fork,
    no_task_file_at_fork,
    split_task_files_at_fork,
    tasks_path,
    two_parent_landing,
)
from tests.conftest import run_test_git

TIMEOUT_S = 30.0


def _text_at(built: SliceRepo, runner: ProcessRunner | None = None) -> TaskText | TaskTextRejection:
    return task_text_at(
        built.landing.fork, built.index, built.repo, runner or SubprocessRunner(), TIMEOUT_S
    )


def _at_fork(built: SliceRepo, path: str) -> str:
    return run_test_git(built.repo, "show", f"{built.landing.fork}:{path}")


class _GitFailingOnPlanShow:
    """Real git, except ``git show`` of a slice plan fails."""

    def __init__(self) -> None:
        self._real = SubprocessRunner()

    def run(self, argv: Sequence[str], **kwargs: object) -> ProcessResult:
        if argv[1] == "show" and "-slices." in argv[2]:
            return ProcessResult(argv=tuple(argv), returncode=128, stdout="", stderr="fatal: boom")
        return self._real.run(argv, cwd=kwargs["cwd"], timeout=kwargs["timeout"])  # type: ignore[arg-type]


@pytest.fixture
def scratch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Where temporary directories are made, so a leftover one is visible."""
    directory = tmp_path / "scratch"
    directory.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(directory))
    return directory


def test_the_text_is_the_design_then_the_tasks_with_file_headings_and_verbatim_content(
    tmp_path: Path,
) -> None:
    built = two_parent_landing(tmp_path)
    design, tasks = design_path(built.index), tasks_path(built.index)

    result = _text_at(built)

    assert isinstance(result, TaskText)
    assert result.text == (
        f"{FILE_HEADING.format(path=design)}\n{_at_fork(built, design)}"
        f"{FILE_HEADING.format(path=tasks)}\n{_at_fork(built, tasks)}"
    )
    assert result.text.startswith(f"## File: {design}\n---\nslice: {SLICE_NAME}\n---\n")
    assert (result.slice_name, result.design_path, result.task_paths) == (
        SLICE_NAME,
        design,
        (tasks,),
    )


def test_split_task_files_are_ordered_2_before_10(tmp_path: Path) -> None:
    built = split_task_files_at_fork(tmp_path)

    result = _text_at(built)

    assert isinstance(result, TaskText)
    assert result.task_paths == tuple(tasks_path(built.index, suffix) for suffix in ("-1", "-2", "-10"))
    positions = [result.text.index(f"## File: {path}") for path in result.task_paths]
    assert positions == sorted(positions)


@pytest.mark.parametrize(
    ("build", "rejection"),
    [
        (no_design_at_fork, SliceCandidateRejection.NO_DESIGN_AT_FORK),
        (no_task_file_at_fork, SliceCandidateRejection.NO_TASKS_AT_FORK),
        (no_slice_plan_at_fork, SliceCandidateRejection.NO_SLICE_PLAN_AT_FORK),
    ],
)
def test_each_missing_piece_is_its_rejection(
    tmp_path: Path, build: object, rejection: SliceCandidateRejection, scratch: Path
) -> None:
    built = build(tmp_path)  # type: ignore[operator]

    result = _text_at(built)

    assert isinstance(result, TaskTextRejection)
    assert result.rejection is rejection
    assert str(built.index) in result.detail or "slice plan" in result.detail
    assert list(scratch.iterdir()) == []


def test_the_temporary_directory_is_gone_after_an_accepted_call(tmp_path: Path, scratch: Path) -> None:
    assert isinstance(_text_at(two_parent_landing(tmp_path)), TaskText)

    assert list(scratch.iterdir()) == []


def test_the_temporary_directory_is_gone_after_a_git_failure(tmp_path: Path, scratch: Path) -> None:
    built = two_parent_landing(tmp_path)

    with pytest.raises(SliceHarnessError, match="show"):
        _text_at(built, _GitFailingOnPlanShow())

    assert list(scratch.iterdir()) == []


def test_the_same_inputs_give_the_same_string(tmp_path: Path) -> None:
    built = two_parent_landing(tmp_path)

    first, second = _text_at(built), _text_at(built)

    assert isinstance(first, TaskText) and isinstance(second, TaskText)
    assert first.text == second.text
