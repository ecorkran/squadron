"""The ``sq stats run`` report: one row per step action, plus read-time totals (D8, D9).

Reads run state only through ``StateManager``, whose atomic-replace writes mean a live
run is never seen torn. Nothing here is stored: totals are computed from the records
each time, so each action stays the one source of truth for its spend.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import cast

from squadron.core.usage import TokenUsage, UsageRecord, add_optional, add_optional_float
from squadron.pipeline.actions import ActionType
from squadron.pipeline.state import SchemaVersionError, StateManager, state_file_name
from squadron.providers.base import USAGE_KEY

_logger = logging.getLogger(__name__)

#: Action types that run an LLM call and so should carry a usage record (D9). Every
#: other ``ActionType`` (cf op, commit, gate, checkpoint, ...) is not expected to.
LLM_ACTION_TYPES = frozenset(
    {ActionType.DISPATCH, ActionType.SUMMARY, ActionType.COMPACT, ActionType.REVIEW}
)


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

    rows: list[ActionUsageRow] = []
    for step in state.completed_steps:
        for action in step.action_results:
            rows.append(_row(run_id, step.step_name, action))
    records = [row.record for row in rows if row.record is not None]
    slice_param = state.params.get("slice")
    return RunUsageReport(
        run_id=state.run_id,
        pipeline=state.pipeline,
        slice=None if slice_param is None else str(slice_param),
        status=state.status,
        started_at=state.started_at,
        updated_at=state.updated_at,
        rows=rows,
        totals=usage_totals(records),
    )


def _row(run_id: str, step: str, action: Mapping[str, object]) -> ActionUsageRow:
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
