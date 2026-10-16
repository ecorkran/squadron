"""The ``sq stats run`` report: one row per step action, plus read-time totals (D8, D9).

Reads run state only through ``StateManager``, whose atomic-replace writes mean a live
run is never seen torn. Nothing here is stored: totals are computed from the records
each time, so each action stays the one source of truth for its spend.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import cast

from squadron.core.usage import TokenUsage, UsageRecord, add_optional, add_optional_float
from squadron.pipeline.actions import ActionType
from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.state import (
    RunState,
    SchemaVersionError,
    StateManager,
    StepState,
    state_file_name,
)
from squadron.pipeline.steps import StepTypeName
from squadron.providers.base import USAGE_KEY
from squadron.stats.json_support import to_json_dict

_logger = logging.getLogger(__name__)

#: Action types that run an LLM call and so should carry a usage record (D9). Every
#: other ``ActionType`` (cf op, commit, gate, checkpoint, ...) is not expected to.
LLM_ACTION_TYPES = frozenset(
    {ActionType.DISPATCH, ActionType.SUMMARY, ActionType.COMPACT, ActionType.REVIEW}
)

#: The row note for a run that stopped or resumed inside a loop step (D9).
PARTIAL_LOOP_NOTE = "partial loop not recorded"


class RunUsageLoadError(Exception):
    """The run's state file is missing or unreadable; the message names what and where."""

    def __init__(self, message: str, *, run_id: str, path: Path) -> None:
        super().__init__(message)
        self.run_id = run_id
        self.path = path


@dataclass(frozen=True)
class UsageTotals:
    """Read-time totals over a set of records (D9)."""

    usage: TokenUsage
    turns: int | None
    cost_usd: float | None  # over priced records only
    priced: int  # records with a cost


@dataclass(frozen=True)
class ActionUsageRow:
    step: str
    action_type: str
    record: UsageRecord | None
    unreadable: bool = False
    #: 1-based loop round (the final round is the highest); ``None`` outside a loop step.
    round: int | None = None


@dataclass(frozen=True)
class RunUsageReport:
    run_id: str
    pipeline: str
    slice: str | None
    status: str
    started_at: datetime
    updated_at: datetime
    rows: list[ActionUsageRow] = field(default_factory=list[ActionUsageRow])
    totals: UsageTotals = field(default_factory=lambda: usage_totals([]))
    #: The run stopped or was resumed inside a loop step, so earlier rounds are not recorded.
    partial_loop: bool = False

    @property
    def llm_actions(self) -> int:
        return sum(1 for row in self.rows if row.action_type in LLM_ACTION_TYPES)

    @property
    def unrecorded(self) -> int:
        """LLM actions with no usable record: pre-slice, nothing reported, or unreadable."""
        return sum(1 for row in self.rows if row.action_type in LLM_ACTION_TYPES and row.record is None)

    @property
    def any_partial(self) -> bool:
        return any(row.record is not None and row.record.partial for row in self.rows)


def usage_totals(records: Iterable[UsageRecord]) -> UsageTotals:
    """Sum tokens and turns with ``None`` kept when unreported; cost over priced rows only."""
    usage = TokenUsage()
    turns: int | None = None
    cost: float | None = None
    priced = 0
    for record in records:
        usage = usage.plus(record.usage)
        turns = add_optional(turns, record.turns)
        if record.cost_usd is not None:
            cost = add_optional_float(cost, record.cost_usd)
            priced += 1
    return UsageTotals(usage=usage, turns=turns, cost_usd=cost, priced=priced)


def run_usage_report(run_id: str, state_manager: StateManager) -> RunUsageReport:
    """Load ``run_id`` and report each step action's usage record."""
    path = state_manager.runs_dir / state_file_name(run_id)
    try:
        state = state_manager.load(run_id)
    except FileNotFoundError as exc:
        raise RunUsageLoadError(
            f"no run {run_id!r} in {state_manager.runs_dir}", run_id=run_id, path=path
        ) from exc
    except (OSError, ValueError, SchemaVersionError) as exc:
        # ValueError covers invalid JSON, undecodable text, a top-level value that is not
        # an object, and a failed model validation.
        raise RunUsageLoadError(f"cannot read {path}: {exc}", run_id=run_id, path=path) from exc

    rows = report_rows(state)
    records = [row.record for row in rows if row.record is not None]
    return RunUsageReport(
        run_id=state.run_id,
        pipeline=state.pipeline,
        slice=run_slice(state),
        status=state.status,
        started_at=state.started_at,
        updated_at=state.updated_at,
        rows=rows,
        totals=usage_totals(records),
        partial_loop=is_partial_loop(state),
    )


