"""Tests for review result models."""

from __future__ import annotations

import json

import pytest

from squadron.review.models import (
    ReviewFinding,
    ReviewResult,
    Severity,
    StructuredFinding,
    Verdict,
)


class TestVerdict:
    """Verdict enum string values."""

    @pytest.mark.parametrize(
        ("member", "expected"),
        [
            (Verdict.PASS, "PASS"),
            (Verdict.CONCERNS, "CONCERNS"),
            (Verdict.FAIL, "FAIL"),
            (Verdict.UNKNOWN, "UNKNOWN"),
        ],
    )
    def test_string_values(self, member: Verdict, expected: str) -> None:
        assert member.value == expected
        assert str(member) == expected


class TestSeverity:
    """Severity enum string values."""

    @pytest.mark.parametrize(
        ("member", "expected"),
        [
            (Severity.PASS, "PASS"),
            (Severity.NOTE, "NOTE"),
            (Severity.CONCERN, "CONCERN"),
            (Severity.FAIL, "FAIL"),
        ],
    )
    def test_string_values(self, member: Severity, expected: str) -> None:
        assert member.value == expected
        assert str(member) == expected

    def test_enum_ordering(self) -> None:
        members = list(Severity)
        assert members == [
            Severity.PASS,
            Severity.NOTE,
            Severity.CONCERN,
            Severity.FAIL,
        ]


class TestReviewFinding:
    """ReviewFinding dataclass."""

    def test_with_file_ref(self) -> None:
        finding = ReviewFinding(
            severity=Severity.FAIL,
            title="Missing validation",
            description="Input not validated at boundary.",
            file_ref="src/app.py:10",
        )
        assert finding.severity == Severity.FAIL
        assert finding.title == "Missing validation"
        assert finding.file_ref == "src/app.py:10"

    def test_without_file_ref(self) -> None:
        finding = ReviewFinding(
            severity=Severity.PASS,
            title="Good structure",
            description="Module layout is clean.",
        )
        assert finding.file_ref is None

    def test_category_and_location_kwargs(self) -> None:
        finding = ReviewFinding(
            severity=Severity.CONCERN,
            title="Naming",
            description="Unclear names.",
            category="naming",
            location="src/foo.py:10",
        )
        assert finding.category == "naming"
        assert finding.location == "src/foo.py:10"

    def test_category_and_location_default_none(self) -> None:
        finding = ReviewFinding(
            severity=Severity.PASS,
            title="OK",
            description="Fine.",
        )
        assert finding.category is None
        assert finding.location is None


class TestStructuredFinding:
    """StructuredFinding dataclass."""

    def test_construction_all_fields(self) -> None:
        sf = StructuredFinding(
            id="F001",
            severity="concern",
            category="error-handling",
            summary="Missing error handling",
            location="src/foo.py:45",
        )
        assert sf.id == "F001"
        assert sf.severity == "concern"
        assert sf.category == "error-handling"
        assert sf.summary == "Missing error handling"
        assert sf.location == "src/foo.py:45"

    def test_location_none(self) -> None:
        sf = StructuredFinding(
            id="F002",
            severity="note",
            category="naming",
            summary="Unclear variable",
        )
        assert sf.location is None


