"""Task-file reader against real task files (slice 176 D4).

The fixtures in ``fixtures/planning`` are verbatim copies of files in this repo, so a
parser that only works on a tidy layout fails here. Expected values were counted from
the files themselves (headings, ``Effort`` lines, commit subjects).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.review.persistence import TASKS_DIR
from squadron.stats.planning_docs import (
    read_task_file,
    read_task_files_for,
    task_file_paths,
)

FIXTURES = Path(__file__).parent / "fixtures" / "planning"

_REAL_TASK_FILES = {
    "100-tasks.foundation.md": 19,
    "170-tasks.profile-aware-dispatch-model-routing.md": 15,
    "175-tasks.usage-and-cost-tracking.md": 34,
    "173-tasks.user-definable-actions-on-supported-events.md": 24,
}


@pytest.mark.parametrize(("name", "count"), _REAL_TASK_FILES.items())
def test_real_task_files_yield_every_task(name: str, count: int) -> None:
    tasks = read_task_file([FIXTURES / name])

    assert len(tasks) == count  # a parser that finds none fails here (D4)
    assert [task.number for task in tasks] == list(range(1, count + 1))


def test_100_efforts_use_the_slash_five_form() -> None:
    tasks = read_task_file([FIXTURES / "100-tasks.foundation.md"])

    assert {task.number for task in tasks if task.effort == 2} == {9, 16}
    assert {task.effort for task in tasks if task.number not in (9, 16)} == {1}
    assert tasks[0].title == "Initialize Python Project with uv"


def test_170_reads_git_commit_subjects_after_other_text() -> None:
    tasks = read_task_file([FIXTURES / "170-tasks.profile-aware-dispatch-model-routing.md"])

    subjects = [subject for task in tasks for subject in task.commit_subjects]
    assert subjects == [
        "refactor: extract _one_shot_dispatch helper from _dispatch_via_agent",
        "feat: branch _render_dispatch on resolved profile for non-SDK models",
        "feat: add hidden sq _dispatch-run subcommand for non-SDK pipeline dispatch",
        "feat: branch sq:run dispatch handler on command field for non-SDK models",
        "fix: raise ProviderAPIError when SDK ResultMessage.is_error is True",
        "docs: mark slice 170 complete",
    ]
    by_number = {task.number: task for task in tasks}
    assert by_number[3].commit_subjects == (subjects[0],)
    assert by_number[4].commit_subjects == ()
    assert tasks[0].effort is None


def test_175_reads_prescribed_commit_subjects() -> None:
    tasks = read_task_file([FIXTURES / "175-tasks.usage-and-cost-tracking.md"])

    assert sum(len(task.commit_subjects) for task in tasks) == 16
    task_3 = next(task for task in tasks if task.number == 3)
    assert task_3.commit_subjects == (
        "feat: add UsageRecord, cache_write, and usage metadata constants",
    )
    assert all(task.effort is None for task in tasks)  # its "Effort: 4/5" is slice-level


def test_173_has_no_commit_subjects_and_ignores_the_trailing_slice_effort() -> None:
    tasks = read_task_file([FIXTURES / "173-tasks.user-definable-actions-on-supported-events.md"])

    assert all(task.commit_subjects == () for task in tasks)
    # The file ends with a flush "Effort: 3/5 overall." paragraph; it is not task 24's.
    assert tasks[-1].effort is None
    assert (tasks[0].checked, tasks[0].total) == (5, 5)


def test_split_parts_read_as_one_ordered_list() -> None:
    parts = [FIXTURES / "900-tasks.split-example-1.md", FIXTURES / "900-tasks.split-example-2.md"]

    tasks = read_task_file(parts)

    assert [task.number for task in tasks] == [1, 2, 3]
    assert [task.effort for task in tasks] == [2, None, 3]
    assert tasks[2].commit_subjects == ("docs: third synthetic subject",)


def test_checked_and_total_for_full_and_partial_tasks() -> None:
    tasks = read_task_file([FIXTURES / "900-tasks.split-example-1.md"])

    assert (tasks[0].checked, tasks[0].total) == (3, 3)
    assert (tasks[1].checked, tasks[1].total) == (1, 3)


def test_non_numeric_effort_is_none_with_warning_naming_file_and_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    path = FIXTURES / "901-tasks.relative-effort.md"

    with caplog.at_level(logging.WARNING, logger="squadron.stats.planning_docs"):
        tasks = read_task_file([path])

    assert tasks[0].effort is None
    message = next(r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)
    assert f"{path}:10" in message


def test_task_file_paths_orders_split_parts_by_number(tmp_path: Path) -> None:
    tasks_dir = tmp_path / TASKS_DIR
    tasks_dir.mkdir(parents=True)
    for suffix in ("-10", "-2", "-1"):
        (tasks_dir / f"902-tasks.parts{suffix}.md").write_text("## Tasks\n", encoding="utf-8")

    paths = task_file_paths(902, tmp_path)

    assert [path.name for path in paths] == [
        "902-tasks.parts-1.md",
        "902-tasks.parts-2.md",
        "902-tasks.parts-10.md",
    ]


def test_read_task_files_for_returns_none_without_a_task_file(tmp_path: Path) -> None:
    (tmp_path / TASKS_DIR).mkdir(parents=True)

    assert read_task_files_for(903, tmp_path) is None


def test_multiple_task_file_names_log_a_warning_and_first_wins(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    tasks_dir = tmp_path / TASKS_DIR
    tasks_dir.mkdir(parents=True)
    for name in ("904-tasks.beta.md", "904-tasks.alpha.md"):
        (tasks_dir / name).write_text("## Tasks\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="squadron.stats.planning_docs"):
        paths = task_file_paths(904, tmp_path)

    assert [path.name for path in paths] == ["904-tasks.alpha.md"]
    assert any("904" in r.getMessage() for r in caplog.records)
