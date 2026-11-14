"""Tests for the fix report parser (slice 423 D4)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from squadron.pipeline.fix_report import BLOCKED_PREFIX, FixReportError, parse_fix_report


def _report(**overrides: Any) -> dict[str, Any]:
    report: dict[str, Any] = {
        "summary": "handle missing template directory",
        "failing_tests": ["tests/test_templates.py::test_missing_dir"],
        "failed_before_change": True,
        "gates": [{"command": "ruff check", "exit_code": 0}],
    }
    report.update(overrides)
    return report


def test_valid_report_inside_prose() -> None:
    reply = f"All done.\n\n{json.dumps(_report())}\n\nLet me know."
    parsed = parse_fix_report(reply)
    assert parsed.summary == "handle missing template directory"
    assert parsed.failing_tests == ["tests/test_templates.py::test_missing_dir"]
    assert parsed.failed_before_change is True
    assert [(gate.command, gate.exit_code) for gate in parsed.gates] == [("ruff check", 0)]


def test_valid_report_inside_code_fence() -> None:
    reply = f"Report:\n```json\n{json.dumps(_report(), indent=2)}\n```\n"
    assert parse_fix_report(reply).summary == "handle missing template directory"


def test_extra_fields_are_ignored() -> None:
    assert parse_fix_report(json.dumps(_report(notes="x", extra={"a": 1}))).gates


def test_report_after_unrelated_prose() -> None:
    reply = "I read the issue, then edited things. Now the report: " + json.dumps(_report())
    assert parse_fix_report(reply).failing_tests


def test_summary_is_stripped() -> None:
    assert parse_fix_report(json.dumps(_report(summary="  tidy up  "))).summary == "tidy up"


@pytest.mark.parametrize(
    ("reply", "field"),
    [
        ("no report here at all", "JSON object"),
        ("{not json", "JSON object"),
        (json.dumps(_report(summary="")), "summary"),
        (json.dumps(_report(summary="  ")), "summary"),
        (json.dumps(_report(summary=3)), "summary"),
        (json.dumps(_report(summary="one\ntwo")), "summary"),
        (json.dumps(_report(summary="fix: add thing")), "summary"),
        (json.dumps(_report(summary="Fix: add thing")), "summary"),
        (json.dumps(_report(failing_tests=[])), "failing_tests"),
        (json.dumps(_report(failing_tests="tests/a.py")), "failing_tests"),
        (json.dumps(_report(failing_tests=[""])), "failing_tests"),
        (json.dumps(_report(failed_before_change=False)), "failed_before_change"),
        (json.dumps(_report(failed_before_change="true")), "failed_before_change"),
        (json.dumps(_report(failed_before_change=1)), "failed_before_change"),
        (
            json.dumps({k: v for k, v in _report().items() if k != "failed_before_change"}),
            "failed_before_change",
        ),
        (json.dumps(_report(gates=[])), "gates"),
        (json.dumps(_report(gates="ruff")), "gates"),
        (json.dumps(_report(gates=["ruff"])), "command"),
        (json.dumps(_report(gates=[{"exit_code": 0}])), "command"),
        (json.dumps(_report(gates=[{"command": "ruff", "exit_code": 1}])), "exit_code"),
        (json.dumps(_report(gates=[{"command": "ruff", "exit_code": "0"}])), "exit_code"),
        (json.dumps(_report(gates=[{"command": "ruff", "exit_code": False}])), "exit_code"),
        (json.dumps(_report(gates=[{"command": "ruff"}])), "exit_code"),
        (json.dumps({k: v for k, v in _report().items() if k != "summary"}), "summary"),
    ],
)
def test_each_defect_names_its_field(reply: str, field: str) -> None:
    with pytest.raises(FixReportError) as info:
        parse_fix_report(reply)
    assert field in str(info.value)
    assert not str(info.value).startswith(BLOCKED_PREFIX)


def test_one_error_names_one_field() -> None:
    with pytest.raises(FixReportError) as info:
        parse_fix_report(json.dumps(_report(summary="", failing_tests=[], gates=[])))
    message = str(info.value)
    assert "summary" in message
    assert "failing_tests" not in message
    assert "gates" not in message


def test_blocked_report_with_only_blocked() -> None:
    with pytest.raises(FixReportError) as info:
        parse_fix_report(json.dumps({"blocked": "needs a decision on the API"}))
    assert str(info.value) == f"{BLOCKED_PREFIX} needs a decision on the API"


def test_blocked_report_with_every_other_field() -> None:
    reply = json.dumps(_report(blocked="cannot reproduce without credentials"))
    with pytest.raises(FixReportError) as info:
        parse_fix_report(reply)
    assert str(info.value) == f"{BLOCKED_PREFIX} cannot reproduce without credentials"


@pytest.mark.parametrize("value", [None, "", "  ", 3, ["x"], True])
def test_unusable_blocked_value_is_a_defect_naming_blocked(value: object) -> None:
    with pytest.raises(FixReportError) as info:
        parse_fix_report(json.dumps(_report(blocked=value)))
    assert "blocked" in str(info.value)
    assert not str(info.value).startswith(BLOCKED_PREFIX)
