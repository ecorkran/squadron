"""Parse agent markdown output into structured ReviewResult."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from squadron.review.models import (
    ReviewFinding,
    ReviewResult,
    Severity,
    Verdict,
)

logger = logging.getLogger(__name__)

# Sentinel for findings whose location cannot be determined or
# is reported as a non-specific placeholder by the model.
UNVERIFIED_LOCATION = "unverified"

# Values from model output that should be normalized to UNVERIFIED_LOCATION.
# Stored lowercased for case-insensitive comparison.
_PLACEHOLDER_LOCATIONS: frozenset[str] = frozenset({"", "-", "global", "n/a", "none"})

# Captures the path portion of a location value: everything up to (but not
# including) the first ':', '#', or end of string. Used by diff-membership
# and path-existence checks. Returns None for UNVERIFIED_LOCATION callers
# (handled by guard at the call site) and for any value that does not
# look like a path (e.g. starts with '<' from leftover prompt examples).
_LOCATION_PATH_RE = re.compile(r"^([^:#<>\s][^:#]*)")

_VERDICT_MAP: dict[str, Verdict] = {
    "PASS": Verdict.PASS,
    "CONCERNS": Verdict.CONCERNS,
    "FAIL": Verdict.FAIL,
}

_SEVERITY_MAP: dict[str, Severity] = {
    "PASS": Severity.PASS,
    "NOTE": Severity.NOTE,
    "CONCERN": Severity.CONCERN,
    "FAIL": Severity.FAIL,
}

# Matches "## Summary" section followed by a verdict keyword (possibly bold)
_SUMMARY_RE = re.compile(
    r"##\s+Summary\s*\n+\s*(?:.*?\b)?(?:\*{0,2})(PASS|CONCERNS|FAIL)(?:\*{0,2})\b",
    re.IGNORECASE,
)

# Matches finding blocks in five formats:
#   ### [SEVERITY] Title          (standard bracketed heading)
#   ### SEVERITY Title            (standard unbracketed heading)
#   ### SEVERITY: Title           (colon separator, no brackets)
#   **[SEVERITY]** Title          (bold brackets, no heading marker)
#   - [SEVERITY] Title            (bullet-point finding)
_FINDING_RE = re.compile(
    r"(?:"
    # Heading formats: ### [SEV] Title, ### SEV Title, ### SEV: Title
    r"###\s+\[?(PASS|NOTE|CONCERN|FAIL)\]?:?\s+(.+?)"
    r"|"
    # Bold bracket format: **[SEV]** Title
    r"\*\*\[(PASS|NOTE|CONCERN|FAIL)\]\*\*\s+(.+?)"
    r"|"
    # Bullet format: - [SEV] Title
    r"-\s+\[(PASS|NOTE|CONCERN|FAIL)\]\s+(.+?)"
    r")"
    r"(?="
    r"\n###\s+\[?(?:PASS|NOTE|CONCERN|FAIL)"
    r"|\n\*\*\[(?:PASS|NOTE|CONCERN|FAIL)\]"
    r"|\n-\s+\[(?:PASS|NOTE|CONCERN|FAIL)\]"
    r"|\n##\s+"
    r"|\Z"
    r")",
    re.DOTALL | re.IGNORECASE,
)

# Lenient: scan for lines that contain severity keywords in paragraph context
_LENIENT_RE = re.compile(
    r"(?:^|\n)([^\n]*\b(NOTE|CONCERN|FAIL)\b[^\n]*)\n((?:[^\n]+\n?)*)",
    re.IGNORECASE,
)

# Structured tag patterns for category/location extraction from finding bodies
# [ \t]* (not \s*) so the value capture cannot bleed across a blank
# value line into the next line of the body (e.g. an empty `location:`
# tag would otherwise pick up "Some detail." on the following line).
_CATEGORY_RE = re.compile(r"^category:[ \t]*(.*)$", re.IGNORECASE | re.MULTILINE)
_LOCATION_RE = re.compile(r"^location:[ \t]*(.*)$", re.IGNORECASE | re.MULTILINE)
# Existing file_ref pattern: -> path/to/file.py:123
_FILE_REF_RE = re.compile(r"^->\s*(.+)$", re.MULTILINE)

# Debug log path
_DEBUG_LOG_PATH = Path.home() / ".config" / "squadron" / "logs" / "review-debug.jsonl"


def _extract_verdict(text: str) -> Verdict:
    """Parse verdict from the ## Summary section."""
    match = _SUMMARY_RE.search(text)
    if match is None:
        return Verdict.UNKNOWN
    keyword = match.group(1).upper()
    return _VERDICT_MAP.get(keyword, Verdict.UNKNOWN)


