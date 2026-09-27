"""Batch report — per-item outcomes of an ``each`` step (slice 195 D9).

Every ``each`` step records one :class:`BatchItemRecord` per item and ends by
writing a Markdown report beside the run state file, so an unattended batch
leaves one document that says which items need a human.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from squadron.documents.frontmatter import FRONTMATTER_LINE_WIDTH
from squadron.pipeline.models import ActionResult

if TYPE_CHECKING:
    from squadron.pipeline.executor import StepResult


class ItemOutcome(StrEnum):
    """How one item of a batch ended."""

    PASSED = "passed"
    ACCEPTED = "accepted"
    FLAGGED = "flagged"


_SECTION_TITLES: dict[ItemOutcome, str] = {
    ItemOutcome.FLAGGED: "Flagged for PM",
    ItemOutcome.ACCEPTED: "Accepted",
    ItemOutcome.PASSED: "Passed",
}


@dataclass
class BatchItemRecord:
    """One item's outcome, with what a reader needs to follow it up."""

    index: str
    name: str
    outcome: ItemOutcome
    reason: str | None = None
    final_verdict: str | None = None
    review_file: str | None = None

    @classmethod
    def from_item(
        cls,
        item: dict[str, object],
        position: int,
        step_results: list[StepResult],
        failure_reason: str | None = None,
    ) -> BatchItemRecord:
        """Build the record for *item* (the ``position``-th, 0-based) from its
        inner step results.

        *failure_reason* is set when the item was pre-flagged, failed, or
        paused — any of which makes it FLAGGED. Otherwise an ``accepted`` loop
        makes it ACCEPTED, and anything else PASSED.
        """
        actions = [r for step in step_results for r in step.action_results]
        if failure_reason is not None:
            outcome = ItemOutcome.FLAGGED
        elif any(step.accepted for step in step_results):
            outcome = ItemOutcome.ACCEPTED
        else:
            outcome = ItemOutcome.PASSED
        return cls(
            index=str(item.get("index", f"#{position + 1}")),
            name=str(item.get("name", "")),
            outcome=outcome,
            reason=failure_reason,
            final_verdict=_last_verdict(actions),
            review_file=_last_review_file(actions),
        )

    def render_line(self) -> str:
        label = f"{self.index} {self.name}".strip()
        details: list[str] = []
        if self.reason:
            details.append(self.reason)
        if self.final_verdict:
            details.append(f"verdict {self.final_verdict}")
        if self.review_file:
            details.append(f"review: {self.review_file}")
        return f"- {label} — {'; '.join(details)}" if details else f"- {label}"


def _last_verdict(actions: list[ActionResult]) -> str | None:
    return next((r.verdict for r in reversed(actions) if r.verdict is not None), None)


def _last_review_file(actions: list[ActionResult]) -> str | None:
    for result in reversed(actions):
        review_file = result.outputs.get("review_file")
        if review_file:
            return str(review_file)
    return None


@dataclass
class BatchReport:
    """All item records of one ``each`` step in one run."""

    pipeline: str
    run_id: str
    step_name: str
    plan: str | None = None
    records: list[BatchItemRecord] = field(default_factory=lambda: [])
    written_to: Path | None = None

    def count(self, outcome: ItemOutcome) -> int:
        return sum(1 for record in self.records if record.outcome is outcome)

    def flagged(self) -> list[BatchItemRecord]:
        return [r for r in self.records if r.outcome is ItemOutcome.FLAGGED]

    def summary_line(self) -> str:
        counts = ", ".join(f"{self.count(o)} {o.value}" for o in ItemOutcome)
        return f"{self.pipeline} {self.step_name}: {len(self.records)} items — {counts}"

    def render(self) -> str:
        """The report as Markdown: frontmatter counts, then flagged, accepted
        and passed sections, flagged first."""
        frontmatter: dict[str, object] = {
            "docType": "batch-report",
            "pipeline": self.pipeline,
            "runId": self.run_id,
        }
        if self.plan is not None:
            frontmatter["plan"] = self.plan
        frontmatter.update({o.value: self.count(o) for o in ItemOutcome})
        heading = f"# Batch report: {self.pipeline}"
        if self.plan is not None:
            heading += f" (plan {self.plan})"
        lines = [
            "---",
            yaml.safe_dump(frontmatter, sort_keys=False, width=FRONTMATTER_LINE_WIDTH).rstrip(),
            "---",
            "",
            heading,
        ]
        for outcome in (ItemOutcome.FLAGGED, ItemOutcome.ACCEPTED, ItemOutcome.PASSED):
            section = [r for r in self.records if r.outcome is outcome]
            lines += ["", f"## {_SECTION_TITLES[outcome]}"]
            lines += [r.render_line() for r in section] or ["- none"]
        return "\n".join(lines) + "\n"

    def path(self, runs_dir: Path) -> Path:
        return runs_dir / f"{self.run_id}.{self.step_name}.report.md"

    def write(self, runs_dir: Path) -> Path:
        """Write the report beside the run state file; return its path."""
        target = self.path(runs_dir)
        target.write_text(self.render(), encoding="utf-8")
        self.written_to = target
        return target
