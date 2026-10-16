"""Reading a replay's outcome from run state: one test per D4 table row (slice 177)."""

from __future__ import annotations

import pytest

from squadron.metrology.replay_models import ReplayOutcome
from squadron.pipeline.failure_kind import FailureKind
from squadron.replay.outcome import (
    FailureClass,
    no_run_state_reading,
    read_outcome,
)
from tests.stats.producer_support import (
    action,
    producer_actions,
    prompt_identity,
    run,
    step,
    usage,
)

_CAP = 2


def _phase(verdict: str = "CONCERNS", **kwargs: object):  # pyright: ignore[reportUnknownParameterType]
    return step("design-0", "design", producer_actions(verdict=verdict, **kwargs))  # type: ignore[arg-type]


def _round(verdict: str, cost: float | None = 0.5) -> list[dict[str, object]]:
    revise = action("dispatch", model="claude-opus", profile="sdk", usage_record=usage(cost=cost))
    return [revise, action("review", verdict=verdict)]


def test_accepted_by_a_revise_round_counts_the_first_review_as_round_one() -> None:
    state = run(
        "r1",
        [
            _phase("FAIL"),
            step(
                "loop-1",
                "loop",
                _round("PASS"),
                iteration=2,
                prior_rounds=[_round("CONCERNS")],
            ),
        ],
    )

    reading = read_outcome(state)

    assert (reading.outcome, reading.rounds, reading.failure_class) == (
        ReplayOutcome.ACCEPTED,
        3,
        None,
    )
    assert reading.first_verdict == "FAIL"


def test_a_first_draft_pass_with_a_skipped_loop_is_accepted_in_one_round() -> None:
    state = run("r2", [_phase("PASS"), step("loop-1", "loop")])

    reading = read_outcome(state)

    assert (reading.outcome, reading.rounds) == (ReplayOutcome.ACCEPTED, 1)


def test_exhausted_but_accepted_by_accept_if_is_accepted() -> None:
    state = run(
        "r3",
        [
            _phase("FAIL"),
            step(
                "loop-1",
                "loop",
                _round("CONCERNS"),
                iteration=_CAP,
                accepted=True,
                exhausted=True,
                prior_rounds=[_round("FAIL")],
            ),
        ],
    )

    reading = read_outcome(state)

    assert (reading.outcome, reading.rounds) == (ReplayOutcome.ACCEPTED, _CAP + 1)


@pytest.mark.parametrize("status", ["failed", "paused"])
def test_an_exhausted_loop_is_exhausted_with_the_cap_plus_one_rounds(status: str) -> None:
    """``on_exhaust: checkpoint`` pauses a run and ``fail`` fails it; both are exhaustion."""
    state = run(
        "r4",
        [
            _phase("FAIL"),
            step(
                "loop-1",
                "loop",
                _round("FAIL"),
                status=status,
                iteration=_CAP,
                exhausted=True,
                prior_rounds=[_round("FAIL")],
            ),
        ],
        status=status,
    )

    reading = read_outcome(state)

    assert (reading.outcome, reading.rounds, reading.failure_class) == (
        ReplayOutcome.EXHAUSTED,
        _CAP + 1,
        None,
    )


def test_a_summary_failure_does_not_undo_an_accepted_artifact() -> None:
    state = run(
        "r5",
        [
            _phase("PASS"),
            step("loop-1", "loop"),
            step(
                "summary-2", "summary", [action("summary", success=False, error="x")], status="failed"
            ),
        ],
        status="failed",
    )

    assert read_outcome(state).outcome is ReplayOutcome.ACCEPTED


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (FailureKind.STALL, FailureClass.STALL),
        (FailureKind.PROVIDER_ERROR, FailureClass.DISPATCH_ERROR),
        (FailureKind.ARTIFACT_MISSING, FailureClass.NO_ARTIFACT),
    ],
)
def test_a_failed_phase_step_is_classified_by_its_stamped_kind(
    kind: FailureKind, expected: FailureClass
) -> None:
    failed = action("dispatch", success=False, error="why it failed", failure_kind=kind.value)
    state = run("r6", [step("design-0", "design", [failed], status="failed")], status="failed")

    reading = read_outcome(state)

    assert (reading.outcome, reading.failure_class) == (ReplayOutcome.FAILED, expected)
    assert reading.failure_detail == "why it failed"
    assert reading.rounds is None


