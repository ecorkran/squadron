"""Tests for squadron.pipeline.batch_report (slice 195 D9)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.documents.frontmatter import read_frontmatter
from squadron.pipeline.batch_report import (
    BatchItemRecord,
    BatchReport,
    BatchReportLoadError,
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


# ---------------------------------------------------------------------------
# report.json (slice 197 D7)
# ---------------------------------------------------------------------------


def _json_report() -> BatchReport:
    report = BatchReport("implement-plan", "3f9c2a1b7d10", "slices", plan="180")
    report.records = [
        BatchItemRecord(
            "196",
            "Branching",
            ItemOutcome.FLAGGED,
            reason="loop exhausted at FAIL",
            final_verdict="FAIL",
            review_file=_REVIEW_FILE,
            flag_kind=FlagKind.REVIEW_UNRESOLVED,
            failed_step="revise-code",
            branch="196-slice.branching",
        ),
        BatchItemRecord(
            "197",
            "Batch",
            ItemOutcome.PASSED,
            decision=ItemDecision.RETRY,
            resumed_at="2026-10-05T12:00:00+00:00",
        ),
        BatchItemRecord("198", "Later", ItemOutcome.NOT_RUN, reason="run halted"),
    ]
    return report


class TestReportJson:
    def test_written_beside_the_markdown_with_the_d7_shape(self, tmp_path: Path) -> None:
        _json_report().write(tmp_path)

        data = json.loads((tmp_path / "3f9c2a1b7d10.slices.report.json").read_text())
        assert data["docType"] == "batch-report"
        assert data["schemaVersion"] == 1
        assert (data["pipeline"], data["runId"], data["stepName"], data["plan"]) == (
            "implement-plan",
            "3f9c2a1b7d10",
            "slices",
            "180",
        )
        assert data["counts"] == {"passed": 1, "accepted": 0, "flagged": 1, "not_run": 1}
        assert data["items"][0] == {
            "index": "196",
            "name": "Branching",
            "outcome": "flagged",
            "flagKind": "review_unresolved",
            "failedStep": "revise-code",
            "reason": "loop exhausted at FAIL",
            "finalVerdict": "FAIL",
            "reviewFile": _REVIEW_FILE,
            "unsavedParts": [],
            "branch": "196-slice.branching",
            "decision": None,
            "resumedAt": None,
        }

    def test_round_trip(self, tmp_path: Path) -> None:
        report = _json_report()
        report.write(tmp_path)

        loaded = BatchReport.load(report.json_path(tmp_path))

        assert loaded.records == report.records
        assert (loaded.pipeline, loaded.run_id, loaded.step_name, loaded.plan) == (
            report.pipeline,
            report.run_id,
            report.step_name,
            report.plan,
        )

    def test_a_failed_write_keeps_the_previous_report_and_logs_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        report = _json_report()
        report.write(tmp_path)
        before = report.json_path(tmp_path).read_text()
        report.records.append(BatchItemRecord("199", "New", ItemOutcome.PASSED))

        with (
            patch.object(Path, "replace", side_effect=OSError(28, "No space left on device")),
            caplog.at_level(logging.ERROR, logger="squadron.pipeline.batch_report"),
        ):
            with pytest.raises(OSError, match="No space left"):
                report.write(tmp_path)

        assert report.json_path(tmp_path).read_text() == before
        assert any(
            r.levelno == logging.ERROR and str(report.path(tmp_path)) in r.getMessage()
            for r in caplog.records
        )

    def test_a_version_mismatch_names_both_versions(self, tmp_path: Path) -> None:
        path = tmp_path / "r.report.json"
        path.write_text(json.dumps({"schemaVersion": 2, "items": []}))

        with pytest.raises(BatchReportLoadError, match="schemaVersion 2; .* schemaVersion 1"):
            BatchReport.load(path)

    def test_an_unparseable_file_names_the_path(self, tmp_path: Path) -> None:
        path = tmp_path / "r.report.json"
        path.write_text("{not json")

        with pytest.raises(BatchReportLoadError, match=f"batch report {path} is unreadable"):
            BatchReport.load(path)

    def test_a_missing_file_names_the_path(self, tmp_path: Path) -> None:
        path = tmp_path / "absent.report.json"

        with pytest.raises(BatchReportLoadError, match=f"batch report {path} not found"):
            BatchReport.load(path)
