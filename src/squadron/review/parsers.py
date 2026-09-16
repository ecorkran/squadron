"""Parse agent markdown output into structured ReviewResult."""

from __future__ import annotations

import json
import logging
import math
import re
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from squadron.review.models import (
    FindingScanCounts,
    ReviewFinding,
    ReviewResult,
    Severity,
    Verdict,
    VerdictSource,
)

logger = logging.getLogger(__name__)

# Sentinel for findings whose location cannot be determined or
# is reported as a non-specific placeholder by the model.
UNVERIFIED_LOCATION = "unverified"

# Values from model output that should be normalized to UNVERIFIED_LOCATION.
# Stored lowercased for case-insensitive comparison.
_PLACEHOLDER_LOCATIONS: frozenset[str] = frozenset({"", "-", "global", "n/a", "none"})

# Captures the path portion of a location value: everything up to (but not
# including) the first ':', '#', whitespace, or end of string. Used by
# diff-membership and path-existence checks. Stopping at whitespace drops
# trailing prose annotations models sometimes append (e.g. "foo.py (and
# related)"), which is never a valid path character on any target platform.
# Returns None for UNVERIFIED_LOCATION callers (handled by guard at the call
# site) and for any value that does not look like a path (e.g. starts with
# '<' from leftover prompt examples).
_LOCATION_PATH_RE = re.compile(r"^([^:#<>\s][^:#\s]*)")

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

# Numeric scoring foundation (slice 300). Lenient, judging-unaware extraction.
# A top-level ``score: <number>`` line — case-insensitive label, leading
# whitespace tolerated, value captured up to end of line. First match wins.
_SCORE_RE = re.compile(r"^[ \t]*score:[ \t]*(.+?)[ \t]*$", re.IGNORECASE | re.MULTILINE)

# A top-level ``criteria:`` label introducing an indented YAML-map block.
# Captures the label's own indent (group 1) so the block scan can stop at the
# first line that is not more-indented than the label (i.e. dedents out).
_CRITERIA_LABEL_RE = re.compile(r"^([ \t]*)criteria:[ \t]*$", re.IGNORECASE | re.MULTILINE)

# A single ``key: <number>`` entry inside a criteria block. The value is
# validated as a finite float separately; this only splits key from value.
_CRITERIA_ENTRY_RE = re.compile(r"^[ \t]+([^:\n]+?):[ \t]*(.+?)[ \t]*$")

# Locates the "## Summary" heading; the verdict keyword itself is matched
# separately, anchored immediately after it (see _extract_verdict / D3).
_SUMMARY_HEADING_RE = re.compile(r"##\s+Summary\s*\n+\s*", re.IGNORECASE)

# Matches a verdict keyword (possibly bold) at a fixed starting position —
# used with re.match, never re.search, so it can only match the very next
# word after the summary heading. A scanning re.search here is D3's bug: a
# keyword fused to the following word (e.g. "PASSThe slice design...") has
# no word boundary after "PASS", so a non-greedy '.*?' scan would run past
# it looking for a bounded match and can find one belonging to a later
# finding's severity word instead — a confidently wrong verdict, worse than
# UNKNOWN. Anchoring at a fixed offset makes that scan impossible: either
# the keyword starts right here, fused or not, or it does not match at all.
_VERDICT_KEYWORD_RE = re.compile(r"(?:\*{0,2})(PASS|CONCERNS|FAIL)", re.IGNORECASE)

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
    """Parse verdict from the ## Summary section.

    Bounded search (D3): the verdict keyword is matched immediately after
    the heading via ``re.match``, not searched for. A scanning search would
    let a fused keyword's missing word boundary carry the match forward into
    a later finding's severity word, returning a confidently wrong verdict
    instead of UNKNOWN.
    """
    heading = _SUMMARY_HEADING_RE.search(text)
    if heading is None:
        return Verdict.UNKNOWN
    keyword_match = _VERDICT_KEYWORD_RE.match(text, heading.end())
    if keyword_match is None:
        return Verdict.UNKNOWN
    keyword = keyword_match.group(1).upper()
    return _VERDICT_MAP.get(keyword, Verdict.UNKNOWN)


