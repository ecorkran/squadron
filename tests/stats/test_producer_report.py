"""Producer aggregation: per-config metrics, the evidence floor, and footer counts (D8, D9)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.pipeline.state import RunState, StateManager
from squadron.pipeline.steps import StepTypeName
from squadron.stats.producer_report import (
    FirstRound,
    ProducerReport,
    ProducerRow,
    producer_report,
)
from tests.stats.producer_support import (
    action,
    producer_actions,
    prompt_identity,
    run,
    step,
    usage,
)

_MIN_N = 3


def _write(runs_dir: Path, *states: RunState) -> StateManager:
    for state in states:
        (runs_dir / f"{state.run_id}.json").write_text(state.model_dump_json())
    return StateManager(runs_dir=runs_dir)


def _dispatch(cost: float) -> dict[str, object]:
    return action("dispatch", model="claude-opus", profile="sdk", usage_record=usage(cost=cost))


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "runs"
    directory.mkdir()
    return directory


def _config_a_runs() -> list[RunState]:
    """Config A (opus, reviewer-a): a clean pass, a one-round revise, an exhausted-but-accepted."""
    clean = run(
        "a1", [step("design-0", "design", producer_actions(verdict="PASS", cost=1.0))]
    )  # cost 1.0, 2 actions
    revised = run(
        "a2",
        [
            step("design-0", "design", producer_actions(verdict="FAIL", cost=1.0)),
            step(
                "loop-1",
                "loop",
                [action("review", verdict="PASS")],
                iteration=2,
                prior_rounds=[[_dispatch(0.5), action("review", verdict="FAIL")]],
            ),
        ],
    )  # cost 1.0 + 0.5, 2 + 2 + 1 actions
    exhausted = run(
        "a3",
        [
            step("design-0", "design", producer_actions(verdict="CONCERNS", cost=1.0)),
            step(
                "loop-1",
                "loop",
                [action("review", verdict="CONCERNS")],
                iteration=3,
                accepted=True,
                exhausted=True,
                prior_rounds=[
                    [_dispatch(0.5), action("review", verdict="FAIL")],
                    [_dispatch(0.5), action("review", verdict="CONCERNS")],
                ],
            ),
        ],
    )  # cost 1.0 + 0.5 + 0.5, 2 + 2 + 2 + 1 actions
    return [clean, revised, exhausted]


def _config_b_runs() -> list[RunState]:
    """Config B (haiku, reviewer-a): one pass and one failed phase step."""
    ok = run("b1", [step("design-0", "design", producer_actions(model="haiku", verdict="PASS"))])
    failed = run(
        "b2",
        [
            step(
                "design-0",
                "design",
                producer_actions(model="haiku", verdict="FAIL"),
                status="failed",
            )
        ],
        status="failed",
    )
    return [ok, failed]


def _row(report: ProducerReport, model: str) -> ProducerRow:
    (section,) = report.phases
    return next(row for row in section.rows if row.model == model)


def test_metrics_for_two_configs_across_several_runs(runs_dir: Path) -> None:
    manager = _write(runs_dir, *_config_a_runs(), *_config_b_runs())

    report = producer_report(phase=None, state_manager=manager, min_n=_MIN_N)

    row_a = _row(report, "claude-opus")
    assert row_a.n == 3
    assert row_a.first_round == {"PASS": 1, "CONCERNS": 1, "FAIL": 1, "none": 0}
    assert row_a.median_revise_rounds == 2.0  # rounds 0, 2, 3
    assert (row_a.accepted, row_a.failed) == (3, 0)
    assert row_a.cost_usd == pytest.approx(4.5)  # 1.0 + 1.5 + 2.0 across the three runs
    assert (row_a.priced, row_a.llm_actions) == (6, 14)  # priced 1 + 2 + 3; actions 2 + 5 + 7
    assert row_a.cost_per_accepted == pytest.approx(4.5 / 3)
    row_b = _row(report, "haiku")
    assert (row_b.n, row_b.accepted, row_b.failed) == (2, 1, 1)
    assert row_b.cost_per_accepted is None  # no recorded cost at all, not $0


def test_a_config_below_min_n_is_marked_and_sorted_after_the_rest(runs_dir: Path) -> None:
    manager = _write(runs_dir, *_config_a_runs(), *_config_b_runs())

    (section,) = producer_report(phase=None, state_manager=manager, min_n=_MIN_N).phases

    assert [(row.model, row.below_floor) for row in section.rows] == [
        ("claude-opus", False),
        ("haiku", True),
    ]
    assert section.runs == 5


def test_a_pre_176_run_file_uses_the_loop_iteration_for_rounds(runs_dir: Path) -> None:
    old = run(
        "old",
        [
            step("design-0", "design", producer_actions(verdict="FAIL")),
            step("loop-1", "loop", [action("review", verdict="PASS")], iteration=3),
        ],
    )
    manager = _write(runs_dir, old)

    report = producer_report(phase=None, state_manager=manager, min_n=1)

    assert _row(report, "claude-opus").median_revise_rounds == 3.0
    assert _row(report, "claude-opus").accepted == 1  # completed on an acceptable verdict
    assert report.rounds_unrecorded == 1


def test_an_unreadable_run_file_is_counted(runs_dir: Path) -> None:
    manager = _write(runs_dir, *_config_b_runs())
    (runs_dir / "run-corrupt.json").write_text("{not json")

    report = producer_report(phase=None, state_manager=manager, min_n=1)

    assert report.unreadable_runs == 1


def test_units_with_no_recorded_cost_are_counted(runs_dir: Path) -> None:
    manager = _write(runs_dir, *_config_a_runs(), *_config_b_runs())

    report = producer_report(phase=None, state_manager=manager, min_n=1)

    assert report.unpriced_runs == 2  # config B's two runs have no usage cost


def test_a_loop_that_exhausted_without_acceptance_is_not_accepted(runs_dir: Path) -> None:
    stuck = run(
        "stuck",
        [
            step("design-0", "design", producer_actions(verdict="FAIL")),
            step(
                "loop-1",
                "loop",
                [action("review", verdict="FAIL")],
                status="failed",
                iteration=2,
                exhausted=True,
                prior_rounds=[[action("review", verdict="FAIL")]],
            ),
        ],
    )
    manager = _write(runs_dir, stuck)

    report = producer_report(phase=None, state_manager=manager, min_n=1)

    assert _row(report, "claude-opus").accepted == 0


def test_the_phase_filter_reports_one_phase(runs_dir: Path) -> None:
    both = run(
        "both",
        [
            step("design-0", "design", producer_actions()),
            step("tasks-0", "tasks", producer_actions()),
        ],
    )
    manager = _write(runs_dir, both)

    only_tasks = producer_report(phase=StepTypeName.TASKS, state_manager=manager, min_n=1)
    everything = producer_report(phase=None, state_manager=manager, min_n=1)

    assert [section.phase for section in only_tasks.phases] == ["tasks"]
    assert [section.phase for section in everything.phases] == ["design", "tasks"]


def test_a_unit_without_a_review_verdict_counts_under_none(runs_dir: Path) -> None:
    dispatch_only = run(
        "d",
        [step("design-0", "design", [_dispatch(1.0)], status="failed")],
        status="failed",
    )
    manager = _write(runs_dir, dispatch_only)

    report = producer_report(phase=None, state_manager=manager, min_n=1)

    row = _row(report, "claude-opus")
    assert row.first_round[FirstRound.NONE.value] == 1
    assert (row.reviewer, row.failed) == (None, 1)


def test_json_values_equal_the_report_values(runs_dir: Path) -> None:
    manager = _write(runs_dir, *_config_a_runs())
    report = producer_report(phase=None, state_manager=manager, min_n=_MIN_N)

    data = report.to_json_dict()

    phases = data["phases"]
    assert isinstance(phases, list)
    assert phases[0]["phase"] == "design" and phases[0]["rows"][0]["n"] == 3
    assert phases[0]["rows"][0]["cost_per_accepted"] == pytest.approx(4.5 / 3)
    assert data["min_n"] == _MIN_N


def _identified_run(run_id: str, guide_version: str | None) -> RunState:
    actions = producer_actions(verdict="PASS", prompt_identity=prompt_identity(guide_version))
    return run(run_id, [step("design-0", "design", actions)])


def test_prompt_identity_counts_units_and_distinct_guide_versions(runs_dir: Path) -> None:
    manager = _write(
        runs_dir,
        _identified_run("i1", "v0.21.1"),
        _identified_run("i2", "v0.21.1"),
        _identified_run("i3", "v0.20.0"),
        _identified_run("i4", None),  # identified, but the project had no guide marker file
        *_config_b_runs(),  # two pre-177 units: no metadata["prompt"]
    )

    report = producer_report(phase=None, state_manager=manager, min_n=1)

    assert (report.units, report.prompt_identified, report.guide_versions) == (6, 4, 2)
    data = report.to_json_dict()
    assert (data["units"], data["prompt_identified"], data["guide_versions"]) == (6, 4, 2)


def test_pre_177_runs_carry_no_prompt_identity(runs_dir: Path) -> None:
    manager = _write(runs_dir, *_config_a_runs(), *_config_b_runs())

    report = producer_report(phase=None, state_manager=manager, min_n=1)

    assert (report.units, report.prompt_identified, report.guide_versions) == (5, 0, 0)
