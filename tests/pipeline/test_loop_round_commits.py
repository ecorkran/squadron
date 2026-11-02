"""Loop-round commits through the real executor and a real repo (slice 196 Task 16)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import squadron.pipeline.steps.loop  # noqa: F401 — register the loop step type
from squadron.pipeline.actions.commit import CommitAction
from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.models import ActionContext, ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.steps import register_step_type
from tests.conftest import run_test_git
from tests.pipeline.conftest import phase_artifact_cf_client

SLICE = 105
DESIGN = "project-documents/user/slices/105-slice.stub.md"
REVIEW = "project-documents/user/reviews/105-review.slice.stub.md"


def _step_type(actions: list[tuple[str, dict[str, object]]]) -> MagicMock:
    step_type = MagicMock()
    step_type.expand.return_value = actions
    return step_type


def _write(repo: Path, relative: str, text: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _action(effect: object) -> MagicMock:
    action = MagicMock()
    action.execute = AsyncMock(side_effect=effect)
    return action


async def _run_loop(repo: Path, *, revise_design: bool, verdicts: list[str], tag: str) -> list[str]:
    """Run a P4-style loop and return the messages its round commits were made with, oldest first.

    Read from the commit action's results: a completed loop collapses its commits (slice 202),
    so by then history no longer holds the per-round messages.
    """
    register_step_type(f"_lc_dispatch_{tag}", _step_type([("dispatch", {})]))
    register_step_type(
        f"_lc_review_{tag}",
        _step_type([("review", {"template": "slice", "slice": str(SLICE)})]),
    )
    rounds = iter(range(1, 10))
    verdict_iter = iter(verdicts)

    async def revise(_ctx: ActionContext) -> ActionResult:
        if revise_design:
            _write(repo, DESIGN, f"design v{next(rounds) + 1}\n")
        return ActionResult(success=True, action_type="dispatch", outputs={})

    async def review(_ctx: ActionContext) -> ActionResult:
        verdict = next(verdict_iter)
        _write(repo, REVIEW, f"---\ndocType: review\nverdict: {verdict}\n---\n")
        return ActionResult(success=True, action_type="review", outputs={}, verdict=verdict)

    round_messages: list[str] = []
    real_commit = CommitAction()

    async def commit(ctx: ActionContext) -> ActionResult:
        committed = await real_commit.execute(ctx)
        if committed.outputs.get("committed") is True:
            round_messages.append(str(committed.outputs["message"]))
        return committed

    cf_client = phase_artifact_cf_client(SLICE, DESIGN, "105-tasks.stub.md")
    cf_client.get_config.return_value = ""
    pipeline = PipelineDefinition(
        name="loop-commits",
        description="test",
        params={},
        steps=[
            StepConfig(
                step_type="loop",
                name="design-loop",
                config={
                    "max": len(verdicts),
                    "until": "review.pass",
                    "commit_each_iteration": True,
                    "steps": [{f"_lc_dispatch_{tag}": {}}, {f"_lc_review_{tag}": {}}],
                },
            )
        ],
    )
    result = await execute_pipeline(
        pipeline,
        {"slice": str(SLICE)},
        resolver=MagicMock(),
        cf_client=cf_client,
        cwd=str(repo),
        _action_registry={
            "dispatch": _action(revise),
            "review": _action(review),
            "commit": _action(commit),
        },
    )
    assert result.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}
    return round_messages


@pytest.fixture
def repo_with_design(temp_git_repo: Path) -> Path:
    _write(temp_git_repo, DESIGN, "design v1\n")
    run_test_git(temp_git_repo, "add", "-A")
    run_test_git(temp_git_repo, "commit", "-q", "-m", "design before the loop")
    return temp_git_repo


@pytest.mark.asyncio
async def test_revision_rounds_name_the_slice_the_round_and_the_verdict(
    repo_with_design: Path,
) -> None:
    messages = await _run_loop(
        repo_with_design, revise_design=True, verdicts=["CONCERNS", "PASS"], tag="revise"
    )

    assert messages == [
        "docs: revise slice 105 design, round 1 (review: CONCERNS)",
        "docs: revise slice 105 design, round 2 (review: PASS)",
    ]


@pytest.mark.asyncio
async def test_a_round_that_only_re_reviews_says_so(repo_with_design: Path) -> None:
    messages = await _run_loop(
        repo_with_design, revise_design=False, verdicts=["CONCERNS", "PASS"], tag="rereview"
    )

    assert messages == [
        "review: re-review slice 105 design, round 1 (CONCERNS)",
        "review: re-review slice 105 design, round 2 (PASS)",
    ]


@pytest.mark.asyncio
async def test_no_internal_step_names_reach_history(repo_with_design: Path) -> None:
    messages = await _run_loop(repo_with_design, revise_design=True, verdicts=["PASS"], tag="names")

    assert not any("phase-" in m or "loop" in m for m in messages)
