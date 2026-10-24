"""A dirty tree fails a branch-entering run at start, before any step spends (#256)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.pipeline.actions.branch import BranchAction
from squadron.pipeline.actions.protocol import RunPreflight
from squadron.pipeline.executor import execute_pipeline
from squadron.pipeline.models import PipelineDefinition, StepConfig


def _dirty(repo: Path) -> Path:
    (repo / "262-slice.other.md").write_text("left over\n")
    return repo


def test_branch_action_is_a_run_preflight() -> None:
    assert isinstance(BranchAction(), RunPreflight)


def test_dirty_tree_with_an_enter_is_refused(temp_git_repo: Path) -> None:
    with pytest.raises(ValueError, match=r"working tree not clean: 262-slice\.other\.md"):
        BranchAction().preflight({"op": "enter"}, str(_dirty(temp_git_repo)))


def test_clean_tree_with_an_enter_passes(temp_git_repo: Path) -> None:
    BranchAction().preflight({"op": "enter"}, str(temp_git_repo))


@pytest.mark.parametrize("params", [{"op": "merge"}, {"op": "enter", "when": "false"}])
def test_dirty_tree_without_an_enabled_enter_passes(
    temp_git_repo: Path, params: dict[str, object]
) -> None:
    BranchAction().preflight(params, str(_dirty(temp_git_repo)))


def _definition() -> PipelineDefinition:
    return PipelineDefinition(
        name="p",
        description="",
        params={},
        steps=[
            StepConfig(step_type="branch", name="branch-0", config={"op": "enter", "when": "{merge}"}),
        ],
    )


async def test_fresh_run_refuses_a_dirty_tree_before_its_first_step(temp_git_repo: Path) -> None:
    observer = MagicMock()

    with pytest.raises(ValueError, match="working tree not clean"):
        await execute_pipeline(
            _definition(),
            {"merge": "true", "_project": "p"},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            cwd=str(_dirty(temp_git_repo)),
            observer=observer,
        )

    observer.step_started.assert_not_called()
