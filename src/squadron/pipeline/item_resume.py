"""Rerun one item of a finished batch on a decision (slice 197 D8, D9).

``sq run --resume <run_id> --item <index> --decision retry|accept`` lands here. In
order: take the project run lock, validate the request against the run's
``report.json``, put git back on the target, rebuild the run's params, re-evaluate the
source for the item, reconcile or dependency-check it, then run the ``each`` body once
for it through the executor. The caller supplies that last step (``BodyRunner``), so
this module never depends on the CLI. Every refusal names the fact that refused it.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum
from pathlib import Path
from typing import Any, cast

from squadron.pipeline.batch_report import (
    BatchItemRecord,
    BatchReport,
    BatchReportLoadError,
    FlagKind,
    ItemDecision,
    ItemOutcome,
    ItemRerun,
    report_json_path,
)
from squadron.pipeline.branch_ops import dirty_paths, restore_target
from squadron.pipeline.control_params import (
    ACCEPT_DECISION,
    OVERRIDE_INSTRUCTIONS,
    RESERVED_PARAMS,
    reserved_param_error,
)
from squadron.pipeline.executor import evaluate_each_source
from squadron.pipeline.git_ops import (
    GitEnvironmentError,
    current_branch,
    read_integration_target,
    slice_branch_name,
    verify_git_state,
)
from squadron.pipeline.item_eligibility import (
    ItemResumeUnsupportedError,
    item_decisions,
    single_each_step,
)
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import StepConfig
from squadron.pipeline.run_lock import RunLockError, project_run_lock
from squadron.pipeline.sources import CfSliceStatus
from squadron.pipeline.state import SchemaVersionError, StateManager
from squadron.pr.branch import parse_slice_branch
from squadron.review.git_utils import run_git

_logger = logging.getLogger(__name__)

RECONCILED_REASON = "reconciled: merged before the report was updated"

# Runs the pipeline's ``each`` body once for ``rerun.item``: (pipeline name, params, rerun).
BodyRunner = Callable[[str, dict[str, object], ItemRerun], Awaitable[object]]


class ResumeExit(IntEnum):
    """Item resume exit codes, for an automated caller (D8)."""

    RESOLVED = 0  # the item ended PASSED or ACCEPTED
    FLAGGED = 1  # the decision was applied and the item was flagged again
    REJECTED = 2  # validation, the git precondition or the run lock refused; nothing ran
    HALTED = 3  # an environment fault or unknown git state ended it mid-item


@dataclass(frozen=True)
class ResumeRequest:
    run_id: str
    index: str
    decision: ItemDecision
    instructions: str | None = None
    model: str | None = None
    param_overrides: dict[str, object] = field(default_factory=lambda: {})


@dataclass(frozen=True)
class ResumeOutcome:
    exit: ResumeExit
    message: str
    record: BatchItemRecord | None = None
    report_path: Path | None = None


class _Stop(Exception):
    """Ends a resume early with its exit code and message."""

    def __init__(self, exit_code: ResumeExit, message: str) -> None:
        super().__init__(message)
        self.exit = exit_code


@dataclass
class _Run:
    """What validation found: the run's pipeline, its ``each`` step and its report."""

    pipeline: str
    params: dict[str, object]
    each: StepConfig
    report: BatchReport
    report_path: Path


async def resume_item(
    request: ResumeRequest,
    *,
    cwd: str,
    cf_client: Any,
    state_manager: StateManager,
    run_body: BodyRunner,
) -> ResumeOutcome:
    """Apply *request*'s decision to one item; never raises for an expected refusal."""
    lock = ExitStack()
    try:
        lock.enter_context(project_run_lock(cwd))
    except (RunLockError, GitEnvironmentError) as exc:
        # Logged at ERROR by the lock; a busy lock means "retry later".
        return ResumeOutcome(ResumeExit.REJECTED, str(exc))
    try:
        return await _resume_locked(request, cwd, cf_client, state_manager, run_body)
    except _Stop as stop:
        log = _logger.error if stop.exit is ResumeExit.HALTED else _logger.warning
        log("item resume %s item %s: %s", request.run_id, request.index, stop)
        return ResumeOutcome(stop.exit, str(stop))
    except GitEnvironmentError as exc:
        _logger.error("item resume %s halted: %s", request.run_id, exc)
        return ResumeOutcome(ResumeExit.HALTED, str(exc))
    except OSError as exc:
        # A file or process fault mid-item (a failed report write leaves the old one intact).
        _logger.exception("item resume %s item %s halted", request.run_id, request.index)
        return ResumeOutcome(ResumeExit.HALTED, f"item resume halted: {exc}")
    finally:
        lock.close()