def _verdict_from_findings(findings: list[ReviewFinding]) -> Verdict:
    """Derive a verdict from parsed finding severities (#28).

    Most-severe-wins over the severity vocabulary the findings already
    carry: any FAIL yields FAIL, any CONCERN yields CONCERNS, otherwise
    PASS. Used only to recover a verdict the summary parse lost — never to
    override one the model actually stated.

    NOTE and PASS findings do not raise the verdict: a review that recorded
    only observations passed, and treating a NOTE as a concern would invent
    severity the reviewer did not assign.
    """
    severities = {finding.severity for finding in findings}
    if Severity.FAIL in severities:
        return Verdict.FAIL
    if Severity.CONCERN in severities:
        return Verdict.CONCERNS
    return Verdict.PASS


def _parse_finite_float(raw: str) -> float | None:
    """Parse a string to a finite float, or None.

    Returns None for non-numeric values and for inf/nan — a non-finite value
    is meaningless as a 0-100 quantity. Never raises. No range check (a value
    outside 0-100 is still a parseable number; range validation is slice 301).
    """
    try:
        value = float(raw)
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return value


def _extract_score(text: str) -> float | None:
    """Extract an optional top-level ``score: <number>`` value.

    Lenient and judging-unaware: returns None when no ``score:`` line is
    present, when the value is non-numeric, or when it is non-finite. First
    ``score:`` line wins (consistent with ``_extract_verdict`` taking the
    first ``## Summary`` match). Never raises; never range-checks.
    """
    match = _SCORE_RE.search(text)
    if match is None:
        return None
    return _parse_finite_float(match.group(1))


def _extract_criteria(text: str) -> dict[str, float] | None:
    """Extract an optional ``criteria:`` YAML-map block.

    Recognized shape: a top-level ``criteria:`` label followed by an indented
    block of ``key: <number>`` lines (the frontmatter map idiom emitted by
    ``format_review_markdown``). Returns the parsed ``dict[str, float]`` or
    None. The whole map becomes None (never a partial/coerced map) when the
    block is absent, empty, or any entry's value is not a finite number.
    Never raises. The structured-output/JSON variant is slice 302.
    """
    label = _CRITERIA_LABEL_RE.search(text)
    if label is None:
        return None

    label_indent = len(label.group(1).expandtabs())
    # `$` in MULTILINE matches before the newline, so the slice begins with the
    # label line's trailing newline; lstrip it so the first block line is first.
    block = text[label.end() :].lstrip("\n")
    lines = block.splitlines()

    criteria: dict[str, float] = {}
    for line in lines:
        if not line.strip():
            break  # blank line ends the block
        indent = len(line[: len(line) - len(line.lstrip())].expandtabs())
        if indent <= label_indent:
            break  # dedent ends the block
        entry = _CRITERIA_ENTRY_RE.match(line)
        if entry is None:
            return None  # malformed line inside the block → whole map None
        value = _parse_finite_float(entry.group(2))
        if value is None:
            return None  # non-finite/non-numeric value → whole map None
        criteria[entry.group(1).strip()] = value

    return criteria or None


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


def location_path(location: str) -> str | None:
    """Extract the path portion of a finding's location string.

    Returns the substring before the first ':' or '#' (e.g. 'src/foo.py'
    from 'src/foo.py:42' or 'src/foo.py#sym'). Returns None for the
    UNVERIFIED_LOCATION sentinel and for values that do not begin with a
    plausible path character.

    Public because how a finding location is read is a review-domain concept:
    consumers outside this module (the findings-addressed gate) need the same
    answer, and a second implementation would drift from this one.
    """
    if location == UNVERIFIED_LOCATION:
        return None
    match = _LOCATION_PATH_RE.match(location)
    if match is None:
        return None
    return match.group(1).strip() or None


# The line portion of a location: ':42' or ':42-50' immediately after the path.
# A '#symbol' anchor names no line, and neither does a bare path.
_LOCATION_LINE_RE = re.compile(r"^[^:#<>\s][^:#\s]*:(\d+)(?:-(\d+))?(?:\s|$)")


def location_line(location: str) -> int | None:
    """The last line number a location cites, or None when it cites none.

    ``path:42`` yields 42 and ``path:42-50`` yields 50 — the last cited line
    is the one that must exist for the range to be real. A ``path#symbol``
    anchor, a bare ``path``, and the UNVERIFIED_LOCATION sentinel are
    whole-file citations and yield None.

    A sibling of :func:`location_path`, which is unchanged: the
    findings-addressed gate depends on its exact contract.
    """
    if location == UNVERIFIED_LOCATION:
        return None
    match = _LOCATION_LINE_RE.match(location)
    if match is None:
        return None
    return int(match.group(2) or match.group(1))


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
        path = location_path(finding.location)
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


