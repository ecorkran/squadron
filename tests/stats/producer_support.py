"""Builders for run-state objects in the producer report tests (slice 176 D8)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from squadron.pipeline.state import RunState, StepState

_NOW = datetime(2026, 11, 1, 12, tzinfo=UTC)


def usage(
    *, alias: str | None = "opus", effort: str | None = None, cost: float | None = None
) -> dict[str, object]:
    """A ``UsageRecord.to_dict()`` shape for an action's ``metadata["usage"]``."""
    return {
        "model": "m",
        "alias": alias,
        "profile": "sdk",
        "effort": effort,
        "turns": 1,
        "duration_seconds": 1.0,
        "usage": {"prompt": 10, "completion": 1},
        "cost_usd": cost,
        "cost_basis": None if cost is None else "provider",
        "partial": False,
    }


def action(
    action_type: str,
    *,
    model: str | None = None,
    requested: str | None = None,
    profile: str | None = None,
    verdict: str | None = None,
    usage_record: dict[str, object] | None = None,
) -> dict[str, object]:
    metadata: dict[str, object] = {}
    if model is not None:
        metadata["model"] = model
    if requested is not None:
        metadata["requested_model"] = requested
    if profile is not None:
        metadata["profile"] = profile
    if usage_record is not None:
        metadata["usage"] = usage_record
    return {"success": True, "action_type": action_type, "verdict": verdict, "metadata": metadata}


def step(
    name: str,
    step_type: str,
    actions: Sequence[dict[str, object]] = (),
    *,
    status: str = "completed",
    iteration: int = 0,
    accepted: bool = False,
    exhausted: bool = False,
    prior_rounds: Sequence[Sequence[dict[str, object]]] = (),
) -> StepState:
    return StepState(
        step_name=name,
        step_type=step_type,
        status=status,
        action_results=list(actions),
        iteration=iteration,
        accepted=accepted,
        exhausted=exhausted,
        prior_round_results=[list(round_results) for round_results in prior_rounds],
        completed_at=_NOW,
    )


def run(
    run_id: str,
    steps: Sequence[StepState],
    *,
    pipeline: str = "p4",
    status: str = "completed",
    current_step: str | None = None,
    slice_index: int | None = 176,
) -> RunState:
    return RunState(
        run_id=run_id,
        pipeline=pipeline,
        params={} if slice_index is None else {"slice": slice_index},
        started_at=_NOW,
        updated_at=_NOW,
        status=status,
        current_step=current_step,
        completed_steps=list(steps),
    )


def producer_actions(
    *,
    model: str = "claude-opus",
    reviewer: str = "reviewer-a",
    verdict: str = "PASS",
    alias: str | None = "opus",
    effort: str | None = None,
    cost: float | None = None,
) -> list[dict[str, object]]:
    """A phase step's dispatch and review actions, as a P4/P5 run records them."""
    return [
        action(
            "dispatch",
            model=model,
            profile="sdk",
            usage_record=usage(alias=alias, effort=effort, cost=cost),
        ),
        action("review", model="reviewer-runtime", requested=reviewer, verdict=verdict),
    ]
