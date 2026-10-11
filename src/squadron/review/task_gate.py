"""Deterministic task-file gate: flag merge steps before any model review (slice 933).

Merging is a Phase 7 action; a task file that schedules it as a checklist item or
heading fails its tasks review outright, with no model call. Pure functions only:
file reads live in ``task_gate_files`` so this module stays I/O-free.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from squadron.review.models import (
    ReviewFinding,
    ReviewResult,
    Severity,
    Verdict,
    VerdictSource,
)
from squadron.review.templates import BuiltinReviewTemplate

# The FAIL result's model field: no model ran, the gate did.
TASK_GATE_MODEL = "squadron-task-gate"
TASK_GATE_CATEGORY = "merge-step"
# The review inputs key holding the task file a part reviews.
INPUT_KEY = "input"

# How many words after the merge word a git object may appear and still count.
MERGE_OBJECT_WINDOW = 4

# Words that name a git object a merge step would target. Bare "slice" is not one.
GIT_OBJECTS: tuple[str, ...] = ("slice branch", "integration branch", "branch", "main", "target")

# Verbs that, joined to the merge word, make it a release step.
RELEASE_VERBS: tuple[str, ...] = ("tag", "release", "publish", "push")

# A hyphen or underscore is not a word boundary: merge-base, --no-merges and
# merge_gate never contain the word.
_EDGE_BEFORE = r"(?<![\w-])"
_EDGE_AFTER = r"(?![\w-])"
_MERGE = rf"{_EDGE_BEFORE}merge[sd]?{_EDGE_AFTER}"
_OBJECT = (
    rf"{_EDGE_BEFORE}(?:"
    + "|".join(re.escape(obj).replace(r"\ ", r"\s+") for obj in GIT_OBJECTS)
    + rf"){_EDGE_AFTER}"
)
_RELEASE = rf"(?:{'|'.join(RELEASE_VERBS)}){_EDGE_AFTER}"
_WORD = r"[\w'-]+"
_GAP = r"[^\w-]+"

# Item labels such as "T14 —", "4.1" or "Task 5 —" ahead of the first word.
_LABEL = re.compile(r"^(?:(?:task\s*|t)?\d+(?:\.\d+)*[.)]?\s*(?:[—–:-]+\s*)?)", re.IGNORECASE)
_CHECKLIST = re.compile(r"^\s*[-*+]\s+\[[ xX]\]\s+(?P<body>.*)$")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(?P<body>.*)$")
_FRONTMATTER_FENCE = "---"


@dataclass(frozen=True)
class MergeStepLine:
    """One flagged line: its 1-based line number and stripped text."""

    line_number: int
    text: str


@dataclass(frozen=True)
class MergePattern:
    """A named rule in the pattern table, matched against normalized item text."""

    name: str
    regex: re.Pattern[str]


def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


# The single place that defines what a merge step is. R1 is matched against the
# item with its label stripped; the rest search the whole item.
MERGE_PATTERNS: tuple[MergePattern, ...] = (
    MergePattern(
        "leading_merge_word",
        _compile(rf"^{_MERGE}(?:\s+(?:to|into){_EDGE_AFTER}|\s+{_OBJECT}|\s*:|\s*[.!]?\s*$)"),
    ),
    MergePattern(
        "joined_release_verb",
        _compile(
            rf"{_EDGE_BEFORE}(?:commit\s*,?\s+and|then)\s+{_MERGE}"
            rf"|{_MERGE}\s*,?\s+(?:and\s+)?{_RELEASE}"
        ),
    ),
    MergePattern(
        "git_object_window",
        _compile(rf"{_MERGE}(?:{_GAP}{_WORD}){{0,{MERGE_OBJECT_WINDOW - 1}}}?{_GAP}{_OBJECT}"),
    ),
    MergePattern(
        "merged_success_criterion",
        _compile(rf"{_EDGE_BEFORE}(?:branch|slice)\s+merged{_EDGE_AFTER}"),
    ),
)


def _normalize(body: str) -> str:
    """Drop bold markers and turn backticks into spaces, so `main` reads as main."""
    return body.replace("**", "").replace("`", " ").strip()


def _is_merge_step(body: str) -> bool:
    text = _normalize(body)
    unlabeled = _LABEL.sub("", text, count=1)
    return any(pattern.regex.search(unlabeled) for pattern in MERGE_PATTERNS)


def _candidate_body(line: str) -> str | None:
    match = _CHECKLIST.match(line) or _HEADING.match(line)
    return match.group("body") if match else None


def _frontmatter_end(lines: list[str]) -> int:
    """Index of the first line after leading YAML frontmatter (0 if none)."""
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        return 0
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_FENCE:
            return index + 1
    return len(lines)


def scan_merge_steps(text: str) -> list[MergeStepLine]:
    """Return every checklist item or heading in ``text`` that is a merge step.

    Frontmatter and prose are never flagged.
    """
    lines = text.splitlines()
    hits: list[MergeStepLine] = []
    for index in range(_frontmatter_end(lines), len(lines)):
        body = _candidate_body(lines[index])
        if body is not None and _is_merge_step(body):
            hits.append(MergeStepLine(line_number=index + 1, text=lines[index].strip()))
    return hits


def _hit_finding(path: str, hit: MergeStepLine) -> ReviewFinding:
    return ReviewFinding(
        severity=Severity.FAIL,
        title=f"Merge step at line {hit.line_number}",
        description=(
            f"Line {hit.line_number} schedules a merge: `{hit.text}`. Merging happens in "
            f"Phase 7 after code review passes; a task file must not contain it."
        ),
        file_ref=path,
        category=TASK_GATE_CATEGORY,
        location=f"{path}:{hit.line_number}",
    )


def _gate_result(inputs: Mapping[str, str], hits: list[MergeStepLine]) -> ReviewResult:
    path = inputs[INPUT_KEY]
    lines = ", ".join(str(hit.line_number) for hit in hits)
    return ReviewResult(
        verdict=Verdict.FAIL,
        findings=[_hit_finding(path, hit) for hit in hits],
        raw_output=(f"The task-file gate found merge steps in {path} (lines {lines}). No model ran."),
        template_name=BuiltinReviewTemplate.TASKS,
        input_files=dict(inputs),
        model=TASK_GATE_MODEL,
        verdict_source=VerdictSource.IMPOSED,
        tools_given=None,
        tool_calls_made=None,
    )


def merge_gate_results(
    scans: Sequence[tuple[Mapping[str, str], list[MergeStepLine]]],
) -> dict[str, ReviewResult]:
    """Build a FAIL result for each part with hits, keyed by its ``input`` path.

    Each scan pairs one part's review inputs dict with that part's hits. Empty
    when every part is clean.
    """
    return {inputs[INPUT_KEY]: _gate_result(inputs, hits) for inputs, hits in scans if hits}
