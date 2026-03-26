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
    CONCERN = "CONCERN"
    FAIL = "FAIL"


class TemplateValidationError(Exception):
    """Raised when a template YAML file fails validation."""


@dataclass
class ReviewFinding:
    """A single finding from a review."""

    severity: Severity
    title: str
    description: str
    file_ref: str | None = None


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
                }
                for f in self.findings
            ],
            "template_name": self.template_name,
            "input_files": self.input_files,
            "timestamp": self.timestamp.isoformat(),
            "model": self.model,
        }

    @property
    def has_failures(self) -> bool:
        """True if any finding has FAIL severity."""
        return any(f.severity == Severity.FAIL for f in self.findings)

    @property
    def concern_count(self) -> int:
        """Number of findings with CONCERN severity."""
        return sum(1 for f in self.findings if f.severity == Severity.CONCERN)
