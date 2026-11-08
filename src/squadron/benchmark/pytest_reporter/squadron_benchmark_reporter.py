"""pytest plugin that writes one JSONL record per collection failure and per test phase.

Injected into a sandbox's pytest with ``-p squadron_benchmark_reporter`` and ``PYTHONPATH``
(slice 421 D10). It runs inside the project's own environment, so it imports only the
standard library and ``pytest``; the harness-side constants it must agree with live in
``squadron.benchmark.python_failure`` and a test asserts they match.

The output path comes from ``SQUADRON_BENCHMARK_REPORT``. The file is created (truncated)
in ``pytest_configure``, so a file that exists proves the plugin loaded.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Generator
from types import TracebackType
from typing import Any

import pytest

REPORT_PATH_ENV = "SQUADRON_BENCHMARK_REPORT"
REPORT_KEYS = (
    "node_id",
    "phase",
    "outcome",
    "exc_type",
    "exc_module",
    "named_module_file",
    "frame_file",
    "frame_line",
)
_MOCK_FILE_SUFFIX = os.path.join("unittest", "mock.py")
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
_report_path: str | None = None


def pytest_configure(config: pytest.Config) -> None:
    global _report_path
    path = os.environ.get(REPORT_PATH_ENV)
    if not path:
        raise pytest.UsageError(f"{REPORT_PATH_ENV} is not set")
    _report_path = path
    with open(path, "w", encoding="utf-8"):
        pass  # truncate: the file existing proves this plugin loaded


def _write(record: dict[str, Any]) -> None:
    if _report_path is None:
        raise RuntimeError("squadron_benchmark_reporter wrote before pytest_configure ran")
    if tuple(record) != REPORT_KEYS:
        raise RuntimeError(f"report record keys {tuple(record)} differ from {REPORT_KEYS}")
    # One append per line: a run killed on timeout keeps every line written so far.
    with open(_report_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def _record(
    node_id: str,
    phase: str,
    outcome: str,
    *,
    exc_type: str | None = None,
    exc_module: str | None = None,
    named_module_file: str | None = None,
    frame_file: str | None = None,
    frame_line: int | None = None,
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "phase": phase,
        "outcome": outcome,
        "exc_type": exc_type,
        "exc_module": exc_module,
        "named_module_file": named_module_file,
        "frame_file": frame_file,
        "frame_line": frame_line,
    }


def _module_file(module: object) -> str | None:
    file = getattr(module, "__file__", None)
    return file if isinstance(file, str) else None


def _innermost(tb: TracebackType | None) -> TracebackType | None:
    while tb is not None and tb.tb_next is not None:
        tb = tb.tb_next
    return tb


def _named_module_file(exc: BaseException, tb: TracebackType | None) -> str | None:
    """The file of the module an ImportError or AttributeError names, when it names one."""
    if isinstance(exc, ImportError):
        if exc.path:
            return exc.path
        return _module_file(sys.modules.get(exc.name)) if exc.name else None
    if not isinstance(exc, AttributeError):
        return None
    obj: object = getattr(exc, "obj", None)
    if obj is not None and _module_file(obj):
        return _module_file(obj)
    # mock.patch of a missing attribute: AttributeError carries no obj, but the innermost
    # frame is the _patch object, whose target is the module the patch names.
    if tb is not None and tb.tb_frame.f_code.co_filename.endswith(_MOCK_FILE_SUFFIX):
        patcher: object = tb.tb_frame.f_locals.get("self")
        return _module_file(getattr(patcher, "target", None))
    return None


def _record_for_exception(
    node_id: str, phase: str, outcome: str, exc: BaseException, traceback: TracebackType | None
) -> dict[str, Any]:
    innermost = _innermost(traceback)
    return _record(
        node_id,
        phase,
        outcome,
        exc_type=type(exc).__qualname__,
        exc_module=type(exc).__module__,
        named_module_file=_named_module_file(exc, innermost),
        frame_file=innermost.tb_frame.f_code.co_filename if innermost else None,
        frame_line=innermost.tb_lineno if innermost else None,
    )


def _phase_outcome(report: pytest.TestReport) -> str:
    wasxfail = hasattr(report, "wasxfail")
    if report.outcome == "skipped" and wasxfail:
        return "xfailed"
    if report.outcome == "passed" and wasxfail:
        return "xpassed"
    return report.outcome


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, Any, None]:
    outcome: Any = yield
    report: pytest.TestReport = outcome.get_result()
    phase_outcome = _phase_outcome(report)
    excinfo = call.excinfo
    if excinfo is None:
        _write(_record(item.nodeid, call.when, phase_outcome))
        return
    _write(_record_for_exception(item.nodeid, call.when, phase_outcome, excinfo.value, excinfo.tb))


def pytest_collectreport(report: pytest.CollectReport) -> None:
    if not report.failed:
        return
    # A collect report keeps only the rendered error, so the type comes from the first
    # "E   module.Type: text" line; it only feeds the collection_error classification.
    crash = getattr(report.longrepr, "reprcrash", None)
    message: str = getattr(crash, "message", "") or ""
    if not message:
        # Colour output (FORCE_COLOR, --color=yes) wraps the "E" in escape codes.
        rendered = _ANSI_ESCAPE.sub("", str(report.longrepr))
        error_lines = [line[1:].strip() for line in rendered.splitlines() if line.startswith("E ")]
        message = error_lines[0] if error_lines else ""
    qualified = message.split(":", 1)[0].strip()
    module, _, name = qualified.rpartition(".")
    _write(
        _record(
            report.nodeid,
            "collect",
            "failed",
            exc_type=name or None,
            exc_module=module or ("builtins" if name else None),
            frame_file=getattr(crash, "path", None),
            frame_line=getattr(crash, "lineno", None),
        )
    )