def _resolve_under(root: Path, path: str) -> Path | None:
    """The resolved path *path* names under *root*, or None if nothing does.

    A review model is given document *content*, not repository paths, so it
    cites documents the only way it can — by bare filename (e.g.
    ``172-tasks.foo.md``). Those live in a subdirectory of the document root
    (``tasks/``, ``slices/``, ``reviews/``, …), so an exact ``root / path``
    join misses them and the check fires on findings that cite real files.

    Multi-segment paths are treated as root-relative and joined exactly:
    a model that supplies a directory is taken at its word. Only a bare
    filename triggers the search, and only its basename is matched — an
    invented filename still resolves nowhere, so the hallucination defense
    this check exists for is preserved.
    """
    direct = root / path
    if direct.exists():
        return direct
    # Only bare filenames get the search; a cited directory is honored as given.
    if "/" in path or "\\" in path:
        return None
    return next(iter(root.rglob(path)), None)


#: Largest file the line-bounds check will read. A citation into something
#: bigger is left unverified rather than streaming an arbitrary blob on the
#: parse path — the check is a cheap sanity test, not an indexing pass.
_MAX_LINE_CHECK_BYTES = 4 * 1024 * 1024

_OUTSIDE_ROOT_REASON = "resolves outside the review root"
_IS_DIRECTORY_REASON = "is a directory, not a file"
_TOO_LARGE_REASON = f"is larger than the {_MAX_LINE_CHECK_BYTES}-byte line-check limit"
_UNREADABLE_REASON = "could not be read"


def _count_lines(root: Path, resolved: Path) -> tuple[int | None, str | None]:
    """Count the lines in *resolved*, or say why the count could not be taken.

    Returns ``(count, None)`` on success and ``(None, reason)`` otherwise.
    Deliberately does not log: it has no finding identifier, and every WARNING
    on this path must name the finding it concerns. The caller iterating
    findings owns the message.

    Containment is checked before the file is ever opened, so a ``../``
    citation cannot make the parser read outside the review root. Lines are
    counted from raw bytes, so no decode can fail on a file that happens not
    to be UTF-8; a final unterminated line still counts.
    """
    try:
        real_root = root.resolve()
        real_path = resolved.resolve()
    except OSError:
        return None, _UNREADABLE_REASON

    if not real_path.is_relative_to(real_root):
        return None, _OUTSIDE_ROOT_REASON

    try:
        stat = real_path.stat()
    except OSError:
        return None, _UNREADABLE_REASON
    if real_path.is_dir():
        return None, _IS_DIRECTORY_REASON
    if stat.st_size > _MAX_LINE_CHECK_BYTES:
        return None, _TOO_LARGE_REASON

    newlines = 0
    last_byte = b""
    try:
        with real_path.open("rb") as handle:
            while chunk := handle.read(65536):
                newlines += chunk.count(b"\n")
                last_byte = chunk[-1:]
    except OSError:
        return None, _UNREADABLE_REASON

    if last_byte and last_byte != b"\n":
        newlines += 1  # a final line with no trailing newline still exists
    return newlines, None


