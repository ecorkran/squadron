"""Tests for input gathering (D7): commits and slice artifacts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.integrations.context_forge import ContextForgeNotAvailable, SliceEntry, TaskEntry
from squadron.pr.inputs import gather_commits_and_slice
from squadron.review.git_utils import CommitRecord

SLICE_BRANCH = "385-slice.create-a-pr-with-a-good-message"
NON_SLICE_BRANCH = "scratch-branch"


def _cf_client(*, slices: list[SliceEntry], tasks: list[TaskEntry]) -> MagicMock:
    client = MagicMock()
    client.list_slices.return_value = slices
    client.list_tasks.return_value = tasks
    return client


def _fake_commits_in_range(base: str, head: str, *, cwd: str) -> list[CommitRecord]:
    return [CommitRecord(sha="abc123", subject="feat: do the thing")]


@pytest.fixture(autouse=True)
def _fake_commits(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setattr("squadron.pr.inputs.commits_in_range", _fake_commits_in_range)


def test_slice_branch_with_design_and_tasks(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "project-documents" / "user" / "tasks"
    tasks_dir.mkdir(parents=True)
    task_file = tasks_dir / "385-tasks.create-a-pr-with-a-good-message.md"
    task_file.write_text("- [x] done\n- [ ] not done\n")

    cf_client = _cf_client(
        slices=[
            SliceEntry(
                index=385,
                name="Create a PR with a Good Message",
                design_file="project-documents/user/slices/385-slice.create-a-pr-with-a-good-message.md",
                status="not_started",
            )
        ],
        tasks=[TaskEntry(index=385, files=["385-tasks.create-a-pr-with-a-good-message.md"])],
    )

    result = gather_commits_and_slice(cf_client, base="main", head=SLICE_BRANCH, cwd=str(tmp_path))

    assert result.slice.index == 385
    assert result.slice.design_file is not None
    assert result.slice.task_items is not None
    assert result.slice.task_items.checked == ("done",)
    assert result.slice.task_items.unchecked == ("not done",)
    assert len(result.commits) == 1


def test_slice_branch_cf_does_not_know_degrades_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cf_client = _cf_client(slices=[], tasks=[])

    with caplog.at_level("WARNING"):
        result = gather_commits_and_slice(cf_client, base="main", head=SLICE_BRANCH, cwd=str(tmp_path))

    assert result.slice.index == 385
    assert result.slice.design_file is None
    assert result.slice.task_items is None
    assert any("385" in record.message for record in caplog.records)


def test_non_slice_branch_makes_no_cf_call(tmp_path: Path) -> None:
    cf_client = _cf_client(slices=[], tasks=[])

    result = gather_commits_and_slice(cf_client, base="main", head=NON_SLICE_BRANCH, cwd=str(tmp_path))

    assert result.slice.index is None
    assert result.slice.design_file is None
    assert result.slice.task_items is None
    cf_client.list_slices.assert_not_called()


def test_task_file_absent_leaves_design_present_and_items_empty(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cf_client = _cf_client(
        slices=[
            SliceEntry(
                index=385,
                name="Create a PR with a Good Message",
                design_file="project-documents/user/slices/385-slice.create-a-pr-with-a-good-message.md",
                status="not_started",
            )
        ],
        tasks=[TaskEntry(index=385, files=["385-tasks.create-a-pr-with-a-good-message.md"])],
    )

    with caplog.at_level("WARNING"):
        result = gather_commits_and_slice(cf_client, base="main", head=SLICE_BRANCH, cwd=str(tmp_path))

    assert result.slice.design_file is not None
    assert result.slice.task_items is None
    assert any("task file" in record.message for record in caplog.records)


def test_cf_unavailable_entirely_degrades_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cf_client = MagicMock()
    cf_client.list_slices.side_effect = ContextForgeNotAvailable("cf not on PATH")

    with caplog.at_level("WARNING"):
        result = gather_commits_and_slice(cf_client, base="main", head=SLICE_BRANCH, cwd=str(tmp_path))

    assert result.slice.index == 385
    assert result.slice.design_file is None
    assert result.slice.task_items is None
    assert any("385" in record.message for record in caplog.records)
