"""squadron.dispatch-branch-work: an implement dispatch must leave commits."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from squadron.events import EventType
from squadron.events.builtin.dispatch_branch_work import DispatchBranchWorkAction
from squadron.events.contexts import PostActionContext
from squadron.pipeline.actions.dispatch import SKIPPED_KEY
from squadron.pipeline.models import ActionResult

_MODULE = "squadron.events.builtin.dispatch_branch_work"


def _context(
    *,
    step_type: str = "implement",
    action_type: str = "dispatch",
    outputs: dict[str, object] | None = None,
    success: bool = True,
) -> PostActionContext:
    return PostActionContext(
        event=EventType.POST_ACTION,
        cwd=".",
        params={"slice": "127"},
        action_type=action_type,
        result=ActionResult(
            success=success,
            action_type=action_type,
            outputs=outputs if outputs is not None else {"response": "Two questions for the PM."},
        ),
        run_id="run-1",
        run_started_at=None,
        run_state_error=None,
        step_name="implement-1",
        step_type=step_type,
        expected_artifact_kind=None,
        iteration=0,
        cf_client=MagicMock(),
    )


@pytest.fixture(autouse=True)
def implement_dispatch_left_commits() -> None:
    """Override the suite-wide stub: these tests exercise the real counting path."""


def _patched(ahead: int):  # noqa: ANN202
    return (
        patch(f"{_MODULE}.read_integration_target", return_value="main"),
        patch(f"{_MODULE}.slice_facts", return_value=("127-slice.x", None)),
        patch(f"{_MODULE}.branch_work_count", return_value=ahead),
    )


async def test_no_commits_fails_with_agent_text() -> None:
    p1, p2, p3 = _patched(0)
    with p1, p2, p3:
        result = await DispatchBranchWorkAction().execute(_context())
    assert not result.success
    assert result.error is not None
    assert "127-slice.x" in result.error
    assert "Two questions for the PM." in result.error


async def test_commits_pass() -> None:
    p1, p2, p3 = _patched(3)
    with p1, p2, p3:
        result = await DispatchBranchWorkAction().execute(_context())
    assert result.success


@pytest.mark.parametrize(
    "ctx",
    [
        _context(step_type="design"),
        _context(action_type="review"),
        _context(success=False),
        _context(outputs={SKIPPED_KEY: "branch-has-work"}),
    ],
)
async def test_not_applicable_never_counts_commits(ctx: PostActionContext) -> None:
    with patch(f"{_MODULE}.branch_work_count") as count:
        result = await DispatchBranchWorkAction().execute(ctx)
    assert result.success
    count.assert_not_called()
