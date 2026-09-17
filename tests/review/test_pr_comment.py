"""Tests for the pure PR comment composer (D2, D4).

No host, no fake runner: ``compose_comment`` takes a ``ReviewResult`` and a
``PullRequestRecord`` and returns a string.
"""

from __future__ import annotations

from datetime import datetime

from squadron.codehost.models import PullRequestRecord
from squadron.review.models import ReviewFinding, ReviewResult, Severity, Verdict
from squadron.review.pr_comment import MARKER_PREFIX, compose_comment, marker_for

_HEAD = "1111111111111111111111111111111111111111"


def _record(number: int = 42, head_sha: str = _HEAD) -> PullRequestRecord:
    return PullRequestRecord(
        host="github.com",
        owner="ecorkran",
        repository="squadron",
        number=number,
        base_ref="main",
        head_ref="feature",
        head_sha=head_sha,
        url=f"https://github.com/ecorkran/squadron/pull/{number}",
    )


def _finding(
    severity: Severity = Severity.CONCERN,
    title: str = "Missing error handling",
    category: str | None = "error-handling",
) -> ReviewFinding:
    return ReviewFinding(
        severity=severity,
        title=title,
        description="detail",
        file_ref="src/foo.py:10",
        category=category,
        location="src/foo.py:10",
    )


def _result(
    verdict: Verdict = Verdict.CONCERNS,
    findings: list[ReviewFinding] | None = None,
    model: str = "z-ai/glm-5.3",
) -> ReviewResult:
    return ReviewResult(
        verdict=verdict,
        findings=[_finding()] if findings is None else findings,
        raw_output="raw",
        template_name="code",
        input_files={"input": "pr"},
        timestamp=datetime(2026, 4, 1, 12, 0, 0),
        model=model,
    )


class TestMarker:
    def test_marker_shape_carries_the_record_key(self) -> None:
        assert marker_for(_record()) == f"{MARKER_PREFIX} github.com/ecorkran/squadron#42 -->"

    def test_marker_uses_key_not_path_key(self) -> None:
        record = _record()
        marker = marker_for(record)
        assert record.path_key not in marker
        assert record.key in marker


class TestSeverityGroupingAndOrder:
    def test_findings_are_grouped_fail_concern_note_pass(self) -> None:
        findings = [
            _finding(Severity.NOTE, "note-1"),
            _finding(Severity.FAIL, "fail-1"),
            _finding(Severity.CONCERN, "concern-1"),
            _finding(Severity.PASS, "pass-1"),
        ]
        body = compose_comment(_result(findings=findings), _record(), live_head_sha=_HEAD)

        fail_pos = body.index("fail-1")
        concern_pos = body.index("concern-1")
        note_pos = body.index("note-1")
        pass_pos = body.index("pass-1")
        assert fail_pos < concern_pos < note_pos < pass_pos

    def test_original_order_preserved_within_a_group(self) -> None:
        findings = [
            _finding(Severity.CONCERN, "concern-first"),
            _finding(Severity.CONCERN, "concern-second"),
        ]
        body = compose_comment(_result(findings=findings), _record(), live_head_sha=_HEAD)

        assert body.index("concern-first") < body.index("concern-second")


class TestNoFindings:
    def test_pass_with_no_findings_renders_the_explicit_line(self) -> None:
        body = compose_comment(
            _result(verdict=Verdict.PASS, findings=[]), _record(), live_head_sha=_HEAD
        )
        assert "_No findings._" in body


class TestContainment:
    def test_a_summary_with_a_marker_opener_yields_exactly_one_marker(self) -> None:
        findings = [_finding(title=f"quoting {MARKER_PREFIX} evil -->")]
        record = _record()
        body = compose_comment(_result(findings=findings), record, live_head_sha=_HEAD)

        assert body.count(marker_for(record)) == 1
        # And the forged one is neutralized rather than dropped silently.
        assert "quoting" in body

    def test_triple_backtick_in_a_summary_does_not_break_structure(self) -> None:
        findings = [_finding(title="summary with ``` inline")]
        body = compose_comment(_result(findings=findings), _record(), live_head_sha=_HEAD)

        assert "summary with ``` inline" in body


class TestSize:
    def test_a_review_over_the_bound_truncates_and_names_the_count(self) -> None:
        findings = [_finding(title=f"finding-{i}") for i in range(250)]
        body = compose_comment(_result(findings=findings), _record(), live_head_sha=_HEAD)

        assert len(body) < 65536
        assert "_50 further findings omitted; see the full review._" in body

    def test_the_truncation_line_names_no_path(self) -> None:
        findings = [_finding(title=f"finding-{i}") for i in range(250)]
        body = compose_comment(_result(findings=findings), _record(), live_head_sha=_HEAD)

        omission_line = next(
            line for line in body.splitlines() if "further findings omitted" in line
        )
        assert ".md" not in omission_line
        assert "/" not in omission_line


class TestStaleness:
    def test_moved_head_names_both_shas(self) -> None:
        record = _record(head_sha="a" * 40)
        body = compose_comment(_result(), record, live_head_sha="b" * 40)

        assert "**Stale:**" in body
        assert "aaaaaaa" in body
        assert "bbbbbbb" in body

    def test_unmoved_head_has_no_staleness_line(self) -> None:
        record = _record(head_sha=_HEAD)
        body = compose_comment(_result(), record, live_head_sha=_HEAD)

        assert "Stale" not in body
