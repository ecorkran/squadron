"""Tests for squadron.pipeline.batch_report (slice 195 D9)."""

from __future__ import annotations

from pathlib import Path

from squadron.documents.frontmatter import read_frontmatter
from squadron.pipeline.batch_report import (
    BatchItemRecord,
    BatchReport,
    FlagKind,
    ItemDecision,
    ItemOutcome,
)
from squadron.pipeline.executor import ExecutionStatus, StepResult
from squadron.pipeline.models import ActionResult

_REVIEW_FILE = "project-documents/user/reviews/923-review.slice.isolation.md"


def _review(verdict: str, review_file: str | None = _REVIEW_FILE) -> ActionResult:
    return ActionResult(
        success=True,
        action_type="review",
        outputs={"review_file": review_file} if review_file else {},
        verdict=verdict,
    )


def _step(*actions: ActionResult, accepted: bool = False) -> StepResult:
    return StepResult(
        step_name="s",
        step_type="loop",
        status=ExecutionStatus.COMPLETED,
        action_results=list(actions),
        accepted=accepted,
    )


_ITEM: dict[str, object] = {"index": "923", "name": "Test Suite Machine-State Isolation"}


class TestRecordOutcome:
    def test_failure_reason_flags(self) -> None:
        record = BatchItemRecord.from_item(_ITEM, 0, [_step(_review("FAIL"))], "loop exhausted")
        assert record.outcome is ItemOutcome.FLAGGED
        assert record.reason == "loop exhausted"

    def test_accepted_loop_accepts(self) -> None:
        steps = [_step(_review("FAIL")), _step(_review("CONCERNS"), accepted=True)]
        record = BatchItemRecord.from_item(_ITEM, 0, steps)
        assert record.outcome is ItemOutcome.ACCEPTED
        assert record.final_verdict == "CONCERNS"

    def test_otherwise_passed(self) -> None:
        # A skipped loop contributes no actions; the design step's review stands.
        record = BatchItemRecord.from_item(_ITEM, 0, [_step(_review("PASS")), _step()])
        assert record.outcome is ItemOutcome.PASSED
        assert record.final_verdict == "PASS"
        assert record.review_file == _REVIEW_FILE

    def test_pre_flagged_item_with_no_results(self) -> None:
        record = BatchItemRecord.from_item(_ITEM, 0, [], "no design review found")
        assert record.outcome is ItemOutcome.FLAGGED
        assert record.final_verdict is None
        assert record.review_file is None

    def test_item_without_index_or_name_is_labeled_by_position(self) -> None:
        record = BatchItemRecord.from_item({"path": "x"}, 2, [_step(_review("PASS"))])
        assert record.index == "#3"
        assert record.name == ""


def _report() -> BatchReport:
    return BatchReport(
        pipeline="slices-plan",
        run_id="3f9c2a1b7d10",
        step_name="slices",
        plan="900",
        records=[
            BatchItemRecord("923", "Isolation", ItemOutcome.PASSED, final_verdict="PASS"),
            BatchItemRecord("924", "Recover", ItemOutcome.ACCEPTED, final_verdict="CONCERNS"),
            BatchItemRecord("928", "Codex", ItemOutcome.PASSED, final_verdict="PASS"),
            BatchItemRecord(
                "929",
                "Serialize",
                ItemOutcome.FLAGGED,
                reason="step design failed",
                review_file=_REVIEW_FILE,
            ),
        ],
    )


