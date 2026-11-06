"""Run a pytest suite in a sandbox and fold the reporter's JSONL into a ``SuiteRun`` (D10).

The reporter plugin is copied to ``<out>/plugin`` and loaded with ``-p`` and ``PYTHONPATH``,
so neither it nor its output touches the tree. A missing or unparseable report is an error
carrying pytest's stderr, never an empty pass.
"""

from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from squadron.benchmark.adapter import (
    FailureKind,
    NodeOutcome,
    NodeResult,
    SandboxContext,
    SuiteRun,
    SuiteRunError,
    SuiteSelection,
)
from squadron.benchmark.python_failure import (
    PHASE_SETUP,
    REPORT_PATH_ENV,
    REPORTER_MODULE,
    fold_records,
    reporter_plugin_dir,
)
from squadron.core.process_runner import ProcessResult, ProcessTimedOutError

_logger = logging.getLogger(__name__)

REPORT_FILE = "report.jsonl"
PLUGIN_SUBDIR = "plugin"
# pytest exit codes: 0 all passed, 1 some failed, 4 usage error (ids not found), 5 none collected.
EXIT_TESTS_FAILED = 1
EXIT_USAGE_ERROR = 4
EXIT_NO_TESTS = 5
_COMPLETE_EXIT_CODES = (0, EXIT_TESTS_FAILED, EXIT_USAGE_ERROR, EXIT_NO_TESTS)
NOT_COLLECTED = "not collected"


def _fail(message: str) -> SuiteRunError:
    _logger.error("suite run failed: %s", message)
    return SuiteRunError(message)


def _pytest_argv(python: Path, selection: SuiteSelection) -> list[str]:
    argv = [
        str(python),
        "-m",
        "pytest",
        "-p",
        REPORTER_MODULE,
        "-p",
        "no:cacheprovider",
        # One broken module must not hide every other node's result.
        "--continue-on-collection-errors",
    ]
    for node_id in selection.deselect:
        argv += ["--deselect", node_id]
    return argv + list(selection.node_ids or ())


def _read_report(report: Path, stderr: str) -> list[dict[str, Any]]:
    if not report.is_file():
        raise _fail(f"the reporter plugin never loaded (no report file); pytest stderr: {stderr}")
    records: list[dict[str, Any]] = []
    for number, line in enumerate(report.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise _fail(
                f"report line {number} does not parse ({exc}); pytest stderr: {stderr}"
            ) from exc
    return records


def _check_exit(
    records: Sequence[object], selection: SuiteSelection, exit_code: int, stderr: str
) -> None:
    """Reject exit codes and empty reports that cannot be a complete answer."""
    if exit_code not in _COMPLETE_EXIT_CODES:
        raise _fail(f"pytest exited {exit_code}; stderr: {stderr}")
    if records:
        return
    empty_is_valid = (selection.node_ids is None and exit_code == EXIT_NO_TESTS) or (
        selection.node_ids is not None and exit_code == EXIT_USAGE_ERROR
    )
    if not empty_is_valid:
        raise _fail(f"empty report at pytest exit {exit_code}; stderr: {stderr}")


def _result_for_requested(
    node_id: str, folded: Mapping[str, NodeResult], timed_out: bool
) -> NodeResult:
    if node_id in folded:
        return folded[node_id]
    file_error = folded.get(node_id.split("::", 1)[0])
    if file_error is not None and file_error.failure_kind is FailureKind.COLLECTION_ERROR:
        return NodeResult(
            node_id,
            NodeOutcome.ERROR,
            FailureKind.COLLECTION_ERROR,
            file_error.phase,
            file_error.exception_type,
        )
    if timed_out:
        return NodeResult(node_id, NodeOutcome.NOT_RUN)
    return NodeResult(
        node_id, NodeOutcome.ERROR, FailureKind.COLLECTION_ERROR, exception_type=NOT_COLLECTED
    )


def _mark_incomplete(results: Mapping[str, NodeResult]) -> dict[str, NodeResult]:
    """After a timeout, a node that passed setup but never reported its call did not finish."""
    return {
        node_id: NodeResult(node_id, NodeOutcome.NOT_RUN)
        if result.phase == PHASE_SETUP and result.outcome is NodeOutcome.PASSED
        else result
        for node_id, result in results.items()
    }


def run_pytest_suite(
    ctx: SandboxContext, selection: SuiteSelection, env: Mapping[str, str]
) -> SuiteRun:
    plugin_dir = ctx.output_dir / PLUGIN_SUBDIR
    plugin_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(reporter_plugin_dir() / f"{REPORTER_MODULE}.py", plugin_dir)
    report = ctx.output_dir / REPORT_FILE
    child_env = {**env, "PYTHONPATH": str(plugin_dir), REPORT_PATH_ENV: str(report)}
    argv = _pytest_argv(ctx.tree / ".venv" / "bin" / "python", selection)
    timed_out = False
    result: ProcessResult | None = None
    try:
        result = ctx.runner.run(
            argv, cwd=str(ctx.tree), timeout=ctx.suite_timeout_s, env=child_env, replace_env=True
        )
    except ProcessTimedOutError:
        timed_out = True
    stderr = result.stderr if result is not None else ""
    records = _read_report(report, stderr)
    if result is not None:
        _check_exit(records, selection, result.returncode, stderr)
    folded = fold_records(records, ctx.tree)
    if timed_out:
        folded = _mark_incomplete(folded)
    if selection.node_ids is None:
        return SuiteRun(tuple(folded.values()), timed_out)
    requested = tuple(_result_for_requested(node, folded, timed_out) for node in selection.node_ids)
    return SuiteRun(requested, timed_out)
