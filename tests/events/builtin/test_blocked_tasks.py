"""squadron.blocked-tasks: an implement dispatch that left BLOCKED markers pauses the run."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from squadron.events import EventType
from squadron.events.builtin.blocked_tasks import BlockedTasksAction
from squadron.events.contexts import PostActionContext
from squadron.integrations.context_forge import ContextForgeError
from squadron.pipeline.actions.dispatch import SKIPPED_KEY
from squadron.pipeline.models import ActionResult

_MODULE = "squadron.events.builtin.blocked_tasks"
_REAL_BLOCKED_LINE = "> BLOCKED: no judge-template review artifact ... PM asked"


@pytest.fixture(autouse=True)
def implement_dispatch_left_no_blocked_markers() -> None:
    """Override the suite-wide stub: these tests exercise the real reading path."""


def _context(
    *,
    step_type: str = "implement",
    action_type: str = "dispatch",
    outputs: dict[str, object] | None = None,
    success: bool = True,
    slice_param: object = "107",
    cwd: str = ".",
) -> PostActionContext:
    params: dict[str, object] = {} if slice_param is None else {"slice": slice_param}
    return PostActionContext(
        event=EventType.POST_ACTION,
        cwd=cwd,
        params=params,
        action_type=action_type,
        result=ActionResult(
            success=success, action_type=action_type, outputs=outputs if outputs is not None else {}
        ),
        run_id="run-42",
        run_started_at=None,
        run_state_error=None,
        step_name="implement-1",
        step_type=step_type,
        expected_artifact_kind=None,
        iteration=0,
        cf_client=MagicMock(),
    )


def _task_file(tmp_path: Path, text: str) -> list[Path]:
    path = tmp_path / "107-tasks.batch.md"
    path.write_text(text)
    return [path]


@pytest.mark.parametrize(
    "ctx",
    [
        _context(step_type="design"),
        _context(action_type="review"),
        _context(success=False),
        _context(slice_param=None),
        _context(outputs={SKIPPED_KEY: True}),
    ],
    ids=["not-implement", "not-dispatch", "failed", "no-slice", "skipped"],
)
async def test_guard_conditions_that_do_not_apply_pass_without_reading_task_files(
    ctx: PostActionContext,
) -> None:
    with patch(f"{_MODULE}.slice_task_paths") as paths:
        result = await BlockedTasksAction().execute(ctx)

    assert result.success
    paths.assert_not_called()


async def test_markers_pause_the_run_with_the_blocker_text_and_resume_command(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    files = _task_file(tmp_path, f"- [ ] 7.2 Capture\n  {_REAL_BLOCKED_LINE}\n- [ ] 8.1 Next\n")

    with (
        patch(f"{_MODULE}.slice_task_paths", return_value=files),
        caplog.at_level(logging.WARNING, logger=_MODULE),
    ):
        result = await BlockedTasksAction().execute(_context())

    assert not result.success
    assert result.awaits_human
    assert result.error == (
        "1 blocked task(s) need the Project Manager: no judge-template review artifact ... "
        "PM asked. Resolve them, remove the BLOCKED lines, then resume: sq run --resume run-42"
    )
    assert any(r.levelno == logging.WARNING for r in caplog.records)


async def test_markers_are_gathered_across_task_files_and_capped_in_the_message(
    tmp_path: Path,
) -> None:
    first = tmp_path / "a.md"
    second = tmp_path / "b.md"
    first.write_text("BLOCKED: one\nBLOCKED: two\n")
    second.write_text("BLOCKED: three\nBLOCKED: four\n")

    with patch(f"{_MODULE}.slice_task_paths", return_value=[first, second]):
        result = await BlockedTasksAction().execute(_context())

    assert result.error is not None
    assert result.error.startswith("4 blocked task(s) need the Project Manager: one; two; three.")
    assert "four" not in result.error


async def test_no_markers_passes(tmp_path: Path) -> None:
    files = _task_file(tmp_path, "- [x] done\n- [ ] 2. Something blocked by the build\n")

    with patch(f"{_MODULE}.slice_task_paths", return_value=files):
        result = await BlockedTasksAction().execute(_context())

    assert result.success
    assert not result.awaits_human


async def test_unreadable_task_file_fails_naming_the_path_without_pausing(tmp_path: Path) -> None:
    missing = tmp_path / "107-tasks.gone.md"

    with patch(f"{_MODULE}.slice_task_paths", return_value=[missing]):
        result = await BlockedTasksAction().execute(_context())

    assert not result.success
    assert not result.awaits_human
    assert result.error is not None
    assert str(missing) in result.error


async def test_cf_error_fails_with_the_cf_text_without_pausing() -> None:
    with patch(f"{_MODULE}.slice_task_paths", side_effect=ContextForgeError("cf exploded")):
        result = await BlockedTasksAction().execute(_context())

    assert not result.success
    assert not result.awaits_human
    assert result.error is not None
    assert "cf exploded" in result.error


async def test_non_numeric_slice_param_fails_rather_than_passes() -> None:
    result = await BlockedTasksAction().execute(_context(slice_param="not-an-index"))

    assert not result.success
    assert result.error is not None
    assert "not-an-index" in result.error
