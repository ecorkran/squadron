"""Producer units and config keys from run state (slice 176 D8, D9)."""

from __future__ import annotations

from squadron.stats.producer_units import ExcludedCounts, ProducerKey, extract_units
from tests.stats.producer_support import action, producer_actions, run, step


def test_design_and_tasks_pairs_are_one_unit_each_with_the_loop_attached() -> None:
    state = run(
        "r1",
        [
            step("design-0", "design", producer_actions()),
            step("loop-1", "loop", [action("review", verdict="PASS")]),
            step("tasks-0", "tasks", producer_actions()),
            step("loop-2", "loop", [action("review", verdict="PASS")]),
        ],
    )

    result = extract_units([state])

    assert [(u.phase.value, u.loop_step.step_name if u.loop_step else None) for u in result.units] == [
        ("design", "loop-1"),
        ("tasks", "loop-2"),
    ]
    assert result.excluded == ExcludedCounts()


def test_a_phase_step_without_a_following_loop_has_no_loop() -> None:
    state = run("r1", [step("design-0", "design", producer_actions()), step("c", "compact")])

    (unit,) = extract_units([state]).units

    assert unit.loop_step is None


def test_the_key_is_model_profile_effort_and_reviewer() -> None:
    state = run(
        "r1",
        [step("design-0", "design", producer_actions(model="m1", reviewer="rev", effort="high"))],
    )

    (unit,) = extract_units([state]).units

    assert unit.key == ProducerKey(model="m1", profile="sdk", effort="high", reviewer="rev")
    assert unit.alias == "opus"
    assert (unit.run_id, unit.pipeline, unit.slice) == ("r1", "p4", "176")


def test_the_same_producer_with_two_reviewers_is_two_config_keys() -> None:
    states = [
        run("r1", [step("design-0", "design", producer_actions(reviewer="rev-a"))]),
        run("r2", [step("design-0", "design", producer_actions(reviewer="rev-b"))]),
    ]

    units = extract_units(states).units

    assert len({unit.key for unit in units}) == 2


def test_the_reviewer_is_the_requested_model_else_the_answering_model() -> None:
    gate_review = action(
        "review", model="squadron-task-gate", requested="claude-sonnet", verdict="FAIL"
    )
    plain_review = action("review", model="claude-haiku", verdict="PASS")
    dispatch = action("dispatch", model="m", profile="sdk")
    states = [
        run("r1", [step("tasks-0", "tasks", [dispatch, gate_review])]),
        run("r2", [step("tasks-0", "tasks", [dispatch, plain_review])]),
    ]

    gate, plain = extract_units(states).units

    assert gate.key.reviewer == "claude-sonnet"  # not the pseudo-model "squadron-task-gate"
    assert plain.key.reviewer == "claude-haiku"


def test_a_dispatch_without_a_review_is_kept_with_no_reviewer() -> None:
    failed = step("design-0", "design", [action("dispatch", model="m", profile="sdk")], status="failed")

    (unit,) = extract_units([run("r1", [failed], status="failed")]).units

    assert unit.key.reviewer is None


def test_a_missing_dispatch_model_falls_back_to_the_requested_model() -> None:
    dispatch = action("dispatch", requested="asked-for", profile="sdk")

    (unit,) = extract_units([run("r1", [step("design-0", "design", [dispatch])])]).units

    assert unit.key.model == "asked-for"


def test_a_resumed_loop_uses_its_last_recorded_step() -> None:
    state = run(
        "r1",
        [
            step("design-0", "design", producer_actions()),
            step("loop-1", "loop", status="paused", iteration=1),
            step("loop-1", "loop", accepted=True, iteration=2),
        ],
    )

    (unit,) = extract_units([state]).units

    assert unit.loop_step is not None and unit.loop_step.accepted


def test_a_loop_with_no_phase_step_before_it_is_counted_not_a_unit() -> None:
    state = run(
        "r1",
        [
            step("tasks-0", "tasks", producer_actions()),
            step("branch", "branch"),
            step("loop-1", "loop"),  # adopted past its phase step
        ],
    )

    result = extract_units([state])

    assert len(result.units) == 1 and result.units[0].loop_step is None
    assert result.excluded.orphan_loops == 1


def test_each_steps_are_counted_and_never_units() -> None:
    state = run("r1", [step("design-0", "design", producer_actions()), step("each-1", "each")])

    result = extract_units([state])

    assert len(result.units) == 1
    assert result.excluded.each_steps == 1


def test_a_run_stopped_inside_a_loop_is_excluded_and_counted() -> None:
    state = run(
        "r1",
        [step("design-0", "design", producer_actions()), step("loop-1", "loop", status="failed")],
        status="failed",
        current_step="loop-1",
    )

    result = extract_units([state])

    assert result.units == ()
    assert result.excluded.partial_loop_runs == 1


def test_a_phase_step_without_a_dispatch_is_excluded_and_counted() -> None:
    state = run("r1", [step("design-0", "design", [action("cf-op")])])

    result = extract_units([state])

    assert result.units == () and result.excluded.without_dispatch == 1


def test_a_paused_phase_step_is_excluded_and_counted() -> None:
    state = run(
        "r1", [step("design-0", "design", producer_actions(), status="paused")], status="paused"
    )

    result = extract_units([state])

    assert result.units == () and result.excluded.paused == 1


def test_runs_without_a_phase_step_contribute_nothing() -> None:
    state = run(
        "r1", [step("impl", "implement"), step("each-1", "each"), step("loop-1", "loop")], pipeline="p6"
    )

    result = extract_units([state])

    assert result.units == () and result.excluded == ExcludedCounts()