def _check_cited_paths(
    findings: list[ReviewFinding],
    cwd: Path,
    *,
    template_name: str,
) -> None:
    """Check each finding's cited path exists, and its cited line is in bounds.

    One pass, because resolving a citation is the expensive part: a bare
    filename — which is how a model cites a document, having been given content
    rather than paths — falls back to ``rglob`` over the whole review root, and
    a hallucinated name walks the tree to exhaustion. Two passes meant two full
    walks per phantom citation, on the parse path the pipeline awaits.

    Existence is a WARNING only, as it has always been. The line check also
    records its result on the finding (``location_verified``): a line past the
    end of a file is the deterministic signature of a hallucinated citation,
    and a WARNING alone was ignored on every #91 phantom.
    """
    for index, finding in enumerate(findings, start=1):
        if finding.location is None:
            continue
        path = location_path(finding.location)
        if path is None:
            continue

        resolved = _resolve_under(cwd, path)
        if resolved is None:
            logger.warning(
                "Finding F%03d (%r) in %s review cites %r which does not "
                "exist on disk (relative to %s).",
                index,
                finding.title,
                template_name,
                path,
                cwd,
            )
            # Verifiably absent. Only meaningful for a line-bearing citation:
            # a whole-file citation of a missing file is already covered by the
            # WARNING above, and location_verified speaks about the line.
            if location_line(finding.location) is not None:
                finding.location_verified = False
            continue

        line = location_line(finding.location)
        if line is None:
            continue  # whole-file citation: nothing to bounds-check

        count, reason = _count_lines(cwd, resolved)
        if count is None:
            logger.warning(
                "Finding F%03d (%r) in %s review cites %r, but its line count "
                "could not be taken: the file %s. Location left unverified.",
                index,
                finding.title,
                template_name,
                finding.location,
                reason,
            )
            continue

        if line > count:
            logger.warning(
                "Finding F%03d (%r) in %s review cites line %d of %r, which has only %d line(s).",
                index,
                finding.title,
                template_name,
                line,
                path,
                count,
            )
            finding.location_verified = False
        else:
            finding.location_verified = True


# A fenced code block: ``` or ~~~ at line start (leading whitespace tolerated),
# optional info string, running to a matching closing fence or end of document.
# A model restating the required format almost always fences it, and
# finding-shaped text inside a fence is never a finding (#91).
# The closing fence must be *at least* as long as the opener, per CommonMark —
# not exactly as long, and not merely three or more. Both directions are real
# failures and the rule is one rule, so both are pinned by tests:
#   - A ``` block closed with ```` must close. A backreference to the whole
#     opener would call it unclosed, mask to end of document, and silently
#     drop every finding after it — the failure this part exists to prevent.
#   - A ```` block must *not* be closed by an inner ```. A bare {3,} closer
#     ends the block early and unmasks the rest of a fenced format echo as if
#     it were live text, which is the same bug pointing the other way.
# ``(?P=char){N,}`` with N taken from the opener is not expressible in a static
# pattern, so only the opener is matched here and the length comparison is
# applied to candidate closers in code. An info string (```markdown) is part
# of the opener and can never close a block.
_FENCE_OPEN_RE = re.compile(
    r"^[ \t]*(?P<fence>(?P<char>[`~])(?P=char){2,})[^\n]*\n",
    re.MULTILINE,
)

# A markdown heading whose text is a single word, used to locate the sections
# the parse is bounded to. Lenient by project rule: any level, bold or code
# emphasis, trailing ':' or '.', and surrounding whitespace all tolerated.
_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})[ \t]*(?P<text>[^\n]*?)[ \t]*$", re.MULTILINE)

# --- Newline-free response normalization (#96, design D1/D2) ---
#
# A real heading-start hash run (1-6 '#') is always followed by a space.
# This is also what makes Trap 1 (mid-run insertion) and Trap 3 (a '#' inside
# a location: anchor, e.g. '...918-slice.review-grounding.md#The-problem')
# structurally impossible to confuse with a heading start: the second '#' of
# '###' is followed by '#', not a space, and an anchor '#' is followed
# directly by its slug's first letter, not a space.
_HEADING_START_RE = re.compile(r"#{1,6}(?= )")

# Trap 2 (fused heading text): a break must also land after a recognized
# single-word section heading ('## Summary' / '## Findings') when the next
# character is not whitespace, or _HEADING_RE's [^\n]*? would swallow the
# entire following paragraph as heading text. Keyed on the same closed
# vocabulary _locate_section normalizes against.
_SECTION_HEADING_FUSION_RE = re.compile(r"#{1,6}[ \t]+(Summary|Findings)(?=\S)", re.IGNORECASE)

# Trap 2's second case: a verdict keyword fused to the prose that follows it
# (e.g. '## SummaryPASSThe slice design...'). A break after the keyword is
# necessary so _SUMMARY_RE's required word boundary exists; D3's bounded-
# search fix to _extract_verdict is the durable guard against the same fusion
# misdirecting a match into a later finding's severity word.
_VERDICT_FUSION_RE = re.compile(r"\b(PASS|CONCERNS|FAIL)(?=[A-Za-z])", re.IGNORECASE)