class TestReviewResult:
    """ReviewResult dataclass construction, serialization, and properties."""

    @pytest.fixture
    def result_with_mixed_findings(self) -> ReviewResult:
        return ReviewResult(
            verdict=Verdict.CONCERNS,
            findings=[
                ReviewFinding(
                    severity=Severity.FAIL,
                    title="Critical bug",
                    description="Null pointer.",
                ),
                ReviewFinding(
                    severity=Severity.CONCERN,
                    title="Naming",
                    description="Inconsistent names.",
                ),
                ReviewFinding(
                    severity=Severity.CONCERN,
                    title="Style",
                    description="Line too long.",
                ),
                ReviewFinding(
                    severity=Severity.PASS,
                    title="Tests present",
                    description="Good coverage.",
                ),
            ],
            raw_output="raw text here",
            template_name="code",
            input_files={"cwd": ".", "files": "src/**/*.py"},
        )

    def test_construction(self, result_with_mixed_findings: ReviewResult) -> None:
        r = result_with_mixed_findings
        assert r.verdict == Verdict.CONCERNS
        assert len(r.findings) == 4
        assert r.template_name == "code"
        assert r.timestamp is not None

    def test_has_failures_true(self, result_with_mixed_findings: ReviewResult) -> None:
        assert result_with_mixed_findings.has_failures is True

    def test_has_failures_false(self) -> None:
        r = ReviewResult(
            verdict=Verdict.PASS,
            findings=[
                ReviewFinding(
                    severity=Severity.PASS,
                    title="OK",
                    description="Fine.",
                ),
            ],
            raw_output="",
            template_name="arch",
            input_files={"input": "a.md"},
        )
        assert r.has_failures is False

    def test_concern_count(self, result_with_mixed_findings: ReviewResult) -> None:
        assert result_with_mixed_findings.concern_count == 2

    def test_to_dict_serializable(self, result_with_mixed_findings: ReviewResult) -> None:
        d = result_with_mixed_findings.to_dict()
        # Must be JSON-serializable
        serialized = json.dumps(d)
        assert isinstance(serialized, str)

    def test_to_dict_structure(self, result_with_mixed_findings: ReviewResult) -> None:
        d = result_with_mixed_findings.to_dict()
        assert d["verdict"] == "CONCERNS"
        assert d["template_name"] == "code"
        assert "raw_output" not in d
        assert len(d["findings"]) == 4
        assert d["findings"][0]["severity"] == "FAIL"
        assert d["findings"][0]["title"] == "Critical bug"
        assert d["findings"][0]["file_ref"] is None
        assert "timestamp" in d
        assert isinstance(d["input_files"], dict)

    def test_to_dict_verdict_override_wins_over_raw_verdict(
        self, result_with_mixed_findings: ReviewResult
    ) -> None:
        """Slice 303 F004: judge templates always parse as UNKNOWN (score is
        the source of truth), so the as_json path must honor verdict_override
        the same way format_review_markdown already does for markdown output."""
        d = result_with_mixed_findings.to_dict(verdict_override="PASS")
        assert d["verdict"] == "PASS"

    def test_to_dict_verdict_override_none_falls_back_to_raw_verdict(
        self, result_with_mixed_findings: ReviewResult
    ) -> None:
        d = result_with_mixed_findings.to_dict(verdict_override=None)
        assert d["verdict"] == result_with_mixed_findings.verdict.value

    def test_to_dict_findings_include_category_location(self) -> None:
        r = ReviewResult(
            verdict=Verdict.CONCERNS,
            findings=[
                ReviewFinding(
                    severity=Severity.CONCERN,
                    title="Test",
                    description="Desc.",
                    category="naming",
                    location="src/x.py:1",
                ),
            ],
            raw_output="",
            template_name="code",
            input_files={},
        )
        d = r.to_dict()
        assert d["findings"][0]["category"] == "naming"
        assert d["findings"][0]["location"] == "src/x.py:1"

    def test_to_dict_has_structured_findings(self) -> None:
        r = ReviewResult(
            verdict=Verdict.CONCERNS,
            findings=[
                ReviewFinding(
                    severity=Severity.CONCERN,
                    title="Missing validation",
                    description="No check.",
                    category="validation",
                    location="src/api.py:20",
                ),
                ReviewFinding(
                    severity=Severity.NOTE,
                    title="Naming",
                    description="Unclear.",
                ),
            ],
            raw_output="",
            template_name="code",
            input_files={},
        )
        d = r.to_dict()
        assert "structured_findings" in d
        sf = d["structured_findings"]
        assert len(sf) == 2
        assert sf[0]["id"] == "F001"
        assert sf[0]["severity"] == "concern"
        assert sf[0]["category"] == "validation"
        assert sf[0]["summary"] == "Missing validation"
        assert sf[0]["location"] == "src/api.py:20"
        assert sf[1]["id"] == "F002"
        assert sf[1]["category"] == "uncategorized"
        assert sf[1]["location"] is None

    def test_to_dict_empty_structured_findings(self) -> None:
        r = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="",
            template_name="arch",
            input_files={},
        )
        d = r.to_dict()
        assert d["structured_findings"] == []

    def test_empty_findings(self) -> None:
        r = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="",
            template_name="arch",
            input_files={},
        )
        assert r.has_failures is False
        assert r.concern_count == 0
        assert r.to_dict()["findings"] == []


class TestReviewResultScoreFields:
    """Numeric scoring foundation (slice 300): score/criteria/provenance."""

    def _base(self, **overrides: object) -> ReviewResult:
        kwargs: dict[str, object] = dict(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="",
            template_name="t",
            input_files={},
        )
        kwargs.update(overrides)
        return ReviewResult(**kwargs)  # type: ignore[arg-type]

    def test_defaults_none(self) -> None:
        r = self._base()
        assert r.score is None
        assert r.criteria is None
        assert r.provenance is None

    def test_round_trips_explicit_values(self) -> None:
        r = self._base(score=87.5, criteria={"alignment": 90.0}, provenance="judge")
        assert r.score == 87.5
        assert r.criteria == {"alignment": 90.0}
        assert r.provenance == "judge"

    def test_to_dict_includes_keys_when_set(self) -> None:
        r = self._base(score=87.5, criteria={"alignment": 90.0}, provenance="judge")
        d = r.to_dict()
        assert {"score", "criteria", "provenance"} <= d.keys()
        assert d["score"] == 87.5
        assert d["criteria"] == {"alignment": 90.0}
        assert d["provenance"] == "judge"

    def test_to_dict_keys_none_when_unset(self) -> None:
        d = self._base().to_dict()
        assert d["score"] is None
        assert d["criteria"] is None
        assert d["provenance"] is None

    def test_existing_shape_keys_unchanged(self) -> None:
        """An existing-shape result still serializes its prior keys."""
        d = self._base().to_dict()
        for key in (
            "verdict",
            "findings",
            "structured_findings",
            "template_name",
            "input_files",
            "timestamp",
            "model",
        ):
            assert key in d


