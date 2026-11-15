"""The test and measurement steps of a grade (slice 425 D1, D2, D12).

Run after the tree is prepared (``grade_prepare``): the baseline of the case's reference, the
producer's new tests as a separate signal, and the snapshot with its lint and type totals.
An empty id list never reaches ``run_suite``, because pytest given no ids runs every test.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence

from squadron.benchmark.adapter import NodeOutcome, NodeResult, SuiteRunError, SuiteSelection
from squadron.benchmark.grade_deps import MissingReferenceGrade, absent
from squadron.benchmark.grade_run import GradeRun, run_git
from squadron.metrology.benchmark_models import GraderCommandKind
from squadron.metrology.grade_models import MAX_LISTED_ITEMS, GradeAbsence, SnapshotRef
from squadron.metrology.snapshot_models import CodeSnapshot, Measurement, SnapshotMetric

_logger = logging.getLogger(__name__)

#: The snapshot metric each checking grader command is measured by.
CHECK_METRICS: dict[GraderCommandKind, SnapshotMetric] = {
    GraderCommandKind.LINT: SnapshotMetric.LINT_COUNT,
    GraderCommandKind.TYPECHECK: SnapshotMetric.TYPE_ERRORS,
}
#: Outcomes that count as a failure of a selected node (D2); skipped and xfailed do not.
FAILING_OUTCOMES = frozenset({NodeOutcome.FAILED, NodeOutcome.ERROR, NodeOutcome.NOT_RUN})


def load_baseline(run: GradeRun) -> None:
    """Read the case's reference grade and its start node ids; a replay needs both (D8)."""
    deps, target = run.deps, run.target
    reference = deps.store.get_reference_grade(
        run.case.case_id, deps.grader.digest, target.environment_digest
    )
    if reference is None or reference.baseline_nodes is None:
        _logger.error(
            "no usable reference grade for case %s in environment %s",
            run.case.case_id,
            target.environment_digest[:12],
        )
        raise MissingReferenceGrade(run.case.case_id, target.environment_digest)
    run.baseline = reference
    run.start_ids = tuple(json.loads(deps.store.nodes.get(reference.baseline_nodes)))


def run_nodes(run: GradeRun, ids: Sequence[str], step: str) -> tuple[NodeResult, ...]:
    """Run exactly *ids*; an empty list runs nothing. A timeout or a run error is an absence.

    Every requested id has exactly one result: one the suite did not report is ``not_run``,
    so no count can silently shrink when the adapter drops a node.
    """
    if not ids:
        return ()
    try:
        suite = run.sandbox.run_suite(SuiteSelection.nodes(tuple(ids)))
    except SuiteRunError as exc:
        raise absent(GradeAbsence.SUITE_ERROR, f"{step}: {exc}") from exc
    if suite.timed_out:
        raise absent(GradeAbsence.GRADER_TIMEOUT, f"{step}: the suite hit its time limit")
    reported = {result.node_id: result for result in suite.results}
    return tuple(
        reported.get(node_id, NodeResult(node_id=node_id, outcome=NodeOutcome.NOT_RUN))
        for node_id in ids
    )


def run_producer_new(run: GradeRun) -> None:
    """Run the tests the producer added; a separate signal that never enters the pass (D2)."""
    collected = run.deps.collect_node_ids(run.sandbox, run.case)
    start = frozenset(run.start_ids)
    new_ids = [node_id for node_id in collected if node_id not in start]
    results = run_nodes(run, new_ids, "producer-new tests")
    run.producer_new_passed = sum(r.outcome is NodeOutcome.PASSED for r in results)
    run.producer_new_failed = sum(r.outcome in FAILING_OUTCOMES for r in results)


def _measurement(snapshot: CodeSnapshot, run: GradeRun, metric: SnapshotMetric) -> Measurement | None:
    for language in snapshot.languages:
        if language.language is run.adapter.language:
            return next((m for m in language.measurements if m.metric is metric), None)
    return None


def _check_total(run: GradeRun, snapshot: CodeSnapshot, kind: GraderCommandKind) -> int | None:
    """The sum of ``per_file`` for a check the case grades; ``None`` when not measured."""
    command = next((c for c in run.case.grader_commands if c.kind is kind), None)
    if command is None:
        return None
    measurement = _measurement(snapshot, run, CHECK_METRICS[kind])
    if measurement is None or measurement.absent is not None or measurement.tool is None:
        return None
    if measurement.tool.name != command.argv[0]:
        raise absent(
            GradeAbsence.CHECK_TOOL_MISMATCH,
            f"the {kind.value} command runs {command.argv[0]} but the snapshot measured "
            f"with {measurement.tool.name}",
        )
    return sum(measurement.per_file.values())


