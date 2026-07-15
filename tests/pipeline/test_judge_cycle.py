"""Control-flow tests for the judge-cycle built-in pipeline.

Loads the real `judge-cycle.yaml` shipped artifact and drives it through
`execute_pipeline` with a real `ReviewAction` (only `run_review_with_profile`
and persistence are mocked) and a mocked `dispatch` action. `resolve_thresholds`
and `enforce_judge` run for real, so these tests prove control flow — score
in, derived verdict, loop exit/exhaust — not model behavior.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.pipeline.actions.review import ReviewAction
from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import ActionResult
from squadron.pipeline.steps import bootstrap_step_types
from squadron.review.models import ReviewResult, Verdict

_P = "squadron.pipeline.actions.review"
_NONEXISTENT = Path("/nonexistent")


def _make_review_result(score: float) -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.CONCERNS,
        findings=[],
        raw_output="## Review\n",
        template_name="judge.slice-vs-arch",
        input_files={"cwd": "/tmp/test"},
        timestamp=datetime(2026, 7, 14, 12, 0, 0),
        model="claude-sonnet-4-20250514",
        score=score,
        criteria=None,
    )


def _slice_info(design_file: str, arch_file: str) -> dict[str, object]:
    return {
        "index": 303,
        "name": "judge-gated-cycle-conventions",
        "slice_name": "judge-gated-cycle-conventions",
        "design_file": design_file,
        "task_files": ["303-tasks.judge-gated-cycle-conventions.md"],
        "arch_file": arch_file,
    }


async def _run_judge_cycle(
    dispatch_mock: MagicMock,
    tmp_path: Path,
    score: float,
    judge_override: dict[str, object] | None = None,
) -> object:
    """Load the real judge-cycle definition and execute it with a forced score.

    Returns the PipelineResult. Real design/arch tmp files satisfy the
    issue-#18 missing-input hard-fail; `resolve_slice_info` is mocked only to
    point at them, not to fabricate the judge verdict path. `judge_override`,
    when given, is injected into the loop body's review step config — the
    exact step-level `judge:` override a user would write.
    """
    bootstrap_step_types()

    definition = load_pipeline("judge-cycle", project_dir=_NONEXISTENT, user_dir=_NONEXISTENT)
    if judge_override is not None:
        loop_config = definition.steps[0].config
        loop_config["steps"][1]["review"]["judge"] = judge_override

    design_file = tmp_path / "303-slice.md"
    design_file.write_text("# slice design\n")
    arch_file = tmp_path / "100-arch.md"
    arch_file.write_text("# architecture\n")

    resolver = MagicMock()
    resolver.resolve.return_value = ("claude-sonnet-4-20250514", None)

    with (
        patch(f"{_P}.resolve_slice_info", return_value=_slice_info(str(design_file), str(arch_file))),
        patch(f"{_P}.run_review_with_profile", return_value=_make_review_result(score)),
        patch(f"{_P}.save_review_file", return_value=None),
        patch(f"{_P}.format_review_markdown", return_value="# Review"),
    ):
        return await execute_pipeline(
            definition,
            {"slice": "303"},
            resolver=resolver,
            cf_client=MagicMock(),
            cwd=str(tmp_path),
            _action_registry={"dispatch": dispatch_mock, "review": ReviewAction()},
        )


def _dispatch_mock() -> MagicMock:
    action = MagicMock()
    action.execute = AsyncMock(
        return_value=ActionResult(success=True, action_type="dispatch", outputs={})
    )
    return action


class TestJudgeCycleAutoAdvance:
    @pytest.mark.asyncio
    async def test_judge_cycle_auto_advance(self, tmp_path: Path) -> None:
        dispatch_mock = _dispatch_mock()
        # 90 clears judge.slice-vs-arch's default pass_floor (82).
        result = await _run_judge_cycle(dispatch_mock, tmp_path, score=90.0)

        assert result.status == ExecutionStatus.COMPLETED
        loop_result = result.step_results[0]
        assert loop_result.iteration == 1
        assert dispatch_mock.execute.await_count == 1


class TestJudgeCycleEscalates:
    @pytest.mark.asyncio
    async def test_judge_cycle_escalates(self, tmp_path: Path) -> None:
        dispatch_mock = _dispatch_mock()
        # 40 is below judge.slice-vs-arch's default concerns_floor (60) —
        # FAIL on every iteration, never clears `until: review.pass`.
        result = await _run_judge_cycle(dispatch_mock, tmp_path, score=40.0)

        assert result.status == ExecutionStatus.PAUSED
        loop_result = result.step_results[0]
        assert loop_result.status == ExecutionStatus.PAUSED
        assert dispatch_mock.execute.await_count == 3

        last_review = loop_result.action_results[-1]
        assert last_review.action_type == "review"
        assert last_review.score == 40.0


class TestJudgeCycleAdvisoryAlwaysEscalates:
    @pytest.mark.asyncio
    async def test_judge_cycle_advisory_always_escalates(self, tmp_path: Path) -> None:
        dispatch_mock = _dispatch_mock()
        # 95 is well above the default pass_floor (82) but below the
        # step-level advisory override (101) — the gate is the threshold,
        # not the model, and pass_floor > 100 is a sanctioned unclamped value.
        result = await _run_judge_cycle(
            dispatch_mock,
            tmp_path,
            score=95.0,
            judge_override={"pass_floor": 101},
        )

        assert result.status == ExecutionStatus.PAUSED
        loop_result = result.step_results[0]
        assert loop_result.status == ExecutionStatus.PAUSED
        assert dispatch_mock.execute.await_count == 3
