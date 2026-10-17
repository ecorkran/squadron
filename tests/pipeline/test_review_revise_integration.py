"""The composed review-revise pipeline run end to end on a throwaway repo (slice 941).

Fake review and dispatch actions stand in for the models; the loop, the observer,
the commit action and git are real.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import squadron.pipeline.steps.loop  # noqa: F401 — register the loop step type
from squadron.pipeline.actions.commit import CommitAction
from squadron.pipeline.executor import ExecutionStatus, PipelineResult, execute_pipeline
from squadron.pipeline.models import ActionContext, ActionResult
from squadron.pipeline.review_revise import build_review_revise_definition
from squadron.pipeline.state import StateManager
from squadron.review.persistence import archive_existing_review
from squadron.review.templates import BuiltinReviewTemplate
from tests.conftest import run_test_git
from tests.pipeline.conftest import phase_artifact_cf_client
from tests.pipeline.observer_support import RecordingObserver

SLICE = 105
DESIGN = "project-documents/user/slices/105-slice.stub.md"
REVIEW = "project-documents/user/reviews/105-review.slice.stub.md"


def _write(repo: Path, relative: str, text: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _action(effect: object) -> MagicMock:
    action = MagicMock()
    action.execute = AsyncMock(side_effect=effect)
    return action


async def _run(repo: Path, verdicts: list[str]) -> tuple[PipelineResult, RecordingObserver]:
    """Run P4's loop after a leading review, one fake review verdict per call."""
    revisions = iter(range(2, 20))
    verdict_iter = iter(verdicts)

    async def revise(_ctx: ActionContext) -> ActionResult:
        _write(repo, DESIGN, f"design v{next(revisions)}\n")
        return ActionResult(success=True, action_type="dispatch", outputs={})

    async def review(_ctx: ActionContext) -> ActionResult:
        verdict = next(verdict_iter)
        # What the real review action does before it saves: keep the prior review.
        assert archive_existing_review(repo / REVIEW)
        _write(repo, REVIEW, f"---\ndocType: review\nverdict: {verdict}\n---\n")
        return ActionResult(success=True, action_type="review", outputs={}, verdict=verdict)

    definition = build_review_revise_definition(BuiltinReviewTemplate.SLICE)
    params: dict[str, object] = {
        key: value for key, value in definition.params.items() if value != "required"
    } | {"slice": str(SLICE), "review-model": "fake-reviewer", "max-revisions": "3"}
    cf_client = phase_artifact_cf_client(SLICE, DESIGN, "105-tasks.stub.md")
    cf_client.get_config.return_value = ""
    observer = RecordingObserver()
    # Scratch run state outside the repo, as `sq review --max` writes (#236).
    runs_dir = repo.parent / "runs"
    run_id = StateManager(runs_dir=runs_dir).init_run(definition.name, params)
    result = await execute_pipeline(
        definition,
        params,
        resolver=MagicMock(),
        cf_client=cf_client,
        cwd=str(repo),
        run_id=run_id,
        runs_dir=runs_dir,
        observer=observer,
        _action_registry={
            "dispatch": _action(revise),
            "review": _action(review),
            "commit": CommitAction(),
        },
    )
    return result, observer


@pytest.fixture
def repo_with_design(temp_git_repo: Path) -> Path:
    _write(temp_git_repo, DESIGN, "design v1\n")
    run_test_git(temp_git_repo, "add", "-A")
    run_test_git(temp_git_repo, "commit", "-q", "-m", "design before the loop")
    return temp_git_repo


@pytest.mark.asyncio
async def test_two_rounds_concerns_then_pass(repo_with_design: Path) -> None:
    result, observer = await _run(repo_with_design, ["CONCERNS", "CONCERNS", "PASS"])

    assert result.status == ExecutionStatus.COMPLETED
    loop = result.step_results[1]
    assert loop.iteration == 2
    assert [r.verdict for r in loop.action_results if r.action_type == "review"] == ["PASS"]
    assert [iteration for _, iteration, _ in observer.rounds] == [1, 2]
    for _, _, round_results in observer.rounds:
        commit = next(r for r in round_results if r.action_type == "commit")
        assert commit.success and commit.outputs["committed"] is True
    subjects = run_test_git(repo_with_design, "log", "--format=%s", "--reverse").splitlines()
    assert len(subjects) == 4  # init, the design, one commit per round
    assert (repo_with_design / "project-documents/user/reviews/archive" / Path(REVIEW).name).exists()
    assert "verdict: PASS" in (repo_with_design / REVIEW).read_text()
    assert (repo_with_design / DESIGN).read_text() == "design v3\n"


@pytest.mark.asyncio
async def test_a_passing_first_review_runs_zero_rounds(repo_with_design: Path) -> None:
    result, observer = await _run(repo_with_design, ["PASS"])

    assert result.status == ExecutionStatus.COMPLETED
    assert result.step_results[1].iteration == 0
    assert observer.rounds == []
    assert len(run_test_git(repo_with_design, "log", "--format=%s").splitlines()) == 2