def _normalize_location(
    location: str | None,
    *,
    finding_id: str,
    finding_title: str,
    verdict: Verdict,
    template_name: str,
) -> str:
    """Normalize a parsed location value, soft-failing missing/placeholder values.

    Returns UNVERIFIED_LOCATION (and logs a WARNING) when the model omitted
    the location entirely or wrote a non-specific placeholder ('-', 'global',
    'n/a', 'none', empty). Any other value is returned stripped, unchanged.
    """
    if location is None or location.strip().lower() in _PLACEHOLDER_LOCATIONS:
        logger.warning(
            "Finding %s (%r) in %s review (verdict=%s) is missing a "
            "specific location; normalized to %r.",
            finding_id,
            finding_title,
            template_name,
            verdict.value,
            UNVERIFIED_LOCATION,
        )
        return UNVERIFIED_LOCATION
    return location.strip()


def _location_path(location: str) -> str | None:
    """Extract the path portion of a finding's location string.

    Returns the substring before the first ':' or '#' (e.g. 'src/foo.py'
    from 'src/foo.py:42' or 'src/foo.py#sym'). Returns None for the
    UNVERIFIED_LOCATION sentinel and for values that do not begin with a
    plausible path character.
    """
    if location == UNVERIFIED_LOCATION:
        return None
    match = _LOCATION_PATH_RE.match(location)
    if match is None:
        return None
    return match.group(1).strip() or None


def _check_diff_membership(
    findings: list[ReviewFinding],
    diff_files: set[str],
    *,
    template_name: str,
) -> None:
    """For each finding citing a path, WARN if the path is not in *diff_files*.

    Only meaningful for code reviews (the only template type with a diff).
    UNVERIFIED_LOCATION findings and findings whose location cannot be
    interpreted as a path are skipped silently.
    """
    for index, finding in enumerate(findings, start=1):
        if finding.location is None:
            continue
        path = _location_path(finding.location)
        if path is None:
            continue
        if path not in diff_files:
            logger.warning(
                "Finding F%03d (%r) in %s review cites %r which is not "
                "among the files in the diff under review.",
                index,
                finding.title,
                template_name,
                path,
            )


def _check_path_existence(
    findings: list[ReviewFinding],
    cwd: Path,
    *,
    template_name: str,
) -> None:
    """For each finding citing a path, WARN if the path does not exist on disk.

    Cheap defense against hallucinated filenames across all template types.
    Paths are resolved relative to *cwd*. UNVERIFIED_LOCATION findings and
    findings whose location cannot be interpreted as a path are skipped.
    """
    for index, finding in enumerate(findings, start=1):
        if finding.location is None:
            continue
        path = _location_path(finding.location)
        if path is None:
            continue
        if not (cwd / path).exists():
            logger.warning(
                "Finding F%03d (%r) in %s review cites %r which does not "
                "exist on disk (relative to %s).",
                index,
                finding.title,
                template_name,
                path,
                cwd,
            )


def _extract_findings(
    text: str,
    *,
    verdict: Verdict = Verdict.UNKNOWN,
    template_name: str = "",
) -> list[ReviewFinding]:
    """Parse finding blocks into ReviewFinding list.

    Supports five formats: ### [SEV] Title, ### SEV Title, ### SEV: Title,
    **[SEV]** Title, and - [SEV] Title.

    Soft-fails on missing/placeholder ``location:`` values: the field is
    normalized to ``"unverified"`` and a WARNING is logged. ``verdict`` and
    ``template_name`` are included in the warning for triage context.
    """
    findings: list[ReviewFinding] = []
    for index, match in enumerate(_FINDING_RE.finditer(text), start=1):
        # Groups: (g1,g2) heading, (g3,g4) bold, (g5,g6) bullet
        sev_raw = match.group(1) or match.group(3) or match.group(5) or ""
        severity_str = sev_raw.upper()
        title_raw = match.group(2) or match.group(4) or match.group(6) or ""
        severity = _SEVERITY_MAP.get(severity_str)
        if severity is None:
            continue
        title = title_raw.strip().split("\n")[0]
        full_block = match.group(0)
        lines = full_block.split("\n")
        body = "\n".join(lines[1:]).strip()

        # Extract category tag and strip from description
        category: str | None = None
        cat_match = _CATEGORY_RE.search(body)
        if cat_match:
            category = cat_match.group(1).strip()
            body = _CATEGORY_RE.sub("", body).strip()

        # Extract location tag and strip from description
        raw_location: str | None = None
        loc_match = _LOCATION_RE.search(body)
        if loc_match:
            raw_location = loc_match.group(1).strip()
            body = _LOCATION_RE.sub("", body).strip()

        # Extract file_ref from -> pattern
        file_ref: str | None = None
        ref_match = _FILE_REF_RE.search(body)
        if ref_match:
            file_ref = ref_match.group(1).strip()
            # Use file_ref as location fallback when no explicit location: tag
            if raw_location is None:
                raw_location = file_ref

        # Soft-fail: normalize missing/placeholder values to UNVERIFIED_LOCATION.
        # ID matches the F### scheme assigned by ReviewResult.structured_findings.
        finding_id = f"F{index:03d}"
        location = _normalize_location(
            raw_location,
            finding_id=finding_id,
            finding_title=title,
            verdict=verdict,
            template_name=template_name,
        )

        findings.append(
            ReviewFinding(
                severity=severity,
                title=title,
                description=body,
                file_ref=file_ref,
                category=category,
                location=location,
            )
        )
    return findings


