"""HEAD stamps on the actions that can commit (slice 202)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.pipeline.head_stamp import HEAD_AFTER_KEY, HEAD_BEFORE_KEY, execute_stamped, read_head
from squadron.pipeline.models import ActionContext, ActionResult
from tests.conftest import run_test_git


def _context(cwd: Path) -> ActionContext:
    return ActionContext(
        pipeline_name="test",
        run_id="run-001",
        params={},
        step_name="step",
        step_index=0,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        cwd=str(cwd),
    )


class _CommittingAction:
    """An action that commits a file while it runs, as a dispatch agent does."""

    def __init__(self, repo: Path) -> None:
        self._repo = repo

    async def execute(self, context: ActionContext) -> ActionResult:
        (self._repo / "agent.md").write_text("agent\n")
        run_test_git(self._repo, "add", "agent.md")
        run_test_git(self._repo, "commit", "-q", "-m", "agent work")
        return ActionResult(success=True, action_type="dispatch", outputs={})


@pytest.mark.asyncio
async def test_a_dispatch_is_stamped_with_the_head_it_started_from_and_left(
    temp_git_repo: Path,
) -> None:
    before = read_head(str(temp_git_repo))

    result = await execute_stamped(
        _CommittingAction(temp_git_repo),  # type: ignore[arg-type]
        _context(temp_git_repo),
        "dispatch",
    )

    after = run_test_git(temp_git_repo, "rev-parse", "HEAD").strip()
    assert result.metadata[HEAD_BEFORE_KEY] == before
    assert result.metadata[HEAD_AFTER_KEY] == after
    assert before != after


@pytest.mark.asyncio
async def test_an_action_that_cannot_commit_is_not_stamped(temp_git_repo: Path) -> None:
    result = await execute_stamped(
        _CommittingAction(temp_git_repo),  # type: ignore[arg-type]
        _context(temp_git_repo),
        "review",
    )

    assert HEAD_BEFORE_KEY not in result.metadata
    assert HEAD_AFTER_KEY not in result.metadata


@pytest.mark.asyncio
async def test_a_directory_that_is_not_a_repository_leaves_the_result_unstamped(
    tmp_path: Path,
) -> None:
    class _Noop:
        async def execute(self, context: ActionContext) -> ActionResult:
            return ActionResult(success=True, action_type="dispatch", outputs={})

    result = await execute_stamped(_Noop(), _context(tmp_path), "dispatch")  # type: ignore[arg-type]

    assert result.metadata == {}


def test_read_head_is_none_outside_a_repository(tmp_path: Path) -> None:
    assert read_head(str(tmp_path)) is None
