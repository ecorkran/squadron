"""``grade_one``: test restoration and the regression run (slice 425 Task 27, D1, D2, D6)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from squadron.benchmark.adapter import NodeOutcome, NodeResult, SuiteRun, SuiteSelection
from squadron.benchmark.grade_checks import (
    load_baseline,
    restore_tests,
    run_producer_new,
    run_regression,
    take_snapshot,
)
from squadron.benchmark.grade_prepare import prepare_tree
from squadron.benchmark.grade_run import GradeRun
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.grade_models import MAX_LISTED_ITEMS, ReviewOutcome
from squadron.metrology.snapshot_models import CodeSnapshot
from tests.benchmark.grade_support import (
    LoggingAdapter,
    LoggingBudget,
    World,
    make_world,
    quiet_review,
    seed_reference,
)
from tests.benchmark.grading_fixtures import (
    HIDDEN_FILE,
    GradingRepo,
    build_variant,
    make_grading_case,
)

START_IDS = tuple(f"t.py::t{i}" for i in range(6))
ORIGINAL_ASSERTION = 'ReviewPart("a-1.md", "part-1")'


def suite_with(
    seen: list[SuiteSelection], outcomes: dict[str, NodeOutcome] | None = None
) -> Callable[[SuiteSelection], SuiteRun]:
    def suite(selection: SuiteSelection) -> SuiteRun:
        seen.append(selection)
        ids = selection.node_ids or ()
        mapping = outcomes or {}
        return SuiteRun(
            results=tuple(
                NodeResult(node_id=i, outcome=mapping.get(i, NodeOutcome.PASSED)) for i in ids
            )
        )

    return suite


def build(
    tmp_path: Path, repo: GradingRepo, variant: str = "producer_a", **kwargs: object
) -> tuple[World, bytes]:
    case = kwargs.pop("case", None) or make_grading_case(repo)
    start_ids: tuple[str, ...] = kwargs.pop("start_ids", START_IDS)  # type: ignore[assignment]
    options: dict[str, object] = {
        "reviewer": quiet_review,
        "case": case,
        "collect": lambda sandbox, c: start_ids,
    }
    options.update(kwargs)
    world = make_world(tmp_path, repo, **options)  # type: ignore[arg-type]
    diff = build_variant(repo, variant, tmp_path / "producer").diff()
    seed_reference(world, start_ids)
    return world, diff


def run_through_regression(world: World, diff: bytes) -> GradeRun:
    with world.factory(world.case) as sandbox:
        run = world.run(world.replay_target(diff), sandbox)
        prepare_tree(run)
        load_baseline(run)
        run_producer_new(run)
        take_snapshot(run)
        restore_tests(run)
        run_regression(run)
        return run


def regression_selection(seen: list[SuiteSelection]) -> tuple[str, ...]:
    return seen[-1].node_ids or ()


def test_superseded_excluded_and_producer_added_ids_are_never_selected(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    case = make_grading_case(grading_repo).model_copy(
        update={"superseded_tests": (START_IDS[0],), "excluded_tests": (START_IDS[1],)}
    )
    seen: list[SuiteSelection] = []
    world, diff = build(
        tmp_path,
        grading_repo,
        case=case,
        suites=suite_with(seen),
        collect=lambda s, c: (*START_IDS, "t.py::producer_added"),
    )
    run = run_through_regression(world, diff)
    assert regression_selection(seen) == START_IDS[2:]
    assert "t.py::producer_added" not in regression_selection(seen)
    assert run.regression_selected == len(START_IDS) - 2


@pytest.mark.parametrize(
    ("outcome", "records_a_failure"),
    [
        (NodeOutcome.SKIPPED, False),
        (NodeOutcome.XFAILED, False),
        (NodeOutcome.XPASSED, False),
        (NodeOutcome.FAILED, True),
        (NodeOutcome.ERROR, True),
        (NodeOutcome.NOT_RUN, True),
    ],
)
def test_only_failed_error_and_not_run_are_regressions(
    tmp_path: Path, grading_repo: GradingRepo, outcome: NodeOutcome, records_a_failure: bool
) -> None:
    seen: list[SuiteSelection] = []
    world, diff = build(tmp_path, grading_repo, suites=suite_with(seen, {START_IDS[3]: outcome}))
    run = run_through_regression(world, diff)
    assert run.regression_failure_count == int(records_a_failure)
    assert run.regression_failures == ((START_IDS[3],) if records_a_failure else ())


def test_a_node_the_suite_does_not_report_counts_as_not_run(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    def dropping(selection: SuiteSelection) -> SuiteRun:
        ids = selection.node_ids or ()
        kept = [i for i in ids if i not in (START_IDS[2], "t.py::new_a")]
        return SuiteRun(results=tuple(NodeResult(i, NodeOutcome.PASSED) for i in kept))

    world, diff = build(
        tmp_path,
        grading_repo,
        suites=dropping,
        collect=lambda s, c: (*START_IDS, "t.py::new_a", "t.py::new_b"),
    )
    run = run_through_regression(world, diff)
    assert run.regression_failures == (START_IDS[2],)
    assert run.regression_failure_count == 1
    assert (run.producer_new_passed, run.producer_new_failed) == (1, 1)


def test_the_steps_run_in_d1_order(tmp_path: Path, grading_repo: GradingRepo) -> None:
    log: list[str] = []

    def collect(sandbox: object, case: object) -> tuple[str, ...]:
        log.append("collect")
        return (*START_IDS, "t.py::new")

    def measure(tree: Path, case: BenchmarkCase, head: str) -> CodeSnapshot:
        from tests.benchmark.grade_support import default_snapshot

        log.append("snapshot")
        return default_snapshot(tree, case, head)

    def reviewer(tree: Path, base: str) -> ReviewOutcome:
        log.append("review")
        return quiet_review(tree, base)

    seen: list[SuiteSelection] = []
    base_suite = suite_with(seen)

    def suite(selection: SuiteSelection) -> SuiteRun:
        return base_suite(selection)

    world, diff = build(
        tmp_path,
        grading_repo,
        suites=suite,
        collect=collect,
        measure=measure,
        reviewer=reviewer,
        budget=LoggingBudget(log),
        adapter=lambda: LoggingAdapter(log),
    )
    world.factory.log = log
    run_through_regression(world, diff)
    steps = [entry for entry in log if entry not in ("budget_check", "budget_charge", "deps_changed")]
    assert steps == [
        "review",
        "restore",
        "collect",
        "suite:1",
        "snapshot",
        "restore_tests",
        "suite:6",
    ]


def test_a_weakened_assertion_runs_the_original_in_the_regression_step(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    holder: dict[str, str] = {}
    seen: list[SuiteSelection] = []
    inner = suite_with(seen)

    def suite(selection: SuiteSelection) -> SuiteRun:
        tree = world.factory.opened[-1].tree
        holder["test_file"] = (tree / HIDDEN_FILE).read_text(encoding="utf-8")
        return inner(selection)

    world, diff = build(tmp_path, grading_repo, "producer_a", suites=suite)
    run = run_through_regression(world, diff)
    assert ORIGINAL_ASSERTION in holder["test_file"]
    assert run.test_edits == (HIDDEN_FILE,)
    assert run.test_edit_count == 1


def test_fifty_one_failures_keep_fifty_ids_and_count_fifty_one(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    many = tuple(f"t.py::t{i:03}" for i in range(MAX_LISTED_ITEMS + 1))
    world, diff = build(
        tmp_path,
        grading_repo,
        suites=suite_with([], {node_id: NodeOutcome.FAILED for node_id in many}),
        collect=lambda s, c: many,
        start_ids=many,
    )
    run = run_through_regression(world, diff)
    assert len(run.regression_failures) == MAX_LISTED_ITEMS
    assert run.regression_failure_count == MAX_LISTED_ITEMS + 1
    assert run.regression_failures == many[:MAX_LISTED_ITEMS]


def test_an_empty_regression_selection_never_calls_run_suite(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    case = make_grading_case(grading_repo).model_copy(update={"excluded_tests": START_IDS})
    world, diff = build(tmp_path, grading_repo, case=case)  # the default suite double raises
    run = run_through_regression(world, diff)
    assert run.regression_selected == 0
    assert run.regression_failure_count == 0
    assert not any(entry.startswith("suite") for entry in world.factory.log)