async def _resume_locked(
    request: ResumeRequest,
    cwd: str,
    cf_client: Any,
    state_manager: StateManager,
    run_body: BodyRunner,
) -> ResumeOutcome:
    run = _validate(request, state_manager)
    target = _git_precondition(cwd, cf_client)
    params = item_params(run.params, request)
    item = await _select_item(request, run, params, cf_client, cwd, target)
    if item is None:  # reconciled
        return _outcome(run, request.index)
    rerun = ItemRerun(item, run.report, request.decision, datetime.now(UTC).isoformat())
    if (reason := _open_dependencies(item, run.report.plan, cf_client)) is not None:
        rerun.replace(BatchItemRecord.from_item(item, 0, [], reason, flag_kind=FlagKind.DEPENDENCY))
        run.report.write(run.report_path.parent)
        return _outcome(run, request.index)
    await run_body(run.pipeline, params, rerun)
    if rerun.record is None:
        raise _Stop(ResumeExit.HALTED, f"item {request.index} did not finish its body")
    return _outcome(run, request.index)


def _outcome(run: _Run, index: str) -> ResumeOutcome:
    record = next(r for r in run.report.records if r.index == index)
    resolved = record.outcome in (ItemOutcome.PASSED, ItemOutcome.ACCEPTED)
    return ResumeOutcome(
        ResumeExit.RESOLVED if resolved else ResumeExit.FLAGGED,
        record.render_line()[2:],
        record,
        run.report_path,
    )


# ---------------------------------------------------------------------------
# Validation (before any git or model work)
# ---------------------------------------------------------------------------


def _validate(request: ResumeRequest, state_manager: StateManager) -> _Run:
    try:
        state = state_manager.load(request.run_id)
    except FileNotFoundError:
        raise _Stop(ResumeExit.REJECTED, f"run {request.run_id} not found") from None
    except SchemaVersionError as exc:
        raise _Stop(ResumeExit.REJECTED, str(exc)) from None
    try:
        each = single_each_step(load_pipeline(state.pipeline))
    except ItemResumeUnsupportedError as exc:
        raise _Stop(ResumeExit.REJECTED, f"run {request.run_id}'s {exc}") from None
    path = report_json_path(state_manager.runs_dir, request.run_id, each.name)
    try:
        report = BatchReport.load(path)
    except BatchReportLoadError as exc:
        _logger.error("item resume: %s", exc)
        raise _Stop(ResumeExit.REJECTED, str(exc)) from None
    _check_record(report, request, path)
    return _Run(state.pipeline, dict(state.params), each, report, path)


def _check_record(report: BatchReport, request: ResumeRequest, path: Path) -> None:
    record = next((r for r in report.records if r.index == request.index), None)
    if record is None:
        raise _Stop(ResumeExit.REJECTED, f"no record for item {request.index} in {path}")
    decisions = item_decisions(record)
    if not decisions:
        raise _Stop(
            ResumeExit.REJECTED,
            f"item {request.index} is {record.outcome}; only flagged or not_run items resume",
        )
    if request.decision not in decisions:
        kind = record.flag_kind or record.outcome
        raise _Stop(
            ResumeExit.REJECTED,
            f"accept requires flagKind review_unresolved; item {request.index} is {kind}",
        )


# ---------------------------------------------------------------------------
# Git precondition (after the lock, before the source reads the working tree)
# ---------------------------------------------------------------------------


