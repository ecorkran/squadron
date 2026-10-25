"""Tests for SquashAction on real repositories (slice 948 D6)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from squadron.pipeline.actions.squash import SquashAction
from squadron.pipeline.models import ActionContext, ActionResult
from tests.conftest import run_test_git
from tests.pipeline.commit_fixtures import cf_client
from tests.pipeline.squash_helpers import head, planning_run


def _run(repo: Path, **params: object) -> ActionResult:
    context = ActionContext(
        pipeline_name="test-pipeline",
        run_id="run-001",
        params={"subject": "design", "slice": "105", **params},
        step_name="squash-step",
        step_index=0,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=cf_client(),
        cwd=str(repo),
    )
    return asyncio.run(SquashAction().execute(context))


def test_planning_run_is_squashed_and_outputs_say_so(temp_git_repo: Path) -> None:
    planning_run(temp_git_repo, 3)

    result = _run(temp_git_repo)

    assert result.success, result.error
    assert result.outputs["squashed"] == 3
    assert result.outputs["commit"] == head(temp_git_repo)
    tag = run_test_git(temp_git_repo, "tag", "-l", "squash-backup/*").strip()
    assert result.outputs["backup_tag"] == tag


def test_no_run_succeeds_with_zero(temp_git_repo: Path) -> None:
    planning_run(temp_git_repo, 1)

    result = _run(temp_git_repo)

    assert result.success, result.error
    assert result.outputs == {"squashed": 0}


def test_refusal_fails_the_step(temp_git_repo: Path) -> None:
    planning_run(temp_git_repo, 2)
    (temp_git_repo / "README.md").write_text("dirty\n")

    result = _run(temp_git_repo)

    assert result.success is False
    assert result.error is not None and "not clean" in result.error


def test_bad_slice_value_fails_the_step(temp_git_repo: Path) -> None:
    result = _run(temp_git_repo, slice={"index": 105})

    assert result.success is False
    assert result.error is not None and "slice index" in result.error
