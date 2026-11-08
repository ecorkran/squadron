"""The test-first check: a hidden test must fail at the parent for the right reason (slice 422 D5).

Each hidden candidate runs at parent plus overlay. ``judge_parent_result`` maps one result
to a verdict by an ordered rule list over ``NodeOutcome`` and ``FailureKind``; the first
rule that matches wins. ``None`` means test-first holds.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol

from squadron.benchmark.adapter import (
    FailureKind,
    NodeOutcome,
    NodeResult,
    SandboxContext,
    SuiteRun,
    SuiteRunError,
    SuiteSelection,
)
from squadron.benchmark.fairness import FairnessVerdict, HarnessFailure
from squadron.metrology.benchmark_models import TestRejection

_logger = logging.getLogger(__name__)

Rule = tuple[Callable[[NodeResult], bool], TestRejection | None]

_SYMBOL_KINDS = (FailureKind.COLLECTION_ERROR, FailureKind.MISSING_SYMBOL)
_HOLDS_KINDS = (FailureKind.ASSERTION_FAILURE, FailureKind.PROJECT_EXCEPTION)

#: First match wins. Anything no rule matches (``other_exception``, ``skipped``, ``xfailed``,
#: ``xpassed``, ``not_run``) is undecidable.
PARENT_RULES: tuple[Rule, ...] = (
    (lambda result: result.failure_kind in _SYMBOL_KINDS, TestRejection.USES_SYMBOL_ADDED_BY_FIX),
    (lambda result: result.outcome is NodeOutcome.ERROR, TestRejection.UNDECIDABLE_FAILURE_AT_PARENT),
    (lambda result: result.outcome is NodeOutcome.PASSED, TestRejection.PASSES_AT_PARENT),
    (
        lambda result: result.outcome is NodeOutcome.FAILED and result.failure_kind in _HOLDS_KINDS,
        None,
    ),
)


class SuiteRunner(Protocol):
    """The part of ``BenchmarkAdapter`` the check uses."""

    def run_suite(self, ctx: SandboxContext, selection: SuiteSelection) -> SuiteRun: ...


def judge_parent_result(result: NodeResult) -> TestRejection | None:
    """The verdict for one node's result at parent plus overlay; ``None`` when test-first holds."""
    for matches, verdict in PARENT_RULES:
        if matches(result):
            return verdict
    return TestRejection.UNDECIDABLE_FAILURE_AT_PARENT


def _describe(result: NodeResult) -> str:
    kind = result.failure_kind.value if result.failure_kind is not None else "-"
    return f"{result.outcome.value}/{kind}"


def run_selection(
    runner: SuiteRunner, ctx: SandboxContext, selection: SuiteSelection
) -> Mapping[str, NodeResult]:
    """One suite run folded to ``node id -> result``; a timeout or ``SuiteRunError`` is a failure.

    Raises ``HarnessFailure`` (after an ERROR log) so a harness problem is never read as a test
    outcome. Shared by the test-first runs and the repeated reference runs.
    """
    try:
        run = runner.run_suite(ctx, selection)
    except SuiteRunError as exc:
        _logger.exception("suite run failed")
        raise HarnessFailure(f"suite run failed: {exc}") from exc
    if run.timed_out:
        detail = f"suite run timed out after {ctx.suite_timeout_s}s"
        _logger.error("fix-case harness failure: %s", detail)
        raise HarnessFailure(detail)
    return {result.node_id: result for result in run.results}


def _run_by_file(
    runner: SuiteRunner, ctx: SandboxContext, node_ids: tuple[str, ...]
) -> dict[str, NodeResult]:
    """One suite run per test file, so a file that fails to import cannot hide the others.

    Requested together, a collection error in one file leaves every other node unreported,
    and the missing nodes would read as collection errors of their own.
    """
    by_file: dict[str, list[str]] = {}
    for node_id in node_ids:
        by_file.setdefault(node_id.split("::", 1)[0], []).append(node_id)
    results: dict[str, NodeResult] = {}
    for group in by_file.values():
        results.update(run_selection(runner, ctx, SuiteSelection.nodes(tuple(group))))
    return results


def run_test_first(
    runner: SuiteRunner, ctx: SandboxContext, node_ids: Sequence[str], repeats: int
) -> dict[str, FairnessVerdict]:
    """Run ``node_ids`` ``repeats`` times at the current file state and judge each node.

    A node whose verdict differs between runs is ``flaky``. ``detail`` lists each run's
    outcome and failure kind. A timeout or ``SuiteRunError`` raises ``HarnessFailure``.
    Each repeat runs the files separately (see ``_run_by_file``).
    """
    ids = tuple(node_ids)
    runs = [_run_by_file(runner, ctx, ids) for _ in range(repeats)]
    verdicts: dict[str, FairnessVerdict] = {}
    for node_id in ids:
        results = [run[node_id] for run in runs]
        judged = {judge_parent_result(result) for result in results}
        detail = "runs: " + ", ".join(_describe(result) for result in results)
        rejection = judged.pop() if len(judged) == 1 else TestRejection.FLAKY
        verdicts[node_id] = FairnessVerdict(rejection=rejection, detail=detail)
    return verdicts
