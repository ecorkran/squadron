"""Shared planning-file paths and cf mock for commit-plan and squash tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry

SLICE = 105
DESIGN_FILE = "project-documents/user/slices/105-slice.batch-foo.md"
TASKS_FILE = "project-documents/user/tasks/105-tasks.batch-foo.md"
PLAN_FILE = "project-documents/user/architecture/100-slices.plan-name.md"
ARCH_FILE = "project-documents/user/architecture/100-arch.plan-name.md"
DESIGN_REVIEW = "project-documents/user/reviews/105-review.slice.batch-foo.md"
TASKS_REVIEW = "project-documents/user/reviews/105-review.tasks.batch-foo.md"
CODE_REVIEW = "project-documents/user/reviews/105-review.code.batch-foo.md"
ARCH_REVIEW = "project-documents/user/reviews/100-review.arch.plan-name.md"


def write_file(repo: Path, relative: str, text: str = "content\n") -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def cf_client() -> MagicMock:
    """A cf client shaped like the real one: the slice plan arrives as a bare stem."""
    client = MagicMock()
    client.list_slices.return_value = [
        SliceEntry(index=SLICE, name="Batch Foo", design_file=DESIGN_FILE, status="in_progress")
    ]
    client.list_tasks.return_value = [TaskEntry(index=SLICE, files=["105-tasks.batch-foo.md"])]
    client.get_config.return_value = ""  # git.integration_branch unset: the target is main
    client.get_project.return_value = ProjectInfo(
        arch_file=ARCH_FILE,
        slice_plan="100-slices.plan-name",
        phase="Phase 4",
        slice=str(SLICE),
        name="squadron",
    )
    return client
