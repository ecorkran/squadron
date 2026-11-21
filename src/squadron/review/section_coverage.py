"""Did a document review cover every section of the document? (#382)

Document templates ask the reviewer for a ``## Coverage`` section: one line per heading
of the reviewed document. This module lists the document's headings, reads that section
back, and names the headings no line covers. A review with uncovered headings cannot
PASS: the model said nothing about part of the document, so its PASS covers a sample.

Matching is lenient. A heading with a leading number or task id (``## 13. The mode
switch``, ``### Task 4: Recipe search``) is covered by any line that starts with that id;
any other heading is covered by a line that contains the start of its text.
"""

from __future__ import annotations

import json
import re

from squadron.review.models import (
    ReviewFinding,
    ReviewResult,
    SectionCoverage,
    Severity,
    Verdict,
    VerdictSource,
)

__all__ = [
    "SECTION_COVERAGE_TITLE",
    "SectionCoverage",
    "check_section_coverage",
    "coverage_entries",
    "impose_section_coverage",
    "reviewed_headings",
    "section_coverage_lines",
]

SECTION_COVERAGE_TITLE = "Review did not cover every section of the document"
_COVERAGE_CATEGORY = "coverage"
#: Heading levels that count as sections of a reviewed document.
_SECTION_LEVELS = (2, 3)
#: How much of an unnumbered heading a coverage line must contain.
_HEADING_MATCH_CHARS = 30

_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_FENCE_RE = re.compile(r"^[ \t]*(```|~~~)")
_COVERAGE_HEADING_RE = re.compile(r"^##[ \t]+Coverage\b[^\n]*$", re.IGNORECASE | re.MULTILINE)
_NEXT_SECTION_RE = re.compile(r"^##[ \t]+", re.MULTILINE)
_BULLET_RE = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+")
_MARKUP_RE = re.compile(r"[`*_]")
#: ``Task 4``, ``T12``, ``13.``, ``6.3`` at the start of a heading.
_ID_RE = re.compile(
    r"^(?:section[ \t]+)?(?P<id>(?:task|t)[ \t]*\d+[a-z]?|\d+(?:\.\d+)*[a-z]?)(?![\w])",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return " ".join(_MARKUP_RE.sub("", text).lower().split())


def reviewed_headings(document: str) -> list[str]:
    """The ``##`` and ``###`` headings of *document*, in order, outside code fences."""
    headings: list[str] = []
    fenced = False
    for line in document.splitlines():
        if _FENCE_RE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        match = _HEADING_RE.match(line)
        if match and len(match.group(1)) in _SECTION_LEVELS:
            headings.append(match.group(2))
    return headings


def coverage_entries(raw_output: str) -> list[str] | None:
    """The lines of the review's ``## Coverage`` section; None when it has no such section."""
    heading = _COVERAGE_HEADING_RE.search(raw_output)
    if heading is None:
        return None
    rest = raw_output[heading.end() :]
    end = _NEXT_SECTION_RE.search(rest)
    body = rest[: end.start()] if end else rest
    return [_BULLET_RE.sub("", line).strip() for line in body.splitlines() if line.strip()]


def _covered(heading: str, entries: list[str]) -> bool:
    normalized = _normalize(heading)
    heading_id = _ID_RE.match(normalized)
    if heading_id is not None:
        wanted = heading_id.group("id")
        return any(
            (found := _ID_RE.match(entry)) is not None and found.group("id") == wanted
            for entry in entries
        )
    return any(normalized[:_HEADING_MATCH_CHARS] in entry for entry in entries)


def check_section_coverage(document: str, raw_output: str) -> SectionCoverage:
    """Which headings of *document* the review in *raw_output* did not cover."""
    headings = reviewed_headings(document)
    raw_entries = coverage_entries(raw_output)
    if raw_entries is None:
        return SectionCoverage(len(headings), tuple(headings), reported=False)
    entries = [_normalize(entry) for entry in raw_entries]
    missing = tuple(heading for heading in headings if not _covered(heading, entries))
    return SectionCoverage(len(headings), missing, reported=True)


def impose_section_coverage(result: ReviewResult, document: str) -> None:
    """Record section coverage on *result*; a PASS with uncovered sections becomes CONCERNS.

    Only a PASS is changed: a CONCERNS or FAIL review already sends the document back, and
    the next round is checked the same way. The synthetic finding names the sections.
    """
    coverage = check_section_coverage(document, result.raw_output)
    result.section_coverage = coverage
    if coverage.complete or result.verdict is not Verdict.PASS:
        return
    what = (
        "The review has no Coverage section, so none of the document's "
        f"{coverage.sections} sections is accounted for."
        if not coverage.reported
        else f"{len(coverage.missing)} of {coverage.sections} sections are not in the review's "
        "Coverage section: " + "; ".join(coverage.missing) + "."
    )
    finding = ReviewFinding(
        severity=Severity.CONCERN,
        title=SECTION_COVERAGE_TITLE,
        description=what + " A PASS that leaves sections out covers a sample of the document.",
        category=_COVERAGE_CATEGORY,
        location=None,
    )
    result.findings = [finding, *result.findings]
    result.verdict = Verdict.CONCERNS
    result.verdict_source = VerdictSource.IMPOSED


def section_coverage_lines(coverage: SectionCoverage | None) -> list[str]:
    """Frontmatter lines for *coverage*; empty when the review type does not check it."""
    if coverage is None:
        return []
    lines = [
        f"sectionsInDocument: {coverage.sections}",
        f"sectionsCovered: {coverage.sections - len(coverage.missing)}",
    ]
    if coverage.missing:
        lines.append("sectionsNotCovered:")
        lines.extend(f"  - {_yaml_string(heading)}" for heading in coverage.missing)
    return lines


def _yaml_string(text: str) -> str:
    # A JSON string is a valid YAML double-quoted scalar, escapes included.
    return json.dumps(text)