def report_rows(state: RunState) -> list[ActionUsageRow]:
    """One row per step action in ``state``, loop rounds included; the single row source."""
    rows: list[ActionUsageRow] = []
    for step in state.completed_steps:
        rows.extend(_step_rows(state.run_id, step))
    return rows


def run_slice(state: RunState) -> str | None:
    """The slice a run was for (``params["slice"]``), as text so ``"176"`` and ``176`` agree."""
    value = state.params.get("slice")
    return None if value is None else str(value)


def is_partial_loop(state: RunState) -> bool:
    """True when the run did not complete and its current step is a loop step (D3, D9)."""
    if state.status == ExecutionStatus.COMPLETED.value:
        return False
    return any(
        step.step_name == state.current_step and step.step_type == StepTypeName.LOOP
        for step in state.completed_steps
    )


def _step_rows(run_id: str, step: StepState) -> list[ActionUsageRow]:
    """A step's rows: a loop's earlier rounds first, then the final round (D3)."""
    if step.step_type != StepTypeName.LOOP:
        return [action_usage_row(run_id, step.step_name, action) for action in step.action_results]
    earlier = len(step.prior_round_results)
    final_round = max(step.iteration, earlier + 1)
    rounds = [*step.prior_round_results, step.action_results]
    rows: list[ActionUsageRow] = []
    for offset, actions in enumerate(rounds):
        round_number = final_round - earlier + offset
        rows.extend(
            replace(action_usage_row(run_id, step.step_name, action), round=round_number)
            for action in actions
        )
    return rows


def action_usage_row(run_id: str, step: str, action: Mapping[str, object]) -> ActionUsageRow:
    """One action's usage row; a malformed record is ``unreadable`` with a WARNING (D9)."""
    action_type = str(action.get("action_type", ""))
    metadata = action.get("metadata")
    raw = (
        cast("Mapping[str, object]", metadata).get(USAGE_KEY) if isinstance(metadata, Mapping) else None
    )
    if raw is None:
        return ActionUsageRow(step=step, action_type=action_type, record=None)
    try:
        if not isinstance(raw, Mapping):
            raise ValueError(f"usage is not a mapping: {raw!r:.200}")
        record = UsageRecord.from_dict(cast("Mapping[str, object]", raw))
    except ValueError as exc:
        # A malformed record is reported, not fatal: the row says unreadable (D9).
        _logger.warning("run %s step %s: unreadable usage record: %s", run_id, step, exc)
        return ActionUsageRow(step=step, action_type=action_type, record=None, unreadable=True)
    return ActionUsageRow(step=step, action_type=action_type, record=record)


@dataclass(frozen=True)
class RunTotalsRow:
    """One run in the cross-run report: its identity and its read-time totals."""

    run_id: str
    pipeline: str
    slice: str | None
    status: str
    started_at: datetime
    llm_actions: int  # step actions that run an LLM call, every loop round included
    recorded: int  # of those, the ones with a usage record
    totals: UsageTotals
    partial_loop: bool  # earlier loop rounds are not recorded (D3)


@dataclass(frozen=True)
class RunsUsageReport:
    """Every readable run matching the filters, newest first, with one total (175 D9)."""

    slice_index: int | None
    pipeline: str | None
    rows: tuple[RunTotalsRow, ...]
    totals: UsageTotals
    llm_actions: int
    unreadable_runs: int

    def to_json_dict(self) -> dict[str, object]:
        return to_json_dict(self)


def runs_usage_report(
    *, slice_index: int | None, pipeline: str | None, state_manager: StateManager
) -> RunsUsageReport:
    """Totals across runs, filtered by slice (``params["slice"]``) and pipeline name."""
    scan = state_manager.scan_runs()
    matching = [
        state
        for state in scan.states
        if (slice_index is None or run_slice(state) == str(slice_index))
        and (pipeline is None or state.pipeline == pipeline)
    ]
    matching.sort(key=lambda state: state.started_at, reverse=True)
    rows: list[RunTotalsRow] = []
    records: list[UsageRecord] = []
    for state in matching:
        run_rows = report_rows(state)
        run_records = [row.record for row in run_rows if row.record is not None]
        records.extend(run_records)
        rows.append(
            RunTotalsRow(
                run_id=state.run_id,
                pipeline=state.pipeline,
                slice=run_slice(state),
                status=state.status,
                started_at=state.started_at,
                llm_actions=sum(row.action_type in LLM_ACTION_TYPES for row in run_rows),
                recorded=len(run_records),
                totals=usage_totals(run_records),
                partial_loop=is_partial_loop(state),
            )
        )
    return RunsUsageReport(
        slice_index=slice_index,
        pipeline=pipeline,
        rows=tuple(rows),
        totals=usage_totals(records),
        llm_actions=sum(row.llm_actions for row in rows),
        unreadable_runs=len(scan.unreadable),
    )
