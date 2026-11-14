"""The fix report: the JSON object an agent ends its reply with (slice 423 D4).

The first JSON object in the reply is the report; the prompt tells the agent to write
no other.

``parse_fix_report`` checks the report's shape before anything is staged. Each defect
raises ``FixReportError`` naming one field, so a refusal tells the agent (or the person
reading the run) exactly what to correct. Unknown extra fields are ignored.
"""

from __future__ import annotations

import json
from typing import Any, cast

from pydantic import BaseModel

from squadron.pipeline.actions.dispatch_io import extract_json_object

BLOCKED_FIELD = "blocked"
#: Starts the message of a ``blocked`` report's refusal.
BLOCKED_PREFIX = "fix blocked:"
# The commit subject prefix the pipeline adds; a summary must not carry it.
_SUBJECT_PREFIX = "fix:"


class FixReportError(ValueError):
    """The reply holds no acceptable fix report; the message names the field at fault."""


class GateRun(BaseModel):
    """One gate command the agent ran after the change."""

    command: str
    exit_code: int


class FixReport(BaseModel):
    """A checked fix report."""

    summary: str
    failing_tests: list[str]
    failed_before_change: bool
    gates: list[GateRun]


def _is_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _check_blocked(raw: dict[str, Any]) -> None:
    """Raise for a ``blocked`` key: its reason when usable, else a defect naming it."""
    if BLOCKED_FIELD not in raw:
        return
    reason = raw[BLOCKED_FIELD]
    if not _is_text(reason):
        raise FixReportError(f"'{BLOCKED_FIELD}' must be a non-empty string reason, got {reason!r}")
    raise FixReportError(f"{BLOCKED_PREFIX} {str(reason).strip()}")


def _check_summary(raw: dict[str, Any]) -> str:
    summary = raw.get("summary")
    if not _is_text(summary):
        raise FixReportError("'summary' must be a non-empty string")
    text = str(summary).strip()
    if "\n" in text or "\r" in text:
        raise FixReportError("'summary' must be a single line")
    if text.lower().startswith(_SUBJECT_PREFIX):
        raise FixReportError(f"'summary' must not start with '{_SUBJECT_PREFIX}'; it is added")
    return text


def _check_failing_tests(raw: dict[str, Any]) -> list[str]:
    tests = raw.get("failing_tests")
    if not isinstance(tests, list) or not tests:
        raise FixReportError("'failing_tests' must be a non-empty list of test ids")
    items = cast(list[object], tests)
    if not all(_is_text(item) for item in items):
        raise FixReportError("'failing_tests' must be a non-empty list of test ids")
    return [str(item) for item in items]


def _check_gates(raw: dict[str, Any]) -> list[GateRun]:
    gates = raw.get("gates")
    if not isinstance(gates, list) or not gates:
        raise FixReportError("'gates' must be a non-empty list of {command, exit_code}")
    runs: list[GateRun] = []
    for index, entry in enumerate(cast(list[object], gates)):
        if not isinstance(entry, dict):
            raise FixReportError(f"'gates[{index}].command' must be a non-empty string")
        gate = cast(dict[str, object], entry)
        if not _is_text(gate.get("command")):
            raise FixReportError(f"'gates[{index}].command' must be a non-empty string")
        exit_code = gate.get("exit_code")
        # bool is an int subclass; True must not pass as exit code 1 or False as 0.
        if isinstance(exit_code, bool) or not isinstance(exit_code, int):
            raise FixReportError(f"'gates[{index}].exit_code' must be an integer")
        if exit_code != 0:
            command = str(gate["command"]).strip()
            raise FixReportError(f"'gates[{index}].exit_code' is {exit_code} for '{command}'")
        runs.append(GateRun(command=str(gate["command"]).strip(), exit_code=exit_code))
    return runs


def parse_fix_report(reply: str) -> FixReport:
    """The checked report in ``reply``; ``FixReportError`` names the first defect.

    A ``blocked`` report is checked first and raises with ``BLOCKED_PREFIX`` and its
    reason whatever else the object holds.
    """
    extracted = extract_json_object(reply)
    if extracted is None:
        raise FixReportError("no JSON object found in the reply; the fix report is missing")
    raw: dict[str, Any] = json.loads(extracted)
    _check_blocked(raw)
    summary = _check_summary(raw)
    failing_tests = _check_failing_tests(raw)
    if raw.get("failed_before_change") is not True:
        raise FixReportError(
            "'failed_before_change' must be true: the failing tests must be run and fail "
            "before the change"
        )
    return FixReport(
        summary=summary,
        failing_tests=failing_tests,
        failed_before_change=True,
        gates=_check_gates(raw),
    )
