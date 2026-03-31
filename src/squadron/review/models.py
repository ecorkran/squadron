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
    # Prompt capture fields — populated at verbosity >= 2, excluded from to_dict()
    system_prompt: str | None = None
    user_prompt: str | None = None
    rules_content_used: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialize for JSON output."""
        return {
            "verdict": self.verdict.value,
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
        }

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