# A category:/location: tag fused to the preceding prose (no line break
# separating a finding's title from its tags). _CATEGORY_RE/_LOCATION_RE are
# '^...$' MULTILINE and need this break to find the tag at all.
_TAG_FUSION_RE = re.compile(r"(?<=\S)(category:|location:)", re.IGNORECASE)

# Trap 3's companion: once an anchor '#' is correctly left alone (not treated
# as a heading), the anchor's kebab-case slug still runs directly into the
# prose that follows with no terminator, which would otherwise make
# _LOCATION_RE's '$'-bounded capture swallow the rest of the finding body as
# part of the location value. Matches a path-like anchor fragment (a '#'
# preceded by non-whitespace, i.e. not a heading start) up to where the
# slug's letter/digit/dash run ends and a capitalized prose word begins.
_ANCHOR_END_RE = re.compile(r"(?<=\S)#[A-Za-z0-9][A-Za-z0-9-]*(?=[A-Z][a-z])")

# #91 guard: a fence marker (3+ backticks or tildes) in newline-free text is
# fused to whatever surrounds it, so _FENCE_OPEN_RE's '^[ \t]*(fence)...\n'
# requirement (MULTILINE) can never match it as-is — a newline-free response
# structurally cannot open a real fence before normalization runs. Isolating
# every fence marker onto its own line restores exactly the property
# _mask_fences depends on, so a newline-free response that quotes the finding
# format inside a fence gets masked the same as any other response (design
# SC5) instead of leaking the quoted text through as fabricated findings.
_FENCE_MARK_RE = re.compile(r"[`~]{3,}")


def _insert_before(text: str, pattern: re.Pattern[str]) -> tuple[str, int]:
    """*text* with a ``\\n`` inserted before each match not already at line start.

    Returns the transformed text and the number of breaks inserted.
    """
    pieces: list[str] = []
    position = 0
    inserted = 0
    for match in pattern.finditer(text):
        start = match.start()
        pieces.append(text[position:start])
        if start > 0 and text[start - 1] != "\n":
            pieces.append("\n")
            inserted += 1
        position = start
    pieces.append(text[position:])
    return "".join(pieces), inserted


def _insert_after(text: str, pattern: re.Pattern[str]) -> tuple[str, int]:
    """*text* with a ``\\n`` inserted after each match's end. Never de-dupes."""
    pieces: list[str] = []
    position = 0
    inserted = 0
    for match in pattern.finditer(text):
        end = match.end()
        pieces.append(text[position:end])
        pieces.append("\n")
        inserted += 1
        position = end
    pieces.append(text[position:])
    return "".join(pieces), inserted


def _insert_around(text: str, pattern: re.Pattern[str]) -> tuple[str, int]:
    """*text* with a ``\\n`` inserted on both sides of each match, isolating
    it onto its own line. Used for fence markers, where both the opener and
    the following content need their own line for ``_FENCE_OPEN_RE`` and the
    closer pattern (both ``^...$`` MULTILINE) to recognize them at all.
    """
    pieces: list[str] = []
    position = 0
    inserted = 0
    for match in pattern.finditer(text):
        start, end = match.start(), match.end()
        pieces.append(text[position:start])
        if start > 0 and text[start - 1] != "\n":
            pieces.append("\n")
            inserted += 1
        pieces.append(text[start:end])
        position = end
    pieces.append(text[position:])
    text = "".join(pieces)

    pieces = []
    position = 0
    for match in pattern.finditer(text):
        end = match.end()
        pieces.append(text[position:end])
        if end < len(text) and text[end] != "\n":
            pieces.append("\n")
            inserted += 1
        position = end
    pieces.append(text[position:])
    return "".join(pieces), inserted


def _normalize_line_structure(text: str) -> tuple[str, int]:
    """Restore the line structure the parser's seven constructs assume (D1).

    Applied only to a response detected as newline-free (D5) — every other
    response is returned unchanged by the caller before reaching here.
    Conservative and ordered: each pass targets one fusion shape measured
    against the real specimen (design D2), never an unconditional break
    before every '#' or tag, which a naive first cut showed makes the parse
    strictly worse (0 findings instead of 1).

    Fence markers are isolated first (#91 guard), before anything else can
    insert a break inside what should become a masked fence body.

    Returns the normalized text and the total count of inserted breaks, for
    the run digest (D4).
    """
    total_inserted = 0
    text, count = _insert_around(text, _FENCE_MARK_RE)
    total_inserted += count
    text, count = _insert_before(text, _HEADING_START_RE)
    total_inserted += count
    text, count = _insert_after(text, _SECTION_HEADING_FUSION_RE)
    total_inserted += count
    text, count = _insert_after(text, _VERDICT_FUSION_RE)
    total_inserted += count
    text, count = _insert_before(text, _TAG_FUSION_RE)
    total_inserted += count
    text, count = _insert_after(text, _ANCHOR_END_RE)
    total_inserted += count
    return text, total_inserted


