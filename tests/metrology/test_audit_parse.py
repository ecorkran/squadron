"""Audit parsing: vocabulary coercion, retention, and boundary failures.

The fixtures here are whole audit files — frontmatter, prose, the human
findings table, *then* the fenced block — not bare blocks. That is the
project's parser-fixture rule: a parser tested only on the shape it wishes
it received provides false confidence, since production input is the full
document the skill writes.

The assertions that matter most are the honesty guarantees. An
out-of-vocabulary category must be *retained*, and an unusable severity must
be *counted*. Both are places where a parser could quietly improve its own
numbers by discarding inconvenient input.
"""

from __future__ import annotations

import pytest

from squadron.metrology.audit_parse import (
    normalize_category,
    normalize_severity,
    parse_audit_findings,
)
from squadron.metrology.errors import AuditBlockMalformedError, AuditBlockMissingError
from squadron.metrology.models import AuditCategory, AuditEffort, AuditSeverity
from squadron.review.parsers import UNVERIFIED_LOCATION

_PROSE_PREAMBLE = """---
docType: analysis
project: example
dateCreated: 20260726
---

# Tech Debt Audit — example

## Executive summary

- 1 Critical finding, 1 High, 1 Medium
- Largest debt concentration: `src/payments/*`

## Architectural mental model

The system is a layered service with a thin HTTP surface over a domain core.

## Findings

| ID | Category | File:Line | Severity | Effort | Description | Recommendation |
|----|----------|-----------|----------|--------|-------------|----------------|
| F001 | architectural-decay | src/payments/processor.py:1240 | Critical | L | God class | Extract retry |
| F002 | test-debt | src/payments/refund.py:12 | High | M | No tests on refunds | Add cases |

## Things that look bad but are actually fine

- The nested callbacks in `webhooks.py` preserve ordering guarantees.

## Open questions

- Is `src/experiments/` intentionally untested?
"""


def _audit_file(block_body: str) -> str:
    """A realistic audit file: prose, table, then the fenced block."""
    return (
        f"{_PROSE_PREAMBLE}\n"
        "<!-- squadron:findings:begin v1 -->\n"
        "```yaml\n"
        f"{block_body}"
        "```\n"
        "<!-- squadron:findings:end -->\n"
    )


_WELL_FORMED = _audit_file(
    """findings:
  - id: F001
    category: architectural-decay
    location: src/payments/processor.py:1240
    severity: Critical
    effort: L
    summary: 1400-line god class handling routing, validation, retry, and reconciliation
  - id: F002
    category: test-debt
    location: src/payments/refund.py:12
    severity: High
    effort: M
    summary: Refund path has no test coverage
  - id: F003
    category: documentation-drift
    location: README.md:40
    severity: Low
    effort: S
    summary: README describes a queue that no longer exists
"""
)


def test_well_formed_block_parses_every_field() -> None:
    findings, unnormalized = parse_audit_findings(_WELL_FORMED)

    assert unnormalized == 0
    assert [f.finding_id for f in findings] == ["F001", "F002", "F003"]

    first = findings[0]
    assert first.category is AuditCategory.ARCHITECTURAL_DECAY
    assert first.raw_category is None
    assert first.severity is AuditSeverity.CRITICAL
    assert first.effort is AuditEffort.L
    assert first.location == "src/payments/processor.py:1240"
    assert first.summary.startswith("1400-line god class")

    assert findings[1].severity is AuditSeverity.HIGH
    assert findings[2].category is AuditCategory.DOCUMENTATION_DRIFT


def test_out_of_vocabulary_category_is_retained_as_other() -> None:
    """The success criterion: unnormalizable categories are kept, not dropped.

    The finding stays in the result with ``OTHER`` and its original string on
    ``raw_category``, so a poor vocabulary fit surfaces as a rising ``other``
    share rather than as findings quietly vanishing from the baseline.
    """
    raw = _audit_file(
        """findings:
  - id: F001
    category: prompt-injection-surface
    location: src/agent/tools.py:88
    severity: High
    effort: M
    summary: Tool descriptions are interpolated from user-controlled text
"""
    )
    findings, unnormalized = parse_audit_findings(raw)

    assert unnormalized == 0
    assert len(findings) == 1, "an out-of-vocabulary finding must be retained, not dropped"
    assert findings[0].category is AuditCategory.OTHER
    assert findings[0].raw_category == "prompt-injection-surface"
    assert findings[0].severity is AuditSeverity.HIGH


def test_unrecognized_severity_is_counted_not_guessed() -> None:
    """A finding without usable severity is excluded but counted.

    Severity drives the baseline, so coercing an unknown value to a default
    would fabricate the measurement. The finding is surfaced through
    ``unnormalized_count`` instead.
    """
    raw = _audit_file(
        """findings:
  - id: F001
    category: test-debt
    location: src/x.py:1
    severity: Catastrophic
    effort: M
    summary: Unknown severity vocabulary
  - id: F002
    category: test-debt
    location: src/y.py:2
    severity: Low
    effort: S
    summary: Usable finding
"""
    )
    findings, unnormalized = parse_audit_findings(raw)

    assert unnormalized == 1
    assert [f.finding_id for f in findings] == ["F002"]
    # F001 is absent entirely — not present under a defaulted severity.
    assert "F001" not in {f.finding_id for f in findings}


def test_absent_block_raises_missing() -> None:
    """A findings table alone is not a fallback in this slice."""
    with pytest.raises(AuditBlockMissingError):
        parse_audit_findings(_PROSE_PREAMBLE)


