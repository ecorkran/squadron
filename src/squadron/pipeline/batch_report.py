"""Batch report — per-item outcomes of an ``each`` step (slice 195 D9).

Every ``each`` step records one :class:`BatchItemRecord` per item and ends by
writing a Markdown report beside the run state file, so an unattended batch
leaves one document that says which items need a human.
"""

from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, cast

import yaml

from squadron.documents.frontmatter import FRONTMATTER_LINE_WIDTH
from squadron.pipeline.actions import ActionType
from squadron.pipeline.actions.review_outputs import review_file, unsaved_parts
from squadron.pipeline.branch_ops import BRANCH_OUTPUT
from squadron.pipeline.models import ActionResult

if TYPE_CHECKING:
    from squadron.pipeline.executor import StepResult

_logger = logging.getLogger(__name__)

# Goes up whenever the record shape or the FlagKind set changes (slice 197 D7).
REPORT_SCHEMA_VERSION = 1
REPORT_DOC_TYPE = "batch-report"
# ``{run_id}.{step}.report.json`` sits in the runs dir beside run state files.
REPORT_JSON_SUFFIX = ".report.json"

# BatchItemRecord attribute → report.json key (camelCase, as review frontmatter).
_JSON_KEYS: dict[str, str] = {
    "index": "index",
    "name": "name",
    "outcome": "outcome",
    "flag_kind": "flagKind",
    "failed_step": "failedStep",
    "reason": "reason",
    "final_verdict": "finalVerdict",
    "review_file": "reviewFile",
    "unsaved_parts": "unsavedParts",
    "branch": "branch",
    "decision": "decision",
    "resumed_at": "resumedAt",
}


class BatchReportLoadError(ValueError):
    """A ``report.json`` is missing, unparseable, or of another schema version."""


class ItemOutcome(StrEnum):
    """How one item of a batch ended."""

    PASSED = "passed"
    ACCEPTED = "accepted"
    FLAGGED = "flagged"
    NOT_RUN = "not_run"  # a halt ended the batch before this item (slice 197 D7)


class FlagKind(StrEnum):
    """Why an item was flagged; routing reads this, never ``reason`` (slice 197 D7)."""

    NOT_READY = "not_ready"  # source flag_reason (D2), except dependency rows
    DEPENDENCY = "dependency"  # flagged or not-designed dependency
    REVIEW_UNRESOLVED = "review_unresolved"  # loop exhausted below accept-threshold
    BRANCH_CONFLICT = "branch_conflict"  # catch-up or merge stopped on a git conflict
    STEP_FAILED = "step_failed"  # any other failed step (implement dispatch, devlog, …)
    PAUSED = "paused"  # a checkpoint paused the item


class ItemDecision(StrEnum):
    """A decision applied to one flagged item by item resume (slice 197 D8)."""

    RETRY = "retry"
    ACCEPT = "accept"