def _mask_fences(text: str) -> str:
    """Blank out the interior of every fenced code block, preserving offsets.

    Every character inside a fence becomes a space except newlines, so line
    numbers and character offsets of unfenced text are unchanged and the
    masked text can be scanned in place of the original.

    A candidate closer shorter than the opener does not close the block, per
    CommonMark; the scan resumes past it and keeps looking. The pattern cannot
    express "at least as long as the opener", so that comparison happens here.
    """
    pieces: list[str] = []
    position = 0
    while position < len(text):
        opener = _FENCE_OPEN_RE.search(text, position)
        if opener is None:
            break
        fence = opener.group("fence")
        body_start = opener.end()
        close = _find_closer(text, body_start, fence)
        body_end = close.start() if close is not None else len(text)
        block_end = close.end() if close is not None else len(text)

        pieces.append(text[position : opener.start()])
        pieces.append(text[opener.start() : body_start])
        pieces.append(_blank(text[body_start:body_end]))
        pieces.append(text[body_end:block_end])
        position = block_end
    pieces.append(text[position:])
    return "".join(pieces)


def _find_closer(text: str, start: int, fence: str) -> re.Match[str] | None:
    """The first closer for *fence* at or after *start*, or ``None``.

    A run of the same character shorter than the opener is not a closer: it is
    ordinary content inside the block, so the search continues past it. No
    sufficient run means an unclosed block, which runs to end of document.
    """
    pattern = _closer_pattern(fence[0])
    for candidate in pattern.finditer(text, start):
        if len(candidate.group("closer")) >= len(fence):
            return candidate
    return None


@lru_cache(maxsize=2)
def _closer_pattern(char: str) -> re.Pattern[str]:
    """A candidate-closer pattern for one fence character."""
    return re.compile(rf"^[ \t]*(?P<closer>{re.escape(char)}{{3,}})[ \t]*$\n?", re.MULTILINE)


def _blank(body: str) -> str:
    """*body* with every character but newlines replaced by a space."""
    return "".join("\n" if ch == "\n" else " " for ch in body)


def _count_finding_matches(text: str) -> int:
    """Finding-shaped matches in *text*, counted without interpreting them."""
    return len(list(_FINDING_RE.finditer(text)))


def _normalize_heading_text(text: str) -> str:
    """Reduce a heading's text to a bare comparable word."""
    return text.strip().strip("*_`").strip().rstrip(":.").strip().lower()


def _locate_section(text: str, name: str) -> tuple[int, int] | None:
    """Span of the ``name`` section's body, or None when it has no heading.

    Runs from the end of the heading line to the next heading of the same or
    higher level, or to the end of the document. A deeper heading (the ``###``
    of an individual finding) does not terminate the section.

    Returns ``None`` for the ``"findings"`` name specifically when the
    located span holds no finding-shaped text while the document does. A
    ``### Findings`` heading is the case: it sits at the same level as the
    ``### [SEV]`` findings it introduces, so it closes before its own first
    finding. Bounding to that empty span would discard every real finding in
    the document, so the caller falls back to the unbounded scan instead —
    the same posture taken for a headingless response, and for the same
    reason: never drop a real finding to exclude a phantom. Other section
    names (e.g. ``"summary"``) legitimately hold zero finding-shaped text and
    are unaffected by this guard.
    """
    for match in _HEADING_RE.finditer(text):
        if _normalize_heading_text(match.group("text")) != name:
            continue
        level = len(match.group("hashes"))
        start = match.end()
        end = len(text)
        for following in _HEADING_RE.finditer(text, start):
            if len(following.group("hashes")) <= level:
                end = following.start()
                break
        if name == "findings" and _count_finding_matches(text[start:end]) == 0 < _count_finding_matches(
            text
        ):
            return None
        return start, end
    return None