def _lenient_extract_findings(
    text: str, verdict: Verdict, template_name: str = ""
) -> list[ReviewFinding]:
    """Attempt lenient extraction: scan for severity keywords in paragraph context."""
    findings: list[ReviewFinding] = []
    for index, match in enumerate(_LENIENT_RE.finditer(text), start=1):
        header_line = match.group(1).strip()
        body = match.group(3).strip()
        # Determine severity from the header line
        upper = header_line.upper()
        if "FAIL" in upper:
            severity = Severity.FAIL
        elif "CONCERN" in upper:
            severity = Severity.CONCERN
        elif "NOTE" in upper:
            severity = Severity.NOTE
        else:
            continue
        title = header_line[:120]
        # Lenient extraction never surfaces a structured location:
        # always normalize (which will warn) so downstream sees the
        # consistent UNVERIFIED_LOCATION sentinel.
        location = _normalize_location(
            None,
            finding_id=f"F{index:03d}",
            finding_title=title,
            verdict=verdict,
            template_name=template_name,
        )
        findings.append(
            ReviewFinding(
                severity=severity,
                title=title,
                description=body,
                location=location,
            )
        )
    return findings


def _synthesize_fallback_finding(
    text: str, verdict: Verdict, template_name: str = ""
) -> ReviewFinding:
    """Create a single synthesized finding from summary text."""
    # Extract text between ## Summary and next ## heading (or end)
    summary_match = re.search(
        r"##\s+Summary\s*\n+(.*?)(?=\n##\s+|\Z)", text, re.DOTALL | re.IGNORECASE
    )
    if summary_match:
        description = summary_match.group(1).strip()
    else:
        description = text.strip()[:500]

    severity = Severity.FAIL if verdict == Verdict.FAIL else Severity.CONCERN
    title = "Unparsed review findings"
    location = _normalize_location(
        None,
        finding_id="F001",
        finding_title=title,
        verdict=verdict,
        template_name=template_name,
    )
    return ReviewFinding(
        severity=severity,
        title=title,
        description=description,
        location=location,
    )


def _write_debug_log(
    *,
    template: str,
    model: str | None,
    verdict: Verdict,
    findings_parsed: int,
    fallback_used: bool,
    raw_output: str,
) -> None:
    """Append a debug entry to the review debug log."""
    try:
        _DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(tz=UTC).isoformat(),
            "template": template,
            "model": model,
            "verdict": verdict.value,
            "findings_parsed": findings_parsed,
            "fallback_used": fallback_used,
            "raw_output": raw_output,
        }
        with _DEBUG_LOG_PATH.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as exc:
        print(f"[squadron] Warning: could not write debug log: {exc}", file=sys.stderr)


def parse_review_output(
    raw_output: str,
    template_name: str,
    input_files: dict[str, str],
    model: str | None = None,
    *,
    diff_files: set[str] | None = None,
    cwd: Path | None = None,
) -> ReviewResult:
    """Parse agent markdown output into a structured ReviewResult.

    Falls back to UNKNOWN verdict if the output doesn't follow expected format.
    When verdict is CONCERNS/FAIL but structured parsing finds zero findings,
    attempts lenient extraction then synthesizes a finding from summary text.

    When *diff_files* is provided (typically only for code-template reviews),
    each finding whose ``location`` cites a path is checked against the diff
    file set; misses log a WARNING. When *cwd* is provided, each finding
    whose ``location`` cites a path is checked for existence on disk; misses
    log a WARNING. Findings with ``location == UNVERIFIED_LOCATION`` are
    skipped by both checks.
    """
    verdict = _extract_verdict(raw_output)
    findings = _extract_findings(
        raw_output, verdict=verdict, template_name=template_name
    )
    fallback_used = False

    mismatch = verdict in (Verdict.CONCERNS, Verdict.FAIL) and not findings
    if mismatch:
        _write_debug_log(
            template=template_name,
            model=model,
            verdict=verdict,
            findings_parsed=0,
            fallback_used=False,
            raw_output=raw_output,
        )
        # Try lenient extraction first
        findings = _lenient_extract_findings(raw_output, verdict, template_name)
        if not findings:
            # Synthesize a single finding from the summary text
            findings = [
                _synthesize_fallback_finding(raw_output, verdict, template_name)
            ]
        fallback_used = True
        _write_debug_log(
            template=template_name,
            model=model,
            verdict=verdict,
            findings_parsed=len(findings),
            fallback_used=True,
            raw_output=raw_output,
        )

    # Post-extraction location validation (slice 904).
    # Diff-membership applies only when a diff file set is supplied
    # (typically code-template reviews). Path-existence applies whenever
    # a cwd is supplied — the cheap defense against hallucinated filenames
    # across all template types.
    if diff_files is not None:
        _check_diff_membership(findings, diff_files, template_name=template_name)
    if cwd is not None:
        _check_path_existence(findings, cwd, template_name=template_name)

    return ReviewResult(
        verdict=verdict,
        findings=findings,
        raw_output=raw_output,
        template_name=template_name,
        input_files=input_files,
        model=model,
        fallback_used=fallback_used,
    )
