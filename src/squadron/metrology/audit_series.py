"""One audit variance series at a pinned commit: run N audits, reduce a noise floor.

Shared by ``sq metrology audit variance`` and ``sq metrology baseline``. This
module never prints; callers pass an observer that does (D4, slice 404).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from squadron.metrology.audit import (
    AuditPreflightError,
    AuditProgress,
    AuditRunFailure,
    AuditRunResult,
    AuditSkillError,
    run_audit,
)
from squadron.metrology.audit_variance import (
    MIN_USABLE_RUNS,
    AuditVarianceError,
    reduce_noise_floor,
)
from squadron.metrology.errors import MetrologyIdentityError
from squadron.metrology.models import AuditNoiseFloor, AuditRun
from squadron.metrology.store import MetrologyStore

# The keyword signature of ``run_audit``; tests and callers inject a fake.
AuditCallable = Callable[..., Coroutine[Any, Any, AuditRunResult]]
ProgressCallback = Callable[[AuditProgress], None]


class NoFloorReason(StrEnum):
    TOO_FEW_RUNS = "too_few_runs"
    UNREDUCIBLE = "unreducible"


@dataclass(frozen=True)
class AuditSeriesRequest:
    project_path: Path
    runs: int
    cooldown_s: int
    profile: str | None
    model: str | None
    # Pins the commit from run 1 on. None pins it from the first successful run.
    expected_sha: str | None
    config_cwd: str


class AuditSeriesObserver(Protocol):
    """Output hooks. ``run_number`` is 1-based."""

    def on_run_start(self, run_number: int) -> None: ...

    def on_cooldown(self, run_number: int, cooldown_s: int) -> None: ...

    def on_outcome(self, run_number: int, outcome: AuditRunResult) -> None: ...

    def progress_callback(self, run_number: int) -> ProgressCallback | None: ...


@dataclass
class AuditSeriesResult:
    runs: list[AuditRun] = field(default_factory=lambda: [])
    failed: int = 0
    floor: AuditNoiseFloor | None = None
    rate_limited: bool = False
    # The preflight, skill or identity error that ended the series early.
    stop_error: str | None = None
    no_floor_reason: NoFloorReason | None = None
    # The reducer's message when ``no_floor_reason`` is UNREDUCIBLE.
    reduce_error: str | None = None


def run_audit_series(
    request: AuditSeriesRequest,
    *,
    store: MetrologyStore,
    observer: AuditSeriesObserver,
    audit: AuditCallable = run_audit,
) -> AuditSeriesResult:
    """Run the series, persist each run, reduce and write the floor if usable.

    ``MetrologyStoreError`` and ``KeyboardInterrupt`` propagate: completed runs
    are already persisted, and the caller owns the process boundary.
    """
    result = AuditSeriesResult()
    pinned_sha = request.expected_sha

    for index in range(request.runs):
        run_number = index + 1
        # Spacing lowers the request rate the series presents, rather than
        # absorbing throttles after they fire. Nothing is spent before run 1.
        if index > 0 and request.cooldown_s > 0:
            observer.on_cooldown(run_number, request.cooldown_s)
            time.sleep(request.cooldown_s)
        observer.on_run_start(run_number)
        try:
            outcome = asyncio.run(
                audit(
                    request.project_path,
                    store=store,
                    profile=request.profile,
                    model=request.model,
                    independent_run=True,
                    require_clean=True,
                    expected_sha=pinned_sha,
                    on_progress=observer.progress_callback(run_number),
                    cwd=request.config_cwd,
                )
            )
        except (AuditPreflightError, AuditSkillError, MetrologyIdentityError) as exc:
            # The same error would end every remaining run; report it once.
            result.stop_error = str(exc)
            result.failed += request.runs - index
            break

        observer.on_outcome(run_number, outcome)
        if outcome.succeeded and outcome.run is not None:
            result.runs.append(outcome.run)
            pinned_sha = outcome.run.commit_sha
            continue
        result.failed += 1
        if outcome.failure is AuditRunFailure.RATE_LIMITED:
            result.rate_limited = True
            break

    _reduce_into(result, store)
    return result


def _reduce_into(result: AuditSeriesResult, store: MetrologyStore) -> None:
    """Write the floor when enough runs landed; otherwise record why not."""
    if len(result.runs) < MIN_USABLE_RUNS:
        result.no_floor_reason = NoFloorReason.TOO_FEW_RUNS
        return
    try:
        floor = reduce_noise_floor(result.runs)
    except AuditVarianceError as exc:
        # Typed "these runs cannot be reduced" outcome, reported via the result.
        result.no_floor_reason = NoFloorReason.UNREDUCIBLE
        result.reduce_error = str(exc)
        return
    store.write_noise_floor(floor)
    result.floor = floor
