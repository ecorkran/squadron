"""Normalize raw audit output into typed findings.

Pure — no I/O, no agent, no filesystem access — so the whole normalization
surface is testable on fixtures at zero token cost.

The parser targets the fenced block the skill emits between
``<!-- squadron:findings:begin v1 -->`` and ``<!-- squadron:findings:end -->``,
**not** the human findings table. YAML at a document boundary reuses the
reader pattern ``read_review_frontmatter`` already establishes; no
markdown-pipe-table parser exists in this repo and none is introduced here.

Two honesty guarantees are load-bearing and asserted by test:

*Nothing is dropped silently.* An out-of-vocabulary category normalizes to
``OTHER`` with the original string retained on ``raw_category``, so the
finding survives and a poor vocabulary fit stays visible. A finding whose
*severity* is unrecognizable cannot be retained — severity is load-bearing
for the baseline and guessing it would fabricate data — so it is counted in
``unnormalized_count`` instead.

*Absent and malformed are different failures.* They raise distinct errors
because a model that never emitted the block and one that emitted damaged
YAML call for different responses.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import yaml

from squadron.metrology.errors import AuditBlockMalformedError, AuditBlockMissingError
from squadron.metrology.models import (
    AuditCategory,
    AuditEffort,
    AuditFinding,
    AuditSeverity,
)
from squadron.review.parsers import UNVERIFIED_LOCATION

_logger = logging.getLogger(__name__)

#: Delimiters the skill wraps the findings block in. Matched leniently on
#: the ``begin``/``end`` markers so a version suffix (``v1``, later ``v2``)
#: or incidental whitespace does not break location — the parser must not
#: fail on formatting the semantic content does not depend on.
_BLOCK_PATTERN = re.compile(
    r"<!--\s*squadron:findings:begin.*?-->(?P<body>.*?)<!--\s*squadron:findings:end\s*-->",
    re.DOTALL,
)

#: Strips an optional ```yaml / ``` fence from inside the delimiters. The
#: fence is what the skill emits, but the block is well-defined without it,
#: so its absence is tolerated rather than treated as damage.
_FENCE_PATTERN = re.compile(r"^\s*```[a-zA-Z]*\s*\n(?P<inner>.*?)\n\s*```\s*$", re.DOTALL)

#: Location values that carry no information and normalize to the sentinel.
#: Mirrors the review parser's placeholder handling, lowercased for
#: case-insensitive comparison.
_PLACEHOLDER_LOCATIONS = frozenset({"", "-", "global", "n/a", "none", "various", "multiple"})


def normalize_category(raw: str) -> tuple[AuditCategory, str | None]:
    """Coerce a raw category string into the closed vocabulary.

    An exact (case- and whitespace-insensitive) match returns that member
    with no raw string. Anything else returns ``(OTHER, raw)`` — the finding
    is kept and the original string is retained, never discarded, so a
    rising ``other`` share stays inspectable as evidence about vocabulary
    fit.
    """
    candidate = raw.strip().casefold()
    for member in AuditCategory:
        if member.value == candidate:
            return member, None
    return AuditCategory.OTHER, raw.strip()


def normalize_severity(raw: str) -> AuditSeverity | None:
    """Coerce a raw severity string, or ``None`` if it is unrecognizable.

    Case-insensitive, since the skill's table uses ``Critical`` while the
    enum stores ``critical``. Returns ``None`` rather than a guess: severity
    is load-bearing for the baseline, and inventing one would fabricate the
    measurement instead of admitting a gap.
    """
    candidate = raw.strip().casefold()
    for member in AuditSeverity:
        if member.value == candidate:
            return member
    return None


def normalize_effort(raw: str | None) -> AuditEffort | None:
    """Coerce a raw effort string, or ``None`` if absent/unrecognizable.

    Unlike severity, an unusable effort does not disqualify a finding —
    nothing in the baseline or the floor is computed from it.
    """
    if raw is None:
        return None
    candidate = raw.strip().upper()
    for member in AuditEffort:
        if member.value == candidate:
            return member
    return None


def normalize_location(raw: str | None) -> str:
    """Return the location, or the ``unverified`` sentinel for a placeholder.

    Reuses ``review.parsers.UNVERIFIED_LOCATION`` rather than defining a
    second sentinel. The path is **not** checked against the filesystem —
    a deliberate divergence from the review parser, since the count and
    class of findings is the measurement and a fabricated location does not
    corrupt it.
    """
    if raw is None:
        return UNVERIFIED_LOCATION
    stripped = raw.strip()
    if stripped.casefold() in _PLACEHOLDER_LOCATIONS:
        return UNVERIFIED_LOCATION
    return stripped


def _extract_block_body(raw: str) -> str:
    """Return the YAML text between the delimiters, fence stripped."""
    match = _BLOCK_PATTERN.search(raw)
    if match is None:
        raise AuditBlockMissingError(
            "Audit output contains no squadron findings block. Expected a section "
            "delimited by <!-- squadron:findings:begin v1 --> and "
            "<!-- squadron:findings:end -->. The findings table is not a fallback."
        )
    body = match.group("body")
    fenced = _FENCE_PATTERN.match(body)
    return fenced.group("inner") if fenced is not None else body


def _coerce_str(value: object) -> str | None:
    """Return a stripped string for a scalar YAML value, else ``None``.

    YAML may hand back an int (``id: 1``) or a bool; those are stringified
    rather than rejected, since the field's *identity* survives the coercion.
    Containers are not — a list where a string belongs is damage, not a
    representation difference.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def parse_audit_findings(raw: str) -> tuple[list[AuditFinding], int]:
    """Parse the findings block from raw audit output.

    Returns ``(findings, unnormalized_count)`` where ``unnormalized_count``
    is the number of entries that were present but could not be turned into
    a usable finding. Those are counted, never silently dropped and never
    filled in with a guess.

    Raises:
        AuditBlockMissingError: no findings block is present.
        AuditBlockMalformedError: the block is present but unparseable.
    """
    body = _extract_block_body(raw)

    try:
        loaded: object = yaml.safe_load(body)
    except yaml.YAMLError as exc:
        raise AuditBlockMalformedError(f"Findings block is not valid YAML: {exc}") from exc

    if loaded is None:
        raise AuditBlockMalformedError("Findings block is empty.")
    if not isinstance(loaded, dict):
        raise AuditBlockMalformedError(
            f"Findings block must be a YAML mapping with a 'findings' key, got {type(loaded).__name__}."
        )

    document: dict[str, Any] = loaded  # pyright: ignore[reportUnknownVariableType]
    entries: object = document.get("findings")
    if entries is None:
        raise AuditBlockMalformedError("Findings block has no 'findings' key.")
    if not isinstance(entries, list):
        raise AuditBlockMalformedError(
            f"Findings block 'findings' must be a list, got {type(entries).__name__}."
        )

    findings: list[AuditFinding] = []
    unnormalized = 0
    entry_list: list[object] = entries  # pyright: ignore[reportUnknownVariableType]

    for index, entry in enumerate(entry_list):
        if not isinstance(entry, dict):
            _logger.warning("Audit finding entry %d is not a mapping; counting unnormalized.", index)
            unnormalized += 1
            continue

        item: dict[str, Any] = entry  # pyright: ignore[reportUnknownVariableType]
        severity_raw = _coerce_str(item.get("severity"))
        severity = normalize_severity(severity_raw) if severity_raw is not None else None
        if severity is None:
            # Severity is load-bearing for the baseline: a finding without a
            # usable one is counted, not coerced to a guessed value.
            _logger.warning(
                "Audit finding %r has unrecognized severity %r; counting unnormalized.",
                _coerce_str(item.get("id")) or f"#{index}",
                severity_raw,
            )
            unnormalized += 1
            continue

        finding_id = _coerce_str(item.get("id"))
        if not finding_id:
            _logger.warning("Audit finding entry %d has no id; counting unnormalized.", index)
            unnormalized += 1
            continue

        category, raw_category = normalize_category(_coerce_str(item.get("category")) or "")
        findings.append(
            AuditFinding(
                finding_id=finding_id,
                category=category,
                raw_category=raw_category,
                severity=severity,
                effort=normalize_effort(_coerce_str(item.get("effort"))),
                location=normalize_location(_coerce_str(item.get("location"))),
                summary=_coerce_str(item.get("summary")) or "",
            )
        )

    return findings, unnormalized
