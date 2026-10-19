"""``slice_task_paths``: the slice's task files as paths (merge guard, BLOCKED check)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry
from squadron.pipeline.branch_ops import slice_task_paths
from squadron.review.persistence import TASKS_DIR

SLICE = 105


def _cf(task_files: list[str]) -> MagicMock:
    client = MagicMock()
    client.list_slices.return_value = [
        SliceEntry(
            index=SLICE,
            name="Batch Foo",
            design_file="project-documents/user/slices/105-slice.batch-foo.md",
            status="in_progress",
        )
    ]
    client.list_tasks.return_value = [TaskEntry(index=SLICE, files=task_files)]
    client.get_project.return_value = ProjectInfo(
        arch_file="a.md", slice_plan="p", phase="Phase 6", slice=str(SLICE), name="squadron"
    )
    return client


def test_returns_the_listed_files_as_paths_under_cwd(tmp_path: Path) -> None:
    paths = slice_task_paths(_cf(["105-tasks.a.md", "105-tasks.b.md"]), SLICE, str(tmp_path))

    assert paths == [
        tmp_path / TASKS_DIR / "105-tasks.a.md",
        tmp_path / TASKS_DIR / "105-tasks.b.md",
    ]


def test_a_slice_with_no_task_files_gives_an_empty_list(tmp_path: Path) -> None:
    assert slice_task_paths(_cf([]), SLICE, str(tmp_path)) == []


def test_a_cf_error_propagates(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No slice with index 999"):
        slice_task_paths(_cf(["105-tasks.a.md"]), 999, str(tmp_path))