def measure_and_store(run: GradeRun, commit_sha: str) -> tuple[SnapshotRef, int | None, int | None]:
    """Snapshot the tree as it is, store it, and total its lint and type counts (D12)."""
    deps = run.deps
    try:
        snapshot = deps.measure_snapshot(run.sandbox.tree, run.case, commit_sha)
    except Exception as exc:
        _logger.exception("snapshot of the graded tree failed")
        raise absent(GradeAbsence.SNAPSHOT_FAILED, f"{type(exc).__name__}: {exc}") from exc
    digest = deps.store.snapshots.put(snapshot.model_dump_json().encode("utf-8"))
    return (
        SnapshotRef(sha256=digest),
        _check_total(run, snapshot, GraderCommandKind.LINT),
        _check_total(run, snapshot, GraderCommandKind.TYPECHECK),
    )


def take_snapshot(run: GradeRun) -> None:
    """Measure the tree as the producer left it, under the start config, and store it (D12)."""
    if run.head_sha is None:
        raise ValueError("the snapshot is taken after the subject's diff is committed")
    run.snapshot, run.lint_total, run.type_total = measure_and_store(run, run.head_sha)


def record_baseline(run: GradeRun) -> None:
    """A reference's start-tree node ids and snapshot, taken before its diff applies (D8).

    Every replay of the case is compared with these, so they are stored once with the
    reference. The node ids become the regression selection of the reference itself too.
    """
    deps = run.deps
    # In collection order, not sorted: tests that depend on the order of their file keep it.
    ids = list(deps.collect_node_ids(run.sandbox, run.case))
    run.start_ids = tuple(ids)
    run.baseline_nodes_sha = deps.store.nodes.put(json.dumps(ids).encode("utf-8"))
    run.baseline_snapshot, run.baseline_lint_total, run.baseline_type_total = measure_and_store(
        run, run.case.start_sha
    )


def capped(items: Sequence[str]) -> tuple[tuple[str, ...], int]:
    """The first ``MAX_LISTED_ITEMS`` of *items* and the true count."""
    return tuple(items[:MAX_LISTED_ITEMS]), len(items)


def run_hidden(run: GradeRun) -> None:
    """Inject the hidden set into the restored tree and run it; the last test step (D1, D3).

    An empty hidden set injects nothing and runs nothing (the slice-case shape, 426): the
    pass then reduces to no regressions.
    """
    deps = run.deps
    injection = run.adapter.inject_hidden(run.sandbox.tree, run.case, run.start, run.reference)
    pairs = [list(pair) for pair in injection.id_map]
    run.hidden_id_map_sha256 = deps.store.nodes.put(json.dumps(pairs).encode("utf-8"))
    run.injection_clashes, run.injection_clash_count = capped(injection.clashes)
    injected = [injected_id for _, injected_id in injection.id_map]
    results = run_nodes(run, injected, "hidden run")
    failures = [r for r in results if r.outcome is not NodeOutcome.PASSED]
    run.hidden_total = len(results)
    run.hidden_passed = len(results) - len(failures)
    run.hidden_failures = tuple(failures[:MAX_LISTED_ITEMS])


def count_added_suppressions(run: GradeRun) -> None:
    """Count suppressions the subject added in ``start..HEAD``; they stay in the tree (D6)."""
    diff = run_git(
        run,
        ["diff", "--binary", run.case.start_sha, run.head_sha or "HEAD"],
        cwd=str(run.sandbox.tree),
        in_sandbox=True,
    )
    run.suppressions = run.adapter.count_suppressions(diff.encode("utf-8"))


def restore_tests(run: GradeRun) -> None:
    """Put the start commit's existing test files back, counting the edits (D6).

    Runs after the snapshot (which measures the producer's tree, test code included) and
    before the regression run, which must run the start commit's tests, not edited ones.
    """
    tree = run.sandbox.tree
    edits = run.adapter.test_side_edits(tree, run.start)
    run.adapter.restore_test_files(tree, run.start, edits)
    run.test_edits, run.test_edit_count = capped(edits)


def run_regression(run: GradeRun) -> None:
    """Run the start tree's tests minus the superseded and excluded ones (D2).

    The selection is the start ids by name, never ``all_tests`` minus a deselect list, so a
    test the producer added cannot enter it. Failures are ``failed``, ``error`` or ``not_run``.
    """
    skipped = {*run.case.superseded_tests, *run.case.excluded_tests}
    selected = [node_id for node_id in run.start_ids if node_id not in skipped]
    results = run_nodes(run, selected, "regression run")
    failing = [r.node_id for r in results if r.outcome in FAILING_OUTCOMES]
    run.regression_selected = len(selected)
    run.regression_failures, run.regression_failure_count = capped(failing)