def test_table_present_but_block_absent_still_raises_missing() -> None:
    """Explicitly: the human table must not be silently parsed instead.

    Table fallback is recorded as Future Work. Until it exists, a missing
    block is a failed run, not a run with fewer findings.
    """
    assert "| F001 |" in _PROSE_PREAMBLE
    with pytest.raises(AuditBlockMissingError):
        parse_audit_findings(_PROSE_PREAMBLE)


def test_malformed_yaml_raises_malformed_not_missing() -> None:
    """Damaged YAML inside the delimiters is a distinct failure from absence."""
    raw = _audit_file("findings:\n  - id: F001\n   category: [unclosed\n")
    with pytest.raises(AuditBlockMalformedError):
        parse_audit_findings(raw)


def test_block_without_findings_key_raises_malformed() -> None:
    raw = _audit_file("summary: nothing useful here\n")
    with pytest.raises(AuditBlockMalformedError):
        parse_audit_findings(raw)


def test_findings_not_a_list_raises_malformed() -> None:
    raw = _audit_file("findings: just-a-string\n")
    with pytest.raises(AuditBlockMalformedError):
        parse_audit_findings(raw)


def test_empty_block_raises_malformed() -> None:
    raw = _audit_file("")
    with pytest.raises(AuditBlockMalformedError):
        parse_audit_findings(raw)


def test_empty_findings_list_parses_as_zero_findings() -> None:
    """An explicit empty list is a real result, not damage.

    Distinct from an empty block: the model said "no findings", which is
    parseable and true, so it must not raise.
    """
    findings, unnormalized = parse_audit_findings(_audit_file("findings: []\n"))
    assert findings == []
    assert unnormalized == 0


@pytest.mark.parametrize("placeholder", ["n/a", "N/A", "-", "global", "none", ""])
def test_placeholder_location_normalizes_to_sentinel(placeholder: str) -> None:
    """Placeholders become the shared ``unverified`` sentinel, not None."""
    raw = _audit_file(
        f"""findings:
  - id: F001
    category: test-debt
    location: "{placeholder}"
    severity: Low
    effort: S
    summary: Placeholder location
"""
    )
    findings, _ = parse_audit_findings(raw)
    assert findings[0].location == UNVERIFIED_LOCATION


def test_missing_location_key_normalizes_to_sentinel() -> None:
    raw = _audit_file(
        """findings:
  - id: F001
    category: test-debt
    severity: Low
    effort: S
    summary: No location key at all
"""
    )
    findings, _ = parse_audit_findings(raw)
    assert findings[0].location == UNVERIFIED_LOCATION


def test_location_is_not_checked_against_the_filesystem() -> None:
    """Deliberate divergence from the review parser's path-existence check.

    The count and class of findings is the measurement; a fabricated
    location does not corrupt it, and re-verifying every location across
    N runs x M projects is I/O the measurement does not need.
    """
    raw = _audit_file(
        """findings:
  - id: F001
    category: test-debt
    location: src/this/path/definitely/does/not/exist.py:9999
    severity: Low
    effort: S
    summary: Nonexistent path is retained verbatim
"""
    )
    findings, unnormalized = parse_audit_findings(raw)
    assert unnormalized == 0
    assert findings[0].location == "src/this/path/definitely/does/not/exist.py:9999"


def test_block_without_yaml_fence_still_parses() -> None:
    """The fence is expected but not required — lenient on formatting."""
    raw = (
        f"{_PROSE_PREAMBLE}\n"
        "<!-- squadron:findings:begin v1 -->\n"
        "findings:\n"
        "  - id: F001\n"
        "    category: test-debt\n"
        "    location: src/x.py:1\n"
        "    severity: Low\n"
        "    effort: S\n"
        "    summary: No fence\n"
        "<!-- squadron:findings:end -->\n"
    )
    findings, _ = parse_audit_findings(raw)
    assert findings[0].finding_id == "F001"


def test_missing_effort_is_optional() -> None:
    raw = _audit_file(
        """findings:
  - id: F001
    category: test-debt
    location: src/x.py:1
    severity: Low
    summary: No effort field
"""
    )
    findings, _ = parse_audit_findings(raw)
    assert findings[0].effort is None


def test_entry_without_id_is_counted_unnormalized() -> None:
    raw = _audit_file(
        """findings:
  - category: test-debt
    location: src/x.py:1
    severity: Low
    effort: S
    summary: No id
"""
    )
    findings, unnormalized = parse_audit_findings(raw)
    assert findings == []
    assert unnormalized == 1


def test_normalize_category_is_case_and_whitespace_insensitive() -> None:
    assert normalize_category("  Test-Debt  ") == (AuditCategory.TEST_DEBT, None)


def test_normalize_category_retains_raw_for_unknown() -> None:
    category, raw = normalize_category("  Weird Thing  ")
    assert category is AuditCategory.OTHER
    assert raw == "Weird Thing"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Critical", AuditSeverity.CRITICAL),
        ("critical", AuditSeverity.CRITICAL),
        ("  HIGH  ", AuditSeverity.HIGH),
        ("Medium", AuditSeverity.MEDIUM),
        ("low", AuditSeverity.LOW),
    ],
)
def test_normalize_severity_accepts_the_skills_casing(raw: str, expected: AuditSeverity) -> None:
    """The skill's table says ``Critical``; the enum stores ``critical``."""
    assert normalize_severity(raw) is expected


def test_normalize_severity_returns_none_for_unknown() -> None:
    assert normalize_severity("Catastrophic") is None