class TestRender:
    def test_frontmatter_parses_and_counts_match(self, tmp_path: Path) -> None:
        path = _report().write(tmp_path)

        assert path == tmp_path / "3f9c2a1b7d10.slices.report.md"
        frontmatter = read_frontmatter(path)
        assert frontmatter == {
            "docType": "batch-report",
            "pipeline": "slices-plan",
            "runId": "3f9c2a1b7d10",
            "plan": "900",
            "passed": 2,
            "accepted": 1,
            "flagged": 1,
            "not_run": 0,
        }

    def test_flagged_section_comes_first_with_reason_and_review(self) -> None:
        text = _report().render()

        flagged = text.index("## Flagged for PM")
        assert flagged < text.index("## Accepted") < text.index("## Passed")
        assert f"- 929 Serialize — step design failed; review: {_REVIEW_FILE}" in text

    def test_no_plan_omits_plan_key(self, tmp_path: Path) -> None:
        report = BatchReport(pipeline="app", run_id="r1", step_name="slices")
        frontmatter = read_frontmatter(report.write(tmp_path))
        assert frontmatter is not None
        assert "plan" not in frontmatter
        assert frontmatter["flagged"] == 0

    def test_summary_line(self) -> None:
        assert _report().summary_line() == (
            "slices-plan slices: 4 items — 2 passed, 1 accepted, 1 flagged, 0 not_run"
        )


class TestUnsavedParts:
    """A split review whose part never reached disk says so next to the item (slice 930)."""

    _PARTS = [
        "project-documents/user/tasks/923-tasks.isolation-1.md",
        "project-documents/user/tasks/923-tasks.isolation-2.md",
    ]

    def test_unsaved_part_renders(self) -> None:
        review = ActionResult(
            success=True,
            action_type="review",
            outputs={"review_file": _REVIEW_FILE, "unsaved_parts": self._PARTS},
            verdict="CONCERNS",
        )
        record = BatchItemRecord.from_item(_ITEM, 0, [_step(review)])

        assert record.unsaved_parts == self._PARTS
        assert record.render_line() == (
            "- 923 Test Suite Machine-State Isolation — verdict CONCERNS; "
            f"review: {_REVIEW_FILE}; unsaved: {self._PARTS[0]}, {self._PARTS[1]}"
        )

    def test_line_without_unsaved_parts_is_unchanged(self) -> None:
        record = BatchItemRecord.from_item(_ITEM, 0, [_step(_review("PASS"))])

        assert record.unsaved_parts == []
        assert record.render_line() == (
            f"- 923 Test Suite Machine-State Isolation — verdict PASS; review: {_REVIEW_FILE}"
        )


# ---------------------------------------------------------------------------
# Flag kinds, decisions and not_run (slice 197 D7)
# ---------------------------------------------------------------------------


class TestStructuredFlags:
    def test_flagged_line_with_every_field(self) -> None:
        record = BatchItemRecord(
            index="196",
            name="Branching",
            outcome=ItemOutcome.FLAGGED,
            reason="loop exhausted at FAIL (accept: review.concerns_or_better)",
            final_verdict="FAIL",
            review_file=_REVIEW_FILE,
            flag_kind=FlagKind.REVIEW_UNRESOLVED,
            failed_step="revise-code",
            branch="196-slice.branching",
            decision=ItemDecision.RETRY,
            resumed_at="2026-10-05T12:00:00+00:00",
        )

        assert record.render_line() == (
            "- 196 Branching — review_unresolved at revise-code; "
            "loop exhausted at FAIL (accept: review.concerns_or_better); verdict FAIL; "
            "branch 196-slice.branching; decision retry at 2026-10-05T12:00:00+00:00; "
            f"review: {_REVIEW_FILE}"
        )

    def test_a_pre_flag_has_no_failed_step_or_branch(self) -> None:
        record = BatchItemRecord(
            index="301",
            name="S",
            outcome=ItemOutcome.FLAGGED,
            reason="no task file",
            flag_kind=FlagKind.NOT_READY,
        )

        assert record.render_line() == "- 301 S — not_ready; no task file"

    def test_not_run_lines_render_in_their_own_section_with_the_reason(self) -> None:
        report = BatchReport("implement-plan", "r1", "slices", plan="180")
        report.records = [
            BatchItemRecord("1", "A", ItemOutcome.PASSED),
            BatchItemRecord("2", "B", ItemOutcome.NOT_RUN, reason="run halted: git state unknown"),
        ]

        text = report.render()

        assert text.index("## Flagged for PM") < text.index("## Not run") < text.index("## Passed")
        assert "- 2 B — run halted: git state unknown" in text
        assert report.summary_line() == (
            "implement-plan slices: 2 items — 1 passed, 0 accepted, 0 flagged, 1 not_run"
        )
