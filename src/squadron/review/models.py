"""Review result models — structured output from review executions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class Verdict(StrEnum):
    """Overall review verdict."""

    PASS = "PASS"
    CONCERNS = "CONCERNS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class Severity(StrEnum):
    """Severity level for an individual finding."""

    PASS = "PASS"
    NOTE = "NOTE"
    CONCERN = "CONCERN"
    FAIL = "FAIL"


class VerdictSource(StrEnum):
    """Whether a review's verdict was stated by the model or derived (#97).

    A closed two-value vocabulary (D7), not a reason string: fallback_used
    already does not distinguish *why* a parse failed, and a reason string
    would need its own vocabulary every consumer switches on — string-dispatch
    on a field whose values are not yet known. The *reason* stays in the run
    digest, which is where a human triages; this field answers only "did the
    model say this?", orthogonal to how much work squadron did to read it
    (a normalized-but-then-stated parse, per slice 919 Part 1's D4, is still
    STATED).
    """

    STATED = "stated"
    DERIVED = "derived"


class TemplateValidationError(Exception):
    """Raised when a template YAML file fails validation."""


@dataclass
class StructuredFinding:
    """Machine-readable finding for frontmatter and pipeline consumption."""

    id: str
    severity: str
    category: str
    summary: str
    location: str | None = None


@dataclass
class ReviewFinding:
    """A single finding from a review."""

    severity: Severity
    title: str
    description: str
    file_ref: str | None = None
    category: str | None = None
    location: str | None = None
    # Was the cited location checked, and did it hold (slice 917 Part 5)?
    #   None  — not checked. The common case: no cwd was supplied, the
    #           citation names no line, or the check could not run.
    #   True  — the path resolved and the cited line is within the file.
    #   False — checked and wrong: the path does not resolve, or the cited
    #           line is past the end of the file. The deterministic signature
    #           of a hallucinated citation.
    # Tri-state deliberately: a plain bool would collapse "checked and bad"
    # with "never checked", and the second is by far the more common. A gate
    # reading False as "hallucinated" would reject most legitimate findings on
    # non-code templates. Written, never read — nothing in this slice consumes
    # it, and it is absent from StructuredFinding, to_dict, and frontmatter.
    location_verified: bool | None = None


@dataclass(frozen=True)
class FindingScanCounts:
    """How many finding-shaped matches the parser saw, and where (slice 917).

    The #91 signature made countable: a response that echoes the template's
    own specimen produces a large ``total`` and a much smaller ``surviving``.
    Reported by the artifact's run digest; nothing gates on these.
    """

    total: int
    """Finding-shaped matches anywhere in the raw response."""
    in_fences: int
    """Of those, how many sat inside a fenced code block."""
    in_section: int
    """Matches inside the bounded ``## Findings`` section, fences already
    masked. Equal to the masked whole-response count when no heading exists."""
    surviving: int
    """Matches that became actual findings after severity validation."""


@dataclass
class ReviewResult:
    """Structured output from a review execution."""

    verdict: Verdict
    findings: list[ReviewFinding]
    raw_output: str
    template_name: str
    input_files: dict[str, str]
    timestamp: datetime = field(default_factory=datetime.now)
    model: str | None = None
    fallback_used: bool = False
    # Whether the verdict was stated by the model or derived from findings
    # (slice 919 Part 2, #97). None means "does not apply" — the
    # nothing-parsed branch, where verdict stays UNKNOWN (D8) — not computed
    # from fallback_used: the findings-parse-mismatch branch sets
    # fallback_used=True for a verdict that was genuinely STATED, so the two
    # fields are independent and must not be conflated.
    verdict_source: VerdictSource | None = None
    # Numeric scoring foundation (slice 300) — all optional, default None.
    # score/criteria are populated by the parser when present; provenance is a
    # reserved field (added here, never set or read in this slice — slice 301).
    score: float | None = None
    criteria: dict[str, float] | None = None
    provenance: str | None = None
    # Tool-use telemetry (slice 265). Both None when the review ran without tools; a
    # populated tools_given with tool_calls_made == 0 is the distinct "offered but unused"
    # case, which is exactly what issue #68 made invisible.
    tools_given: list[str] | None = None
    tool_calls_made: int | None = None
    # Why tools were withheld (slice 266), or None if they were not. The third state the
    # two fields above cannot express: an empty tools_given is otherwise identical to a
    # review whose template declared no tools at all.
    tools_suppressed_reason: str | None = None
    # Stop-reason evidence (slice 918, issue #92). None means *not reported* — the same
    # tri-state the telemetry fields above use — which is the honest reading for the SDK
    # path, where finish_reason has no equivalent (D12).
    #
    # These live in to_dict() but NOT in frontmatter (D10). The two surfaces are not
    # required to match and already do not: frontmatter is the consumed contract the
    # verdict gate reads, while JSON is what programmatic consumers read, and fallback_used
    # is likewise JSON-only. Promoting a diagnostic into frontmatter would make the gate
    # depend on it.
    #
    # Why the backend stopped, verbatim from the stream; an abnormal value ("length") is a
    # mechanical signal that output was truncated rather than complete.
    stop_reason: str | None = None
    # How many characters the model spent reasoning before answering. Large with an empty
    # or unparseable response is the #92 signature.
    reasoning_chars: int | None = None
    # How many tool calls failed. 0 is a real answer and must render and serialize as 0:
    # the Amoeba orchestrator routes on ``tool_calls_made == failed_tool_calls > 0`` as a
    # retry predicate, which a 0 collapsed into "not reported" would silently defeat.
    failed_tool_calls: int | None = None
    # Parse-scan facts (slice 917 Part 3). None means "not produced by the
    # parser" — a hand-built result — the same convention provenance uses.
    # These feed the artifact's run digest (Part 6) and nothing else: no gate
    # reads them, and they are absent from to_dict() and from frontmatter.
    summary_section_located: bool | None = None
    findings_section_located: bool | None = None
    finding_scan: FindingScanCounts | None = None
    # Newline-free normalization (slice 919 Part 1, #96). 0 means the response
    # contained at least one newline and took the unmodified parse path (D5) —
    # not recoverable from raw_output alone at render time, unlike the
    # newline-free indicator above, since an *inserted-break count* requires
    # having actually run the normalizer. Feeds the run digest (D4) only.
    normalized_break_count: int = 0
    # Prompt capture fields — populated at verbosity >= 2, excluded from to_dict()
    system_prompt: str | None = None
    user_prompt: str | None = None
    rules_content_used: str | None = None
    # True when the SDK's claude_code preset carried system_prompt as its appended part
    # (#85). Without this a reader of the -vv appendix would take the recorded text for
    # the whole system prompt; the CLI's preset text is not squadron's to capture.
    default_system_prompt_preset_used: bool = False

    def to_dict(self, verdict_override: str | None = None) -> dict[str, object]:
        """Serialize for JSON output.

        Args:
            verdict_override: Explicit verdict string; falls back to
                ``self.verdict.value``. See ``format_review_markdown`` for
                why judge templates need this (score-derived verdict, not
                the always-``UNKNOWN`` raw parse).
        """
        payload: dict[str, object] = {
            "verdict": verdict_override or self.verdict.value,
            "findings": [
                {
                    "severity": f.severity.value,
                    "title": f.title,
                    "description": f.description,
                    "file_ref": f.file_ref,
                    "category": f.category,
                    "location": f.location,
                }
                for f in self.findings
            ],
            "structured_findings": [
                {
                    "id": sf.id,
                    "severity": sf.severity,
                    "category": sf.category,
                    "summary": sf.summary,
                    "location": sf.location,
                }
                for sf in self.structured_findings
            ],
            "template_name": self.template_name,
            "input_files": self.input_files,
            "timestamp": self.timestamp.isoformat(),
            "model": self.model,
            "score": self.score,
            "criteria": self.criteria,
            "provenance": self.provenance,
            "tools_given": self.tools_given,
            "tool_calls_made": self.tool_calls_made,
            # Slice 918: additive and always present, null when the provider stamped
            # nothing, exactly as the two telemetry keys above behave. Emitted
            # unconditionally rather than only-when-set so a consumer can tell "reported
            # zero" from "never reported" without inferring it from a missing key.
            "stop_reason": self.stop_reason,
            "reasoning_chars": self.reasoning_chars,
            "failed_tool_calls": self.failed_tool_calls,
            # A degraded parse must be visible to JSON consumers too, or an
            # empty findings list reads as "the model found nothing" (issue #72).
            "fallback_used": self.fallback_used,
            # Slice 919 Part 2 (#97): always present, null when it does not apply (the
            # nothing-parsed branch, D8) — so a consumer can tell "does not apply" from
            # "never computed" without inferring it from a missing key, matching
            # stop_reason's convention above. Must agree with frontmatter's
            # verdictSource line for the same ReviewResult (design SC6).
            "verdictSource": self.verdict_source.value if self.verdict_source else None,
        }
        # Slice 266: added only when the gate fired, matching the markdown frontmatter, so
        # an un-gated run's JSON is unchanged.
        if self.tools_suppressed_reason is not None:
            payload["tools_suppressed_reason"] = self.tools_suppressed_reason
        return payload

    @property
    def structured_findings(self) -> list[StructuredFinding]:
        """Derive structured findings from parsed findings list."""
        result: list[StructuredFinding] = []
        for i, f in enumerate(self.findings, 1):
            result.append(
                StructuredFinding(
                    id=f"F{i:03d}",
                    severity=f.severity.value.lower(),
                    category=f.category or "uncategorized",
                    summary=f.title,
                    location=f.location or f.file_ref,
                )
            )
        return result

    @property
    def has_failures(self) -> bool:
        """True if any finding has FAIL severity."""
        return any(f.severity == Severity.FAIL for f in self.findings)

    @property
    def concern_count(self) -> int:
        """Number of findings with CONCERN severity."""
        return sum(1 for f in self.findings if f.severity == Severity.CONCERN)
