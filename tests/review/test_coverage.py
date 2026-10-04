"""Tests for impose_diff_coverage (slice 927 D4, D6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.review.coverage import (
    COVERAGE_CATEGORY,
    impose_diff_coverage,
    impose_output_coverage,
)
from squadron.review.models import (
    DiffInjection,
    ReviewFinding,
    ReviewResult,
    Severity,
    Verdict,
    VerdictSource,
)
from squadron.review.persistence import SliceInfo, format_review_markdown, save_review_result


def _result(
    *,
    verdict: Verdict,
    diff_injection: DiffInjection | None,
    tool_calls_made: int | None,
    failed_tool_calls: int | None,
    findings: list[ReviewFinding] | None = None,
    **overrides: object,
) -> ReviewResult:
    return ReviewResult(
        verdict=verdict,
        findings=findings or [],
        raw_output="",
        template_name="code",
        input_files={},
        diff_injection=diff_injection,
        tool_calls_made=tool_calls_made,
        failed_tool_calls=failed_tool_calls,
        **overrides,  # type: ignore[arg-type]
    )


_TRUNCATED = DiffInjection(total_chars=1000, injected_chars=400)
_NOT_TRUNCATED = DiffInjection(total_chars=1000, injected_chars=1000)


@pytest.mark.parametrize("verdict", [Verdict.PASS, Verdict.CONCERNS, Verdict.FAIL, Verdict.UNKNOWN])
@pytest.mark.parametrize(
    ("tool_calls_made", "failed_tool_calls"),
    [(None, None), (0, None), (3, 3), (2, 0)],
)
@pytest.mark.parametrize("truncated", [True, False])
def test_impose_diff_coverage_matrix(
    verdict: Verdict,
    tool_calls_made: int | None,
    failed_tool_calls: int | None,
    truncated: bool,
) -> None:
    diff_injection = _TRUNCATED if truncated else _NOT_TRUNCATED
    original_finding = ReviewFinding(severity=Severity.NOTE, title="Existing", description="d")
    result = _result(
        verdict=verdict,
        diff_injection=diff_injection,
        tool_calls_made=tool_calls_made,
        failed_tool_calls=failed_tool_calls,
        findings=[original_finding],
    )

    successful_calls = (tool_calls_made or 0) - (failed_tool_calls or 0)
    should_cap = verdict is Verdict.PASS and truncated and successful_calls <= 0

    impose_diff_coverage(result)

    if should_cap:
        assert result.verdict is Verdict.CONCERNS
        assert result.verdict_source is VerdictSource.IMPOSED
        assert len(result.findings) == 2
        assert result.findings[0].category == COVERAGE_CATEGORY
        assert result.findings[1] is original_finding
        assert "verdict was PASS" in result.findings[0].description
        assert "1000" in result.findings[0].description
        assert "400" in result.findings[0].description
        assert "600" in result.findings[0].description
    else:
        assert result.verdict is verdict
        assert result.verdict_source is None
        assert result.findings == [original_finding]


def test_impose_diff_coverage_no_diff_injection_is_noop() -> None:
    result = _result(
        verdict=Verdict.PASS,
        diff_injection=None,
        tool_calls_made=None,
        failed_tool_calls=None,
    )
    impose_diff_coverage(result)
    assert result.verdict is Verdict.PASS
    assert result.verdict_source is None
    assert result.findings == []


def test_impose_diff_coverage_finding_has_no_location() -> None:
    result = _result(
        verdict=Verdict.PASS,
        diff_injection=_TRUNCATED,
        tool_calls_made=None,
        failed_tool_calls=None,
    )
    impose_diff_coverage(result)
    assert result.findings[0].location is None
    assert result.findings[0].location_verified is None


def test_impose_diff_coverage_does_not_hide_derived_findings() -> None:
    """D6: capping a derived PASS renders both the synthetic and parsed findings,
    with no 'Findings Not Parsed' notice."""
    parsed_finding = ReviewFinding(
        severity=Severity.PASS, title="Looks fine", description="Clean.", category="style"
    )
    result = _result(
        verdict=Verdict.PASS,
        diff_injection=_TRUNCATED,
        tool_calls_made=None,
        failed_tool_calls=None,
        findings=[parsed_finding],
        fallback_used=True,
        verdict_source=VerdictSource.DERIVED,
    )

    impose_diff_coverage(result)

    markdown = format_review_markdown(result, "code")
    assert COVERAGE_CATEGORY in markdown or "Diff truncated" in markdown
    assert "Looks fine" in markdown
    assert "Findings Not Parsed" not in markdown


# ---------------------------------------------------------------------------
# impose_output_coverage (slice 196 D12, #152)
# ---------------------------------------------------------------------------


def _budget_result(verdict: Verdict, *, exhausted: bool, **overrides: object) -> ReviewResult:
    return _result(
        verdict=verdict,
        diff_injection=None,
        tool_calls_made=overrides.pop("tool_calls_made", None),  # type: ignore[arg-type]
        failed_tool_calls=None,
        findings=[ReviewFinding(severity=Severity.NOTE, title="Existing", description="d")],
        output_budget_exhausted=exhausted,
        **overrides,
    )


def test_exhausted_pass_is_imposed_to_concerns_with_finding_first() -> None:
    result = _budget_result(Verdict.PASS, exhausted=True)

    impose_output_coverage(result)

    assert result.verdict is Verdict.CONCERNS
    assert result.verdict_source is VerdictSource.IMPOSED
    assert result.findings[0].category == COVERAGE_CATEGORY
    assert result.findings[0].severity is Severity.CONCERN
    assert "findings after the cutoff are lost" in result.findings[0].description
    assert result.findings[1].title == "Existing"


@pytest.mark.parametrize(
    ("verdict", "exhausted"),
    [
        (Verdict.PASS, False),
        (Verdict.CONCERNS, True),
        (Verdict.FAIL, True),
        (Verdict.UNKNOWN, True),
    ],
)
def test_other_cases_are_unchanged(verdict: Verdict, exhausted: bool) -> None:
    result = _budget_result(verdict, exhausted=exhausted)

    impose_output_coverage(result)

    assert result.verdict is verdict
    assert result.verdict_source is None
    assert [f.title for f in result.findings] == ["Existing"]


@pytest.mark.parametrize("tool_calls_made", [None, 0, 12])
def test_tool_call_count_is_ignored(tool_calls_made: int | None) -> None:
    """Truncation loses findings however much the model read."""
    result = _budget_result(Verdict.PASS, exhausted=True, tool_calls_made=tool_calls_made)

    impose_output_coverage(result)

    assert result.verdict is Verdict.CONCERNS


def test_saved_artifact_frontmatter_records_the_imposed_verdict(tmp_path: Path) -> None:
    result = _budget_result(Verdict.PASS, exhausted=True)
    impose_output_coverage(result)

    slice_info = SliceInfo(
        index=196,
        name="coverage",
        slice_name="coverage",
        design_file=None,
        task_files=[],
        arch_file="",
        project="squadron",
    )
    saved = save_review_result(result, "code", slice_info=slice_info, reviews_dir=tmp_path)

    frontmatter = saved.read_text().split("---")[1]
    assert "verdict: CONCERNS" in frontmatter
    assert "verdictSource: imposed" in frontmatter