def _extract_findings(
    text: str,
    *,
    verdict: Verdict = Verdict.UNKNOWN,
    template_name: str = "",
) -> tuple[list[ReviewFinding], FindingScanCounts, bool]:
    """Parse finding blocks into a ReviewFinding list, bounded to the findings.

    Supports five formats: ### [SEV] Title, ### SEV Title, ### SEV: Title,
    **[SEV]** Title, and - [SEV] Title.

    The scan is bounded twice (slice 917 Part 3, #91). Fenced code blocks are
    masked, because a model restating the required format almost always fences
    it and finding-shaped text inside a fence is never a finding. Then, when a
    ``## Findings`` heading exists, only that section is scanned. When it does
    not, the whole response is scanned exactly as before — real reviews exist
    that omit the heading and start their findings at line 2, and discarding
    those would lose genuine findings to fix a phantom.

    The permissive five-shape matching inside the scanned region is not the
    bug and is unchanged.

    Soft-fails on missing/placeholder ``location:`` values: the field is
    normalized to ``"unverified"`` and a WARNING is logged. ``verdict`` and
    ``template_name`` are included in the warning for triage context.

    Returns the findings, the scan counts feeding the run digest, and whether
    a findings heading was located.
    """
    total = _count_finding_matches(text)
    masked = _mask_fences(text)
    in_fences = total - _count_finding_matches(masked)

    span = _locate_section(masked, "findings")
    scanned = masked[span[0] : span[1]] if span is not None else masked
    in_section = _count_finding_matches(scanned)

    findings: list[ReviewFinding] = []
    for index, match in enumerate(_FINDING_RE.finditer(scanned), start=1):
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
    counts = FindingScanCounts(
        total=total,
        in_fences=in_fences,
        in_section=in_section,
        surviving=len(findings),
    )
    return findings, counts, span is not None