# Report sections in render order: the items a human owes something first.
_SECTION_TITLES: dict[ItemOutcome, str] = {
    ItemOutcome.FLAGGED: "Flagged for PM",
    ItemOutcome.NOT_RUN: "Not run",
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
    unsaved_parts: list[str] = field(default_factory=lambda: [])
    flag_kind: FlagKind | None = None
    failed_step: str | None = None  # the failing step's name; None for a pre-flag
    branch: str | None = None  # the slice branch, when the item entered one
    decision: ItemDecision | None = None
    resumed_at: str | None = None

    @classmethod
    def from_item(
        cls,
        item: dict[str, object],
        position: int,
        step_results: list[StepResult],
        failure_reason: str | None = None,
        *,
        flag_kind: FlagKind | None = None,
        failed_step: str | None = None,
    ) -> BatchItemRecord:
        """Build the record for *item* (the ``position``-th, 0-based) from its
        inner step results.

        *failure_reason* is set when the item was pre-flagged, failed, or
        paused — any of which makes it FLAGGED, with *flag_kind* set where the
        flag was raised. Otherwise an ``accepted`` loop makes it ACCEPTED, and
        anything else PASSED.
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
            unsaved_parts=_last_review_unsaved_parts(actions),
            flag_kind=flag_kind if failure_reason is not None else None,
            failed_step=failed_step if failure_reason is not None else None,
            branch=_slice_branch(actions),
        )

    @classmethod
    def not_run(cls, item: dict[str, object], position: int, reason: str) -> BatchItemRecord:
        """The record of an item a halted batch never reached (slice 197 D7)."""
        return cls(
            index=str(item.get("index", f"#{position + 1}")),
            name=str(item.get("name", "")),
            outcome=ItemOutcome.NOT_RUN,
            reason=reason,
        )

    def to_json(self) -> dict[str, object]:
        return {key: getattr(self, attr) for attr, key in _JSON_KEYS.items()}

    @classmethod
    def from_json(cls, data: dict[str, object]) -> BatchItemRecord:
        values = {attr: data.get(key) for attr, key in _JSON_KEYS.items()}
        flag_kind, decision = values["flag_kind"], values["decision"]
        return cls(
            index=str(values["index"]),
            name=str(values["name"]),
            outcome=ItemOutcome(str(values["outcome"])),
            reason=_optional_str(values["reason"]),
            final_verdict=_optional_str(values["final_verdict"]),
            review_file=_optional_str(values["review_file"]),
            unsaved_parts=[str(p) for p in cast(list[object], values["unsaved_parts"] or [])],
            flag_kind=FlagKind(str(flag_kind)) if flag_kind is not None else None,
            failed_step=_optional_str(values["failed_step"]),
            branch=_optional_str(values["branch"]),
            decision=ItemDecision(str(decision)) if decision is not None else None,
            resumed_at=_optional_str(values["resumed_at"]),
        )

    def render_line(self) -> str:
        label = f"{self.index} {self.name}".strip()
        details: list[str] = []
        if self.flag_kind:
            at = f" at {self.failed_step}" if self.failed_step else ""
            details.append(f"{self.flag_kind}{at}")
        if self.reason:
            details.append(self.reason)
        if self.final_verdict:
            details.append(f"verdict {self.final_verdict}")
        if self.branch:
            details.append(f"branch {self.branch}")
        if self.decision:
            details.append(f"decision {self.decision} at {self.resumed_at}")
        if self.review_file:
            details.append(f"review: {self.review_file}")
        if self.unsaved_parts:
            details.append(f"unsaved: {', '.join(self.unsaved_parts)}")
        return f"- {label} — {'; '.join(details)}" if details else f"- {label}"


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)


def _slice_branch(actions: list[ActionResult]) -> str | None:
    """The slice branch a branch action entered or merged, when one ran successfully."""
    for result in actions:
        if result.action_type == ActionType.BRANCH and result.success:
            branch = result.outputs.get(BRANCH_OUTPUT)
            if branch:
                return str(branch)
    return None


def _last_verdict(actions: list[ActionResult]) -> str | None:
    return next((r.verdict for r in reversed(actions) if r.verdict is not None), None)


def _last_review_file(actions: list[ActionResult]) -> str | None:
    for result in reversed(actions):
        path = review_file(result)
        if path:
            return path
    return None


def _last_review_unsaved_parts(actions: list[ActionResult]) -> list[str]:
    """Parts of the item's last review that never reached disk (slice 930)."""
    last_review = next((r for r in reversed(actions) if r.action_type == ActionType.REVIEW), None)
    return unsaved_parts(last_review) if last_review is not None else []


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
        """The report as Markdown: frontmatter counts, then flagged, not run,
        accepted and passed sections, flagged first."""
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
        for outcome in _SECTION_TITLES:
            section = [r for r in self.records if r.outcome is outcome]
            lines += ["", f"## {_SECTION_TITLES[outcome]}"]
            lines += [r.render_line() for r in section] or ["- none"]
        return "\n".join(lines) + "\n"

    def to_json(self) -> dict[str, object]:
        """The report as ``report.json`` content (slice 197 D7)."""
        return {
            "docType": REPORT_DOC_TYPE,
            "schemaVersion": REPORT_SCHEMA_VERSION,
            "pipeline": self.pipeline,
            "runId": self.run_id,
            "stepName": self.step_name,
            "plan": self.plan,
            "counts": {o.value: self.count(o) for o in ItemOutcome},
            "items": [r.to_json() for r in self.records],
        }

    def path(self, runs_dir: Path) -> Path:
        return runs_dir / f"{self.run_id}.{self.step_name}.report.md"

    def json_path(self, runs_dir: Path) -> Path:
        return runs_dir / f"{self.run_id}.{self.step_name}{REPORT_JSON_SUFFIX}"

    def write(self, runs_dir: Path) -> Path:
        """Write the Markdown and JSON reports beside the run state file; return the
        Markdown path. Each file is replaced atomically, so a reader never sees a partial
        one and a failed write leaves the previous report intact."""
        target = self.path(runs_dir)
        _write_atomic(target, self.render())
        _write_atomic(self.json_path(runs_dir), json.dumps(self.to_json(), indent=2) + "\n")
        self.written_to = target
        return target

    @classmethod
    def load(cls, path: Path) -> BatchReport:
        """Read a ``report.json`` back; any problem raises ``BatchReportLoadError``."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise BatchReportLoadError(f"batch report {path} not found") from None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BatchReportLoadError(f"batch report {path} is unreadable: {exc}") from exc
        if not isinstance(data, dict):
            raise BatchReportLoadError(f"batch report {path} is not a JSON object")
        report = cast(dict[str, object], data)
        version = report.get("schemaVersion")
        if version != REPORT_SCHEMA_VERSION:
            raise BatchReportLoadError(
                f"batch report {path} has schemaVersion {version}; "
                f"this squadron reads schemaVersion {REPORT_SCHEMA_VERSION}"
            )
        try:
            items = cast(list[dict[str, object]], report["items"])
            return cls(
                pipeline=str(report["pipeline"]),
                run_id=str(report["runId"]),
                step_name=str(report["stepName"]),
                plan=_optional_str(report.get("plan")),
                records=[BatchItemRecord.from_json(item) for item in items],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BatchReportLoadError(f"batch report {path} is malformed: {exc!r}") from exc


def _write_atomic(target: Path, text: str) -> None:
    """Write *text* to a temp file beside *target*, then rename it over *target*."""
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=target.parent, prefix=f".{target.name}.", delete=False
        ) as handle:
            handle.write(text)
            temp = Path(handle.name)
        temp.replace(target)
    except OSError:
        _logger.exception("cannot write batch report %s", target)
        raise


@dataclass
class ItemRerun:
    """One item of a finished ``each`` step, rerun on a decision (slice 197 D8).

    The executor runs only ``item`` (the source is not evaluated again), then replaces
    that index's record in ``report`` with the new outcome and writes the report. The
    new record is left in ``record`` for the caller.
    """

    item: dict[str, object]
    report: BatchReport
    decision: ItemDecision
    resumed_at: str
    record: BatchItemRecord | None = None

    def replace(self, record: BatchItemRecord) -> None:
        """Put *record* in the place of the item's old record, with the decision on it."""
        record.decision = self.decision
        record.resumed_at = self.resumed_at
        records = self.report.records
        position = next(i for i, r in enumerate(records) if r.index == record.index)
        records[position] = record
        self.record = record