def _git_precondition(cwd: str, cf_client: Any) -> str:
    """Return to the target from a flagged slice branch, then require a clean target."""
    target = read_integration_target(cf_client)
    start = current_branch(cwd)
    if start != target and parse_slice_branch(start) is not None:
        restore_target(target, cwd)  # GitStateUnknownError → HALTED
    current = current_branch(cwd)
    if current != target:
        raise _Stop(ResumeExit.REJECTED, f"on {current}, expected {target}; nothing changed")
    if paths := dirty_paths(cwd):
        raise _Stop(ResumeExit.REJECTED, f"working tree not clean: {paths}; nothing changed")
    verify_git_state(target, cwd=cwd)
    return target


# ---------------------------------------------------------------------------
# Params, source and dependencies
# ---------------------------------------------------------------------------


def item_params(stored: dict[str, object], request: ResumeRequest) -> dict[str, object]:
    """The run's params with the request's overrides and decision keys (D8).

    Reserved keys stored in run state (a checkpoint may have stored instructions) are
    dropped with a WARNING: an earlier run's instructions never carry into a decision.
    """
    params = dict(stored)
    dropped = sorted(key for key in RESERVED_PARAMS if params.pop(key, None) is not None)
    if dropped:
        _logger.warning(
            "item resume %s: dropped stored %s; a decision sets them",
            request.run_id,
            ", ".join(dropped),
        )
    for key, value in request.param_overrides.items():
        if (reserved := reserved_param_error(key)) is not None:
            raise _Stop(ResumeExit.REJECTED, reserved)
        params[key] = value
    if request.model is not None:
        params["model"] = request.model
    if request.instructions:
        params[OVERRIDE_INSTRUCTIONS] = request.instructions
    if request.decision is ItemDecision.ACCEPT:
        params[ACCEPT_DECISION] = True
    return params


async def _select_item(
    request: ResumeRequest,
    run: _Run,
    params: dict[str, object],
    cf_client: Any,
    cwd: str,
    target: str,
) -> dict[str, object] | None:
    """The item, freshly selected; ``None`` when it was reconciled to PASSED."""
    source = str(run.each.config.get("source", ""))
    _, items = await evaluate_each_source(source, params, cf_client)
    item = next((i for i in items if str(i.get("index")) == request.index), None)
    if item is not None:
        return item
    entry = next(
        (e for e in cf_client.list_slices(run.report.plan) if str(e.index) == request.index), None
    )
    status = entry.status if entry is not None else "not in the plan"
    if entry is not None and status == CfSliceStatus.COMPLETE and entry.design_file:
        branch = slice_branch_name(entry.index, entry.design_file)
        merged = run_git(["merge-base", "--is-ancestor", branch, target], cwd=cwd)
        if merged is not None and merged.returncode == 0:
            _reconcile(request, run, entry.name)
            return None
        status = f"{status} but {branch} is not merged into {target}"
    raise _Stop(
        ResumeExit.REJECTED,
        f"item {request.index} is no longer selected by {source}: status {status}",
    )


def _reconcile(request: ResumeRequest, run: _Run, name: str) -> None:
    """An earlier resume merged the item and died before rewriting the report (D8)."""
    records = run.report.records
    position = next(i for i, r in enumerate(records) if r.index == request.index)
    records[position] = BatchItemRecord(
        request.index,
        name,
        ItemOutcome.PASSED,
        reason=RECONCILED_REASON,
        branch=records[position].branch,
        decision=request.decision,
        resumed_at=datetime.now(UTC).isoformat(),
    )
    _logger.warning("item resume %s: item %s %s", request.run_id, request.index, RECONCILED_REASON)
    run.report.write(run.report_path.parent)


def _open_dependencies(item: dict[str, object], plan: str | None, cf_client: Any) -> str | None:
    """Why a lone item must not run: in-plan dependencies not complete on the target."""
    raw = item.get("dependencies")
    dependencies = (
        [d for d in cast(list[object], raw) if isinstance(d, int)] if isinstance(raw, list) else []
    )
    if not dependencies:
        return None
    status = {e.index: e.status for e in cf_client.list_slices(plan)}
    open_ = [d for d in dependencies if d in status and status[d] != CfSliceStatus.COMPLETE]
    return "; ".join(f"dependency {d} not complete" for d in open_) or None