class TestStructuredFindingsProperty:
    """ReviewResult.structured_findings computed property."""

    @pytest.fixture
    def result_with_findings(self) -> ReviewResult:
        return ReviewResult(
            verdict=Verdict.CONCERNS,
            findings=[
                ReviewFinding(
                    severity=Severity.CONCERN,
                    title="Missing error handling",
                    description="No try/except.",
                    file_ref="src/app.py:10",
                    category="error-handling",
                    location="src/app.py:10",
                ),
                ReviewFinding(
                    severity=Severity.NOTE,
                    title="Unclear variable name",
                    description="Variable x is unclear.",
                    file_ref="src/utils.py:5",
                ),
                ReviewFinding(
                    severity=Severity.FAIL,
                    title="SQL injection",
                    description="Unparameterized query.",
                    category="security",
                ),
            ],
            raw_output="",
            template_name="code",
            input_files={},
        )

    def test_returns_correct_count(self, result_with_findings: ReviewResult) -> None:
        assert len(result_with_findings.structured_findings) == 3

    def test_auto_assigns_ids(self, result_with_findings: ReviewResult) -> None:
        ids = [sf.id for sf in result_with_findings.structured_findings]
        assert ids == ["F001", "F002", "F003"]

    def test_maps_severity_to_lowercase(self, result_with_findings: ReviewResult) -> None:
        severities = [sf.severity for sf in result_with_findings.structured_findings]
        assert severities == ["concern", "note", "fail"]

    def test_defaults_category_to_uncategorized(self, result_with_findings: ReviewResult) -> None:
        sf = result_with_findings.structured_findings
        assert sf[0].category == "error-handling"
        assert sf[1].category == "uncategorized"
        assert sf[2].category == "security"

    def test_uses_location_over_file_ref(self, result_with_findings: ReviewResult) -> None:
        sf = result_with_findings.structured_findings[0]
        assert sf.location == "src/app.py:10"

    def test_falls_back_to_file_ref(self, result_with_findings: ReviewResult) -> None:
        sf = result_with_findings.structured_findings[1]
        assert sf.location == "src/utils.py:5"

    def test_location_none_when_both_absent(self, result_with_findings: ReviewResult) -> None:
        sf = result_with_findings.structured_findings[2]
        assert sf.location is None

    def test_empty_findings(self) -> None:
        r = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="",
            template_name="arch",
            input_files={},
        )
        assert r.structured_findings == []


# ---------------------------------------------------------------------------
# Tool-use telemetry fields (slice 265)
# ---------------------------------------------------------------------------


def _bare_result(**overrides: object) -> ReviewResult:
    defaults: dict[str, object] = {
        "verdict": Verdict.PASS,
        "findings": [],
        "raw_output": "",
        "template_name": "code",
        "input_files": {},
    }
    defaults.update(overrides)
    return ReviewResult(**defaults)  # type: ignore[arg-type]


def test_tool_telemetry_fields_default_to_none() -> None:
    result = _bare_result()

    assert result.tools_given is None
    assert result.tool_calls_made is None


def test_to_dict_always_includes_tool_telemetry() -> None:
    """The new keys join the always-included group, not the verbosity-gated one."""
    payload = _bare_result().to_dict()

    assert payload["tools_given"] is None
    assert payload["tool_calls_made"] is None
    # The gated prompt-capture fields stay excluded.
    assert "system_prompt" not in payload


def test_to_dict_carries_populated_tool_telemetry() -> None:
    payload = _bare_result(tools_given=["read_file", "grep"], tool_calls_made=3).to_dict()

    assert payload["tools_given"] == ["read_file", "grep"]
    assert payload["tool_calls_made"] == 3


def test_to_dict_distinguishes_zero_calls_from_no_tools() -> None:
    """Design D5: "offered three tools, called none" must not look like "never had tools"."""
    offered = _bare_result(tools_given=["read_file"], tool_calls_made=0).to_dict()
    never = _bare_result().to_dict()

    assert offered["tools_given"] == ["read_file"]
    assert offered["tool_calls_made"] == 0
    assert never["tools_given"] is None
    assert never["tool_calls_made"] is None