def test_a_failure_with_no_kind_is_other_with_its_error_text() -> None:
    failed = action("dispatch", success=False, error="every tool call failed: denied")
    state = run("r7", [step("design-0", "design", [failed], status="failed")], status="failed")

    reading = read_outcome(state)

    assert reading.failure_class is FailureClass.OTHER
    assert reading.failure_detail == "every tool call failed: denied"


def test_an_unknown_failure_kind_is_other_not_an_error() -> None:
    failed = action("dispatch", success=False, error="odd", failure_kind="from_the_future")
    state = run("r8", [step("design-0", "design", [failed], status="failed")], status="failed")

    assert read_outcome(state).failure_class is FailureClass.OTHER


def test_a_dispatch_failure_inside_a_revise_round_fails_the_replay() -> None:
    failed = action("dispatch", success=False, error="rate limited", failure_kind="provider_error")
    state = run(
        "r9",
        [
            _phase("FAIL"),
            step("loop-1", "loop", [failed], status="failed", iteration=1),
        ],
        status="failed",
    )

    reading = read_outcome(state)

    assert (reading.outcome, reading.failure_class) == (
        ReplayOutcome.FAILED,
        FailureClass.DISPATCH_ERROR,
    )


def test_a_state_with_no_phase_step_is_a_failed_run() -> None:
    reading = read_outcome(run("r10", [], status="failed"))

    assert (reading.outcome, reading.failure_class) == (ReplayOutcome.FAILED, FailureClass.OTHER)
    assert reading.first_verdict is None and reading.cost_usd is None


def test_no_run_file_is_no_run_state_with_the_detail_recorded() -> None:
    reading = no_run_state_reading("exit 2: boom")

    assert (reading.outcome, reading.failure_class) == (
        ReplayOutcome.FAILED,
        FailureClass.NO_RUN_STATE,
    )
    assert reading.failure_detail == "exit 2: boom"


def test_cost_sums_every_round_and_counts_priced_of_llm_actions() -> None:
    state = run(
        "r11",
        [
            _phase("FAIL", cost=1.0),
            step(
                "loop-1",
                "loop",
                _round("PASS", cost=0.25),
                iteration=2,
                prior_rounds=[_round("CONCERNS", cost=0.5)],
            ),
        ],
    )

    reading = read_outcome(state)

    assert reading.cost_usd == pytest.approx(1.75)
    # three priced dispatches; the phase step's and two rounds' dispatches + reviews are LLM actions
    assert reading.priced[0] == 3
    assert reading.priced[1] >= reading.priced[0]


def test_an_unpriced_model_reports_k_below_m_and_no_zero_cost() -> None:
    state = run("r12", [_phase("PASS", cost=None), step("loop-1", "loop")])

    reading = read_outcome(state)

    assert reading.cost_usd is None
    assert reading.priced[0] == 0 and reading.priced[1] > 0


def test_prompt_identity_task_prompt_effort_and_producer_come_from_the_phase_dispatch() -> None:
    cf_op = action(
        "cf-op",
        outputs={"operation": "build_context", "stdout": "Create a design for slice 7."},
    )
    dispatch = action(
        "dispatch",
        model="claude-opus-5-5",
        profile="sdk",
        usage_record=usage(alias="opus", effort="high", cost=1.0),
        prompt_identity=prompt_identity("v0.21.1"),
    )
    review = action("review", model="r", requested="sonnet", verdict="PASS")
    state = run("r13", [step("design-0", "design", [cf_op, dispatch, review]), step("loop-1", "loop")])

    reading = read_outcome(state)

    assert reading.task_prompt == "Create a design for slice 7."
    assert reading.effort_sent == "high"
    assert (reading.producer_model, reading.producer_profile) == ("claude-opus-5-5", "sdk")
    assert reading.prompt is not None and reading.prompt.guide_version == "v0.21.1"


def test_a_state_from_before_prompt_identity_has_none() -> None:
    reading = read_outcome(run("r14", [_phase("PASS"), step("loop-1", "loop")]))

    assert reading.prompt is None and reading.task_prompt is None
