"""Whether a ``running`` run is still alive (slice 174 D3).

The single definition of orphaned and stale, shared by the run listing,
``sq runs wait`` and ``sq runs prune``. Pure apart from the injected
``process_alive`` check; the result is derived on every read and never
persisted (D4).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from squadron.pipeline.state import RUNNING_STATUS, RunState

_logger = logging.getLogger(__name__)

# Missed heartbeat intervals before a run is suspect. A protocol constant, not tuning.
STALE_HEARTBEAT_INTERVALS = 10


class RunLiveness(StrEnum):
    """What can be said about a ``running`` run's owning process."""

    LIVE = "live"
    STALE = "stale"  # heartbeat overdue; suspect, never terminal
    ORPHANED = "orphaned"  # owning process gone on this host; conclusive
    UNOWNED = "unowned"  # no owner record: v3/v4 file or prompt-only run


@dataclass(frozen=True)
class LivenessAssessment:
    """A liveness verdict with the durations the listing shows."""

    liveness: RunLiveness
    elapsed: timedelta | None  # since the owner claimed the run
    progress_age: timedelta | None  # since the last step start, item start or completion
    heartbeat_age: timedelta | None


ProcessCheck = Callable[[int], bool | None]


def process_alive(pid: int) -> bool | None:
    """Whether *pid* is a live process on this host; ``None`` when that cannot be told.

    ``0`` and negative PIDs address process groups, so ``os.kill`` would read
    them as alive; they are unknown instead.
    """
    if pid <= 0:
        _logger.warning("process check: pid %d is not a process id; liveness unknown", pid)
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by another user
    except OSError as exc:
        _logger.warning("process check: pid %d failed (%s); liveness unknown", pid, exc)
        return None
    return True


def assess_liveness(
    state: RunState,
    *,
    now: datetime,
    hostname: str,
    process_alive: ProcessCheck = process_alive,
) -> LivenessAssessment | None:
    """Apply D3 to *state*; ``None`` when the run is not ``running``.

    Rows are evaluated top to bottom, so a same-host run whose process is gone
    is ``ORPHANED`` even when its heartbeat is also overdue. An unknown process
    check falls through to the heartbeat rule.
    """
    if state.status != RUNNING_STATUS:
        return None
    progress_age = _age(now, state.progress_at)
    heartbeat_age = _age(now, state.heartbeat_at)
    owner = state.owner
    if owner is None:
        return LivenessAssessment(RunLiveness.UNOWNED, None, progress_age, heartbeat_age)
    elapsed = now - owner.claimed_at
    if owner.hostname == hostname and process_alive(owner.pid) is False:
        liveness = RunLiveness.ORPHANED
    elif heartbeat_age is not None and heartbeat_age > _stale_after(owner.heartbeat_interval_s):
        liveness = RunLiveness.STALE
    else:
        liveness = RunLiveness.LIVE
    return LivenessAssessment(liveness, elapsed, progress_age, heartbeat_age)


def format_duration(delta: timedelta) -> str:
    """A compact two-unit duration: ``40s``, ``12m05s``, ``1h04m``, ``3d02h``."""
    seconds = max(0, int(delta.total_seconds()))
    minutes, secs = divmod(seconds, 60)
    hours, mins = divmod(minutes, 60)
    days, hrs = divmod(hours, 24)
    if days:
        return f"{days}d{hrs:02d}h"
    if hours:
        return f"{hours}h{mins:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def _stale_after(heartbeat_interval_s: int) -> timedelta:
    return timedelta(seconds=STALE_HEARTBEAT_INTERVALS * heartbeat_interval_s)


def _age(now: datetime, then: datetime | None) -> timedelta | None:
    return None if then is None else now - then