def _write_debug_log(
    *,
    template: str,
    model: str | None,
    verdict: Verdict,
    findings_parsed: int,
    degraded: bool,
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
            "degraded": degraded,
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
    the model did not follow the required ``### [SEVERITY] Title`` format.
    Rather than guessing at findings from unstructured prose, the findings
    list is left empty and a WARNING is logged — a wrong-but-plausible
    fabricated finding is worse than an honestly empty list, since it looks
    like real signal. The raw model output remains available on
    ``ReviewResult.raw_output`` (and in the saved review file) either way, so
    nothing is silently discarded — it is just not disguised as a finding.

    When *diff_files* is provided (typically only for code-template reviews),
    each finding whose ``location`` cites a path is checked against the diff
    file set; misses log a WARNING. When *cwd* is provided, each finding
    whose ``location`` cites a path is checked for existence on disk; misses
    log a WARNING. Findings with ``location == UNVERIFIED_LOCATION`` are
    skipped by both checks.
    """
    # Newline-free responses break seven line-structure-dependent constructs
    # in this parser (#96, design D1). Scoped narrowly to that exact trigger
    # (D5): every response that parses correctly today — anything containing
    # at least one newline — takes this same, byte-identical path it always
    # has. `parsed_text` is what every downstream parsing step reads;
    # `raw_output` (unmodified) is what the ReviewResult and the artifact's
    # `### Raw Response` section persist — the two must never be conflated.
    if "\n" not in raw_output:
        parsed_text, normalized_break_count = _normalize_line_structure(raw_output)
    else:
        parsed_text, normalized_break_count = raw_output, 0

    verdict = _extract_verdict(parsed_text)
    # Provenance (#97, D7): STATED unless a later branch derives or cannot
    # resolve it. Set here, not computed from fallback_used, because one
    # branch below (the findings-parse mismatch) sets fallback_used=True for
    # a verdict that was genuinely stated — only the *findings* failed to
    # parse (T2.3). Reassigning per branch, by what actually happened to the
    # verdict, is the only way that branch resolves correctly.
    verdict_source: VerdictSource | None = VerdictSource.STATED
    findings, finding_scan, findings_section_located = _extract_findings(
        parsed_text, verdict=verdict, template_name=template_name
    )
    summary_section_located = _locate_section(_mask_fences(parsed_text), "summary") is not None
    if not findings_section_located:
        # INFO, not WARNING: a missing heading is not a degradation. Real
        # reviews omit it and parse correctly, so warning here would fire on
        # good input and train readers to ignore the channel. The fact is
        # carried on the result and rendered in the artifact's run digest,
        # which is where a surprising finding count gets explained.
        logger.info(
            "No '## Findings' heading located in %s review (model %s); "
            "scanned the whole response for findings.",
            template_name,
            model,
        )
    fallback_used = False

    # Reconcile a lost verdict against the findings that did parse (#28).
    # Finding extraction accepts five heading formats while verdict
    # extraction requires one '## Summary' shape, so a model that renders
    # recognizable findings but reshapes its summary loses the verdict and
    # writes a self-contradictory document — UNKNOWN alongside a [CONCERN].
    # Deriving from the findings applies the project's lenient-parsing rule
    # (parse the semantic content, not the formatting) to the same output.
    if verdict is Verdict.UNKNOWN and findings:
        derived = _verdict_from_findings(findings)
        logger.warning(
            "%s review (model=%s) parsed %d finding(s) but no usable "
            "'## Summary' verdict; deriving %s from finding severities. "
            "The model likely reshaped or omitted its summary section.",
            template_name,
            model,
            len(findings),
            derived.value,
        )
        _write_debug_log(
            template=template_name,
            model=model,
            verdict=derived,
            findings_parsed=len(findings),
            degraded=True,
            raw_output=raw_output,
        )
        verdict = derived
        fallback_used = True
        verdict_source = VerdictSource.DERIVED
    elif verdict is Verdict.UNKNOWN:
        # Genuinely unknown: no verdict and nothing to derive one from.
        # Previously silent, which made a failed parse indistinguishable
        # from a review that legitimately had nothing to say.
        logger.warning(
            "%s review (model=%s) produced no usable '## Summary' verdict and "
            "no parseable findings; verdict left UNKNOWN. See raw_output for "
            "the model's actual response.",
            template_name,
            model,
        )
        # The two sibling branches retain the raw output here; this one did not, so the
        # one case with nothing else to go on was the one that kept no evidence (#61).
        # The result's own fallback_used stays False — nothing was derived or fabricated;
        # the artifact keys its degraded rendering on the UNKNOWN verdict instead.
        # verdictSource (#97, D8): omitted rather than STATED — there is no
        # verdict here to attribute provenance to (UNKNOWN is not a resolved
        # verdict), so "does not apply" is the honest answer, following the
        # established _review_frontmatter_lines convention for optional keys.
        verdict_source = None
        _write_debug_log(
            template=template_name,
            model=model,
            verdict=verdict,
            findings_parsed=0,
            degraded=True,
            raw_output=raw_output,
        )

    mismatch = verdict in (Verdict.CONCERNS, Verdict.FAIL) and not findings
    if mismatch:
        fallback_used = True
        # verdictSource stays STATED here (#97, T2.3): this verdict came from
        # _extract_verdict — the model genuinely stated it — only the
        # *findings* failed to parse. fallback_used=True and STATED both hold
        # simultaneously; do not compute verdict_source from fallback_used or
        # this branch mislabels a stated verdict as derived.
        logger.warning(
            "%s review (model=%s) has verdict=%s but zero structured findings "
            "were parsed — the model likely did not follow the required "
            "'### [SEVERITY] Title' format. Findings left empty rather than "
            "fabricated from unstructured text; see raw_output for the "
            "model's actual response.",
            template_name,
            model,
            verdict.value,
        )
        _write_debug_log(
            template=template_name,
            model=model,
            verdict=verdict,
            findings_parsed=0,
            degraded=True,
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
        _check_cited_paths(findings, cwd, template_name=template_name)

    # Numeric scoring foundation (slice 300): optional, lenient extraction.
    # Absent or malformed → None (silent — a score-less review is the norm).
    # provenance is never set by the parser (reserved field — slice 301).
    score = _extract_score(raw_output)
    criteria = _extract_criteria(raw_output)

    return ReviewResult(
        verdict=verdict,
        findings=findings,
        raw_output=raw_output,
        template_name=template_name,
        input_files=input_files,
        model=model,
        fallback_used=fallback_used,
        verdict_source=verdict_source,
        score=score,
        criteria=criteria,
        summary_section_located=summary_section_located,
        findings_section_located=findings_section_located,
        finding_scan=finding_scan,
        normalized_break_count=normalized_break_count,
    )
