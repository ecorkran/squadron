"""Producer units and config keys from run state (slice 176 D8).

A unit is a top-level design or tasks phase step plus the loop step that directly follows
it. Reads only the states ``StateManager.scan_runs()`` returned; no file or git access.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from squadron.pipeline.actions import ActionType
from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.loop_config import LoopCondition
from squadron.pipeline.state import RunState, StepState
from squadron.pipeline.steps import StepTypeName
from squadron.stats.usage_report import action_usage_row, is_partial_loop, run_slice

#: The phase step types a producer unit can be, in report order.
PHASE_TYPES = (StepTypeName.DESIGN, StepTypeName.TASKS)

#: What counts as accepted: the verdict P4/P5's loops accept (their ``accept_if``).
_ACCEPTANCE = LoopCondition.REVIEW_CONCERNS_OR_BETTER


@dataclass(frozen=True)
class ProducerKey:
    """What a producer config is: who wrote it, how, and who reviewed it (D8)."""

    model: str | None
    profile: str | None
    effort: str | None  # the effort that was sent (175 D7); None when none was
    reviewer: str | None  # None when the phase step recorded no review action


@dataclass(frozen=True)
class ProducerUnit:
    run_id: str
    pipeline: str
    slice: str | None
    phase: StepTypeName
    key: ProducerKey
    alias: str | None  # display name of the producer model
    phase_step: StepState
    loop_step: StepState | None


@dataclass
class ExcludedCounts:
    """What was left out of the units, each counted for the report footer (D9)."""

    orphan_loops: int = 0  # loops in a phase run with no phase step directly before
    each_steps: int = 0  # `each` steps: phase work inside them is not a top-level step
    partial_loop_runs: int = 0  # runs stopped or resumed inside a loop (D3)
    without_dispatch: int = 0  # phase steps that ran no dispatch (artifact kept, skipped)
    paused: int = 0  # phase steps paused at a checkpoint: the outcome is not decided yet


@dataclass(frozen=True)
class UnitExtraction:
    units: tuple[ProducerUnit, ...]
    excluded: ExcludedCounts


def extract_units(states: list[RunState]) -> UnitExtraction:
    """Units from every run; ``excluded`` counts what each exclusion rule dropped."""
    units: list[ProducerUnit] = []
    excluded = ExcludedCounts()
    for state in states:
        steps = state.completed_steps
        if not any(step.step_type in PHASE_TYPES for step in steps):
            continue  # not a producer run: its loops and each steps are someone else's
        excluded.each_steps += sum(step.step_type == StepTypeName.EACH for step in steps)
        excluded.orphan_loops += _orphan_loops(steps)
        if is_partial_loop(state):
            excluded.partial_loop_runs += 1
            continue
        for position, step in enumerate(steps):
            if step.step_type not in PHASE_TYPES:
                continue
            unit = _unit(state, steps, position)
            if unit is None:
                excluded.without_dispatch += 1
            elif step.status == ExecutionStatus.PAUSED:
                excluded.paused += 1
            else:
                units.append(unit)
    return UnitExtraction(units=tuple(units), excluded=excluded)


def _orphan_loops(steps: list[StepState]) -> int:
    return sum(
        step.step_type == StepTypeName.LOOP
        and (position == 0 or steps[position - 1].step_type not in PHASE_TYPES)
        for position, step in enumerate(steps)
    )


def _unit(state: RunState, steps: list[StepState], position: int) -> ProducerUnit | None:
    step = steps[position]
    dispatch = _first_action(step, ActionType.DISPATCH)
    if dispatch is None:
        return None
    usage = action_usage_row(state.run_id, step.step_name, dispatch).record
    review = _first_action(step, ActionType.REVIEW)
    metadata = _metadata(dispatch)
    key = ProducerKey(
        model=_text(metadata.get("model")) or _text(metadata.get("requested_model")),
        profile=_text(metadata.get("profile")),
        effort=None if usage is None else usage.effort,
        reviewer=None if review is None else _reviewer(review),
    )
    return ProducerUnit(
        run_id=state.run_id,
        pipeline=state.pipeline,
        slice=run_slice(state),
        phase=StepTypeName(step.step_type),
        key=key,
        alias=None if usage is None else usage.alias,
        phase_step=step,
        loop_step=_loop_after(steps, position),
    )


def _loop_after(steps: list[StepState], position: int) -> StepState | None:
    """The loop directly after the phase step; a resumed run's last record of it wins."""
    if position + 1 >= len(steps) or steps[position + 1].step_type != StepTypeName.LOOP:
        return None
    name = steps[position + 1].step_name
    return next(step for step in reversed(steps[position + 1 :]) if step.step_name == name)


def _reviewer(review: Mapping[str, object]) -> str | None:
    """The configured reviewer model. The mechanical task gate reports itself as ``model``;
    ``requested_model`` is the reviewer the run asked for, which also drives the loop."""
    metadata = _metadata(review)
    return _text(metadata.get("requested_model")) or _text(metadata.get("model"))


def _first_action(step: StepState, action_type: ActionType) -> Mapping[str, object] | None:
    return next((a for a in step.action_results if a.get("action_type") == action_type), None)


def _metadata(action: Mapping[str, object]) -> Mapping[str, object]:
    raw = action.get("metadata")
    return cast("Mapping[str, object]", raw) if isinstance(raw, Mapping) else {}


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def loop_rounds(loop: StepState | None) -> int:
    """Loop rounds run: from the persisted rounds (176 D3), else the loop's own iteration."""
    if loop is None:
        return 0
    return len(loop.prior_round_results) + 1 if loop.prior_round_results else loop.iteration


def phase_accepted(phase_step: StepState, loop_step: StepState | None) -> bool:
    """The unit ended accepted (176 D8).

    With no loop, or a loop that ran no rounds (``skip_if_met``: the first draft already
    passed, or a ``--decision accept``), the phase step's first-round verdict decides.
    Otherwise the loop ended accepted, or completed on an acceptable verdict.
    """
    if phase_step.status != ExecutionStatus.COMPLETED:
        return False
    if loop_step is None or _ran_no_rounds(loop_step):
        if loop_step is not None and loop_step.accepted:
            return True  # accepted by decision, with no rounds run
        verdict = phase_step.verdict
        return verdict is not None and _ACCEPTANCE.met_by_verdict(verdict)
    if loop_step.status != ExecutionStatus.COMPLETED:
        return False
    # `accepted` is set when a loop exhausted its rounds but met accept_if; a loop whose
    # `until` was met ends completed on an acceptable verdict, and so does a pre-176 file.
    return loop_step.accepted or (
        loop_step.verdict is not None and _ACCEPTANCE.met_by_verdict(loop_step.verdict)
    )


def _ran_no_rounds(loop: StepState) -> bool:
    return not loop.action_results and not loop.prior_round_results and loop.iteration == 0
