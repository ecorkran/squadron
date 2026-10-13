"""Tests for the review-revise CLI runner and its RoundPrinter (slice 941)."""

from __future__ import annotations

import pytest

from squadron.cli.commands.review_revise import RoundPrinter
from squadron.pipeline.actions.review_outputs import ReviewOutputKey
from squadron.pipeline.executor import ExecutionStatus, StepResult
from squadron.pipeline.models import ActionResult


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
