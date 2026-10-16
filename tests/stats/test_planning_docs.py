"""Task-file reader against real task files (slice 176 D4).

The fixtures in ``fixtures/planning`` are verbatim copies of files in this repo, so a
parser that only works on a tidy layout fails here. Expected values were counted from
the files themselves (headings, ``Effort`` lines, commit subjects).
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import pytest

from squadron.integrations.context_forge import ARCHITECTURE_DIR
from squadron.review.persistence import SLICES_DIR, TASKS_DIR
from squadron.stats.planning_docs import (
    UnknownSliceError,
    planned_slice,
    read_slice_plans,
    read_task_file,
    read_task_files_for,
    slice_status,
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


_PLAN_FIXTURE = "140-slices.pipeline-foundation.md"


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """A project tree holding the real 140 slice plan."""
    architecture = tmp_path / ARCHITECTURE_DIR
    architecture.mkdir(parents=True)
    shutil.copy(FIXTURES / _PLAN_FIXTURE, architecture / _PLAN_FIXTURE)
    (tmp_path / TASKS_DIR).mkdir(parents=True)
    (tmp_path / SLICES_DIR).mkdir(parents=True)
    return tmp_path


def _write_design(root: Path, index: int, front: str) -> None:
    path = root / SLICES_DIR / f"{index}-slice.example.md"
    path.write_text(f"---\n{front}\n---\n\nBody\n", encoding="utf-8")


def test_every_entry_in_the_140_plan_is_read(project_root: Path) -> None:
    plans = read_slice_plans(project_root)

    assert len(plans) == 35
    assert plans[140].title == "Command Surface Parity"
    assert plans[168].title == "`sq review code` — Slice Implementation Review"


def test_checked_and_unchecked_entries_are_both_read(project_root: Path) -> None:
    plans = read_slice_plans(project_root)

    assert plans[175].title == "Usage and Cost Tracking"  # [x] in the plan
    assert plans[176].title.startswith("Effort Calibration")  # [ ] in the plan


def test_effort_n_of_5_is_read_wherever_it_sits_in_the_entry(project_root: Path) -> None:
    plans = read_slice_plans(project_root)

    assert plans[140].effort == 1
    assert plans[141].effort == 2
    # 172's entry has plain numbered lines inside it; its Effort is further down.
    assert plans[172].effort == 1
    assert plans[168].effort is None  # this entry has no Effort figure


def test_plan_entries_pick_up_their_task_files(project_root: Path) -> None:
    shutil.copy(FIXTURES / "175-tasks.usage-and-cost-tracking.md", project_root / TASKS_DIR)

    plans = read_slice_plans(project_root)

    tasks = plans[175].tasks
    assert tasks is not None and len(tasks) == 34
    assert plans[140].tasks is None


def test_slice_status_complete_other_and_missing(project_root: Path) -> None:
    _write_design(project_root, 175, "status: complete\ndateCreated: 20261014")
    _write_design(project_root, 176, "status: in_progress\ndateCreated: 20261015")

    assert slice_status(175, project_root) == (True, "20261014")
    assert slice_status(176, project_root) == (False, "20261015")
    assert slice_status(999, project_root) == (False, None)


def test_slice_status_accepts_the_completed_alias(project_root: Path) -> None:
    _write_design(project_root, 175, "status: completed\ndateCreated: 20261014")

    assert slice_status(175, project_root)[0] is True


def test_completion_comes_from_the_design_not_the_plan_checkbox(project_root: Path) -> None:
    _write_design(project_root, 176, "status: complete")  # plan entry 176 is unchecked

    assert planned_slice(176, project_root).complete is True
    assert planned_slice(175, project_root).complete is False  # [x] in the plan, no design


def test_unknown_index_lists_the_plan_files_searched(project_root: Path) -> None:
    with pytest.raises(UnknownSliceError) as raised:
        planned_slice(99999, project_root)

    assert raised.value.index == 99999
    assert [path.name for path in raised.value.searched] == [_PLAN_FIXTURE]
    assert _PLAN_FIXTURE in str(raised.value)
