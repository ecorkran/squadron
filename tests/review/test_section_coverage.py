"""A document review must account for every section of the document (#382)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from squadron.review.models import ReviewResult, Verdict, VerdictSource
from squadron.review.section_coverage import (
    SECTION_COVERAGE_TITLE,
    check_section_coverage,
    coverage_entries,
    impose_section_coverage,
    reviewed_headings,
    section_coverage_lines,
)

_DOCS = Path(__file__).parents[2] / "project-documents" / "user"
REAL_TASKS = _DOCS / "tasks" / "434-tasks.recipe-reviews-in-pipelines.md"
REAL_SLICE = _DOCS / "slices" / "434-slice.recipe-reviews-in-pipelines.md"

DOCUMENT = """\
# Tasks

## Context Summary
text

## 1. The `wire` package (D3; effort 2)
- [ ] 1.1 thing

```markdown
## Not a heading, it is inside a fence
```

## 13. The mode switch, `join` and `leave`
### Task 4: Recipe search by name (D1)
### Notes
"""
HEADINGS = [
    "Context Summary",
    "1. The `wire` package (D3; effort 2)",
    "13. The mode switch, `join` and `leave`",
    "Task 4: Recipe search by name (D1)",
    "Notes",
]


def _review(coverage: str, verdict: str = "PASS") -> str:
    return f"## Summary\n{verdict}\n\n## Findings\n\n### [PASS] Fine\nlocation: a.md\nok\n\n{coverage}"


FULL = """## Coverage
- Context Summary: read against the design
- 1. The wire package: checked imports in src/wire
- Section 13: walked join then leave
- **Task 4**: recipe search signature checked
- Notes: nothing to check
"""


def test_headings_are_levels_two_and_three_outside_fences() -> None:
    assert reviewed_headings(DOCUMENT) == HEADINGS


def test_a_review_that_lists_every_heading_is_complete() -> None:
    coverage = check_section_coverage(DOCUMENT, _review(FULL))
    assert coverage.complete and coverage.sections == 5 and coverage.missing == ()


def test_a_numbered_heading_is_not_covered_by_another_number() -> None:
    partial = FULL.replace("- Section 13: walked join then leave\n", "- 13.3b: join branches\n")
    coverage = check_section_coverage(DOCUMENT, _review(partial))
    assert coverage.missing == ("13. The mode switch, `join` and `leave`",)


def test_a_review_with_no_coverage_section_covers_nothing() -> None:
    coverage = check_section_coverage(DOCUMENT, _review(""))
    assert coverage.reported is False and coverage.missing == tuple(HEADINGS)
    assert coverage_entries(_review("")) is None


def test_the_coverage_section_ends_at_the_next_section() -> None:
    entries = coverage_entries(_review(FULL + "\n## Notes for the PM\n- Task 99: not coverage\n"))
    assert entries is not None and len(entries) == 5


def _result(raw: str, verdict: Verdict = Verdict.PASS) -> ReviewResult:
    return ReviewResult(
        verdict=verdict,
        findings=[],
        raw_output=raw,
        template_name="tasks",
        input_files={},
        verdict_source=VerdictSource.STATED,
    )


def test_a_pass_that_skips_a_section_becomes_concerns_and_names_it() -> None:
    result = _result(_review(FULL.replace("- Notes: nothing to check\n", "")))
    impose_section_coverage(result, DOCUMENT)
    assert result.verdict is Verdict.CONCERNS and result.verdict_source is VerdictSource.IMPOSED
    assert result.findings[0].title == SECTION_COVERAGE_TITLE
    assert "Notes" in result.findings[0].description
    assert result.section_coverage is not None and result.section_coverage.missing == ("Notes",)


def test_a_complete_pass_is_left_alone() -> None:
    result = _result(_review(FULL))
    impose_section_coverage(result, DOCUMENT)
    assert result.verdict is Verdict.PASS and result.findings == []
    assert result.section_coverage is not None and result.section_coverage.complete


def test_a_failing_review_keeps_its_verdict_but_records_the_gap() -> None:
    result = _result(_review("", "FAIL"), Verdict.FAIL)
    impose_section_coverage(result, DOCUMENT)
    assert result.verdict is Verdict.FAIL and result.findings == []
    assert result.section_coverage is not None and not result.section_coverage.complete


def test_frontmatter_lines_round_trip() -> None:
    coverage = check_section_coverage(
        DOCUMENT, _review(FULL.replace("- Notes: nothing to check\n", ""))
    )
    parsed = yaml.safe_load("\n".join(section_coverage_lines(coverage)))
    assert parsed == {"sectionsInDocument": 5, "sectionsCovered": 4, "sectionsNotCovered": ["Notes"]}
    assert section_coverage_lines(None) == []


@pytest.mark.parametrize("path", [REAL_TASKS, REAL_SLICE])
def test_real_documents_are_covered_by_a_line_per_heading(path: Path) -> None:
    """The format production consumes: a real task file and slice design from this repo."""
    document = path.read_text(encoding="utf-8")
    headings = reviewed_headings(document)
    assert len(headings) > 10
    listing = "## Coverage\n" + "\n".join(f"- {heading}: checked" for heading in headings)
    assert check_section_coverage(document, _review(listing)).complete
    dropped = "## Coverage\n" + "\n".join(f"- {heading}: checked" for heading in headings[:-1])
    assert check_section_coverage(document, _review(dropped)).missing == (headings[-1],)
