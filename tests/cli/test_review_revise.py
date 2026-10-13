"""Tests for the review-revise CLI runner and its RoundPrinter (slice 941)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.cli.commands.review_revise import RoundPrinter, outcome_of, run_review_revise
from squadron.pipeline.actions.review_outputs import ReviewOutputKey
from squadron.pipeline.executor import ExecutionStatus, PipelineResult, StepResult
from squadron.pipeline.models import ActionResult
from squadron.review.templates import BuiltinReviewTemplate


def _review(verdict: str | None, findings: int = 0, file_name: str | None = None) -> ActionResult:
    outputs: dict[str, object] = {}
    if file_name is not None:
        outputs[ReviewOutputKey.REVIEW_FILE] = file_name
    return ActionResult(
        success=True,
        action_type="review",
        outputs=outputs,
        verdict=verdict,
        findings=[{"id": f"F{n}"} for n in range(findings)],
    )


def _commit(outputs: dict[str, object], *, success: bool = True) -> ActionResult:
    return ActionResult(
        success=success, action_type="commit", outputs=outputs, error=None if success else "boom"
    )


def _printer() -> tuple[RoundPrinter, list[str]]:
    lines: list[str] = []
    return RoundPrinter(write=lines.append), lines


def test_header_names_kind_slice_models_and_max() -> None:
    printer, lines = _printer()

    printer.header("slice", "941", "sol", "opus", 3)

    assert lines == ["review-revise slice 941  reviewer=sol  reviser=opus  max=3"]


def test_leading_review_prints_verdict_finding_count_and_file() -> None:
    printer, lines = _printer()
    result = StepResult(
        step_name="review",
        step_type="review",
        status=ExecutionStatus.COMPLETED,
        action_results=[_review("CONCERNS", findings=4, file_name="941-review.slice.x.md")],
    )

    printer.step_completed(result)

    assert lines == ["  review    CONCERNS (4)  941-review.slice.x.md"]


def test_other_steps_print_nothing() -> None:
    printer, lines = _printer()
    printer.step_completed(
        StepResult(
            step_name="revise-1",
            step_type="loop",
            status=ExecutionStatus.COMPLETED,
            action_results=[],
        )
    )

    assert lines == []


def test_round_with_a_commit_prints_verdict_and_short_sha() -> None:
    printer, lines = _printer()

    printer.round_completed(
        "loop-1", 2, [_review("PASS"), _commit({"committed": True, "sha": "d4e5f6a7b8c9"})]
    )

    assert lines == ["  round 2   " + "PASS".ljust(14) + "committed d4e5f6a"]


def test_round_with_a_failed_commit_says_so() -> None:
    printer, lines = _printer()

    printer.round_completed("loop-1", 1, [_review("CONCERNS", findings=2), _commit({}, success=False)])

    assert lines == ["  round 1   CONCERNS (2)  commit failed"]


def test_round_with_nothing_to_commit_says_no_changes() -> None:
    printer, lines = _printer()

    printer.round_completed("loop-1", 1, [_review("FAIL", findings=1), _commit({"committed": False})])

    assert lines == ["  round 1   " + "FAIL (1)".ljust(14) + "no changes"]


def test_round_without_a_review_raises() -> None:
    printer, _ = _printer()

    with pytest.raises(ValueError, match="no review result"):
        printer.round_completed("loop-1", 1, [_commit({"committed": False})])


def test_round_without_a_commit_raises() -> None:
    printer, _ = _printer()

    with pytest.raises(ValueError, match="no commit result"):
        printer.round_completed("loop-1", 1, [_review("PASS")])


def test_review_without_a_verdict_raises() -> None:
    printer, _ = _printer()

    with pytest.raises(ValueError, match="no verdict"):
        printer.round_completed("loop-1", 1, [_review(None), _commit({"committed": False})])


# ---------------------------------------------------------------------------
# Runner: params, exit codes, outcome mapping (slice 941 D3, D5)
# ---------------------------------------------------------------------------

_MODULE = "squadron.cli.commands.review_revise"


def _step(
    name: str,
    step_type: str,
    results: list[ActionResult],
    *,
    status: ExecutionStatus = ExecutionStatus.COMPLETED,
    iteration: int = 0,
    accepted: bool = False,
    exhausted: bool = False,
    error: str | None = None,
) -> StepResult:
    return StepResult(
        step_name=name,
        step_type=step_type,
        status=status,
        action_results=results,
        iteration=iteration,
        accepted=accepted,
        exhausted=exhausted,
        error=error,
    )


def _result(*steps: StepResult) -> PipelineResult:
    failed = any(s.status != ExecutionStatus.COMPLETED for s in steps)
    return PipelineResult(
        pipeline_name="review-revise-slice",
        status=ExecutionStatus.FAILED if failed else ExecutionStatus.COMPLETED,
        step_results=list(steps),
    )


def _leading(verdict: str) -> StepResult:
    return _step("review", "review", [_review(verdict)])


def _round_results(verdict: str) -> list[ActionResult]:
    return [_review(verdict), _commit({"committed": True, "sha": "abc1234def"})]


@pytest.mark.parametrize(("verdict", "code"), [("PASS", 0), ("CONCERNS", 0), ("FAIL", 2)])
def test_zero_rounds_exit_follows_the_leading_verdict(verdict: str, code: int) -> None:
    outcome = outcome_of(_result(_leading(verdict), _step("loop-1", "loop", [], iteration=0)))

    assert (outcome.exit_code, outcome.final_verdict, outcome.rounds) == (code, verdict, 0)


def test_loop_that_met_until_uses_its_last_rounds_verdict() -> None:
    loop = _step("loop-1", "loop", _round_results("PASS"), iteration=2)

    outcome = outcome_of(_result(_leading("CONCERNS"), loop))

    assert (outcome.exit_code, outcome.final_verdict, outcome.rounds) == (0, "PASS", 2)


def test_exhausted_and_accepted_exits_zero() -> None:
    loop = _step(
        "loop-1", "loop", _round_results("CONCERNS"), iteration=2, accepted=True, exhausted=True
    )

    outcome = outcome_of(_result(_leading("FAIL"), loop))

    assert (outcome.exit_code, outcome.final_verdict) == (0, "CONCERNS")


def test_exhausted_not_accepted_exits_two_not_one() -> None:
    loop = _step(
        "loop-1",
        "loop",
        _round_results("FAIL"),
        status=ExecutionStatus.FAILED,
        iteration=2,
        exhausted=True,
        error="loop exhausted at FAIL",
    )

    outcome = outcome_of(_result(_leading("FAIL"), loop))

    assert (outcome.exit_code, outcome.final_verdict, outcome.error) == (2, "FAIL", None)


def test_failed_revise_dispatch_exits_one_with_the_error() -> None:
    loop = _step(
        "loop-1",
        "loop",
        [],
        status=ExecutionStatus.FAILED,
        iteration=1,
        error="loop loop-1 round 1: revise dispatch failed: timed out",
    )

    outcome = outcome_of(_result(_leading("CONCERNS"), loop))

    assert outcome.exit_code == 1
    assert outcome.error == "loop loop-1 round 1: revise dispatch failed: timed out"


def test_failed_round_commit_exits_one_with_the_executors_text() -> None:
    loop = _step(
        "loop-1",
        "loop",
        [_review("CONCERNS"), _commit({}, success=False)],
        status=ExecutionStatus.FAILED,
        iteration=1,
        error="loop loop-1 round 1 commit failed: hook rejected",
    )

    outcome = outcome_of(_result(_leading("CONCERNS"), loop))

    assert outcome.exit_code == 1
    assert outcome.error == "loop loop-1 round 1 commit failed: hook rejected"


def test_failed_leading_review_exits_one_with_the_action_error() -> None:
    failed = ActionResult(success=False, action_type="review", outputs={}, error="model unreachable")
    review = _step("review", "review", [failed], status=ExecutionStatus.FAILED)

    outcome = outcome_of(_result(review))

    assert (outcome.exit_code, outcome.error) == (1, "model unreachable")


def _run_with(result: PipelineResult, **kwargs: object) -> tuple[int, AsyncMock, MagicMock]:
    """Run the runner with the executor stubbed; return the exit code and the stubs."""
    execute = AsyncMock(return_value=result)
    classification = MagicMock(needs_persistent_session=False)
    arguments: dict[str, object] = {
        "kind": BuiltinReviewTemplate.SLICE,
        "slice_index": "941",
        "reviewer": "sol",
        "revise_model": None,
        "max_rounds": 3,
        "cwd": "/repo",
    } | kwargs
    with (
        patch(f"{_MODULE}.execute_pipeline", execute),
        patch(f"{_MODULE}.classify_for_run", return_value=classification) as classify,
        patch(f"{_MODULE}.ContextForgeClient"),
    ):
        code = run_review_revise(**arguments)  # type: ignore[arg-type]
    return code, execute, classify


def test_params_carry_slice_reviewer_and_rounds_without_a_reviser() -> None:
    _, execute, _ = _run_with(_result(_leading("PASS"), _step("loop-1", "loop", [])))

    params = execute.await_args.args[1]
    assert (params["slice"], params["review-model"], params["max-revisions"]) == ("941", "sol", "3")
    assert params["model"] == "opus"  # P4's own default, untouched


def test_revise_model_overrides_the_pipeline_default() -> None:
    _, execute, _ = _run_with(
        _result(_leading("PASS"), _step("loop-1", "loop", [])), revise_model="sonnet"
    )

    assert execute.await_args.args[1]["model"] == "sonnet"


def test_a_pool_alias_reaches_review_model_unchanged() -> None:
    _, execute, _ = _run_with(
        _result(_leading("PASS"), _step("loop-1", "loop", [])), reviewer="pool:cheap"
    )

    assert execute.await_args.args[1]["review-model"] == "pool:cheap"


def test_zero_rounds_prints_the_leading_verdict_and_zero_rounds(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, _, _ = _run_with(_result(_leading("PASS"), _step("loop-1", "loop", [])))

    out = capsys.readouterr().out
    assert code == 0
    assert "final: PASS after 0 rounds" in out
    assert "reviewer=sol  reviser=opus  max=3" in out


def test_failed_round_commit_prints_the_error_on_stderr_and_exits_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    loop = _step(
        "loop-1",
        "loop",
        [_review("CONCERNS"), _commit({}, success=False)],
        status=ExecutionStatus.FAILED,
        iteration=1,
        error="loop loop-1 round 1 commit failed: hook rejected",
    )

    code, _, _ = _run_with(_result(_leading("CONCERNS"), loop))

    assert code == 1
    assert "round 1 commit failed: hook rejected" in capsys.readouterr().err
