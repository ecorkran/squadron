"""Per-invocation spend tally for the pipeline cost cap (slice 947 D3-D6).

``RunSpend`` sums the cost of every action's stamped usage record. The executor
adds after each action and compares the total with the cap from ``read_cost_cap``.
Pure bookkeeping: no I/O, no awaiting, so concurrent fan_out branches on one event
loop can share an instance.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from squadron.config.keys import COST_CAP_KEY
from squadron.config.manager import get_config
from squadron.core.usage import UsageRecord

__all__ = ["CostCap", "RunSpend", "read_cost_cap"]

_logger = logging.getLogger(__name__)


# Where a cap came from, named in its errors (#241: flag, then pipeline YAML, then config).
RUN_FLAG_SOURCE = "--max-cost"
PIPELINE_SOURCE = "pipeline max_cost_usd"


@dataclass(frozen=True)
class CostCap:
    """A dollar cap and the setting it came from."""

    usd: float
    source: str


def read_cost_cap(
    cwd: str, *, run_override: object = None, pipeline_cap: float | None = None
) -> CostCap | None:
    """The run's dollar cap, or ``None`` when nothing sets one (no cap).

    Precedence (#241): *run_override* (``sq run --max-cost``), then *pipeline_cap*
    (the YAML's ``max_cost_usd``), then the config key. Raises ``ValueError`` naming
    the source when the winning value is anything but a positive, finite number,
    so a mistyped cap fails the run at start.
    """
    if run_override is not None:
        return CostCap(_positive_usd(run_override, RUN_FLAG_SOURCE), RUN_FLAG_SOURCE)
    if pipeline_cap is not None:
        return CostCap(_positive_usd(pipeline_cap, PIPELINE_SOURCE), PIPELINE_SOURCE)
    value = get_config(COST_CAP_KEY, cwd=cwd)
    if value is None:
        return None
    return CostCap(_positive_usd(value, COST_CAP_KEY), COST_CAP_KEY)


def _positive_usd(value: object, source: str) -> float:
    # bool is an int subclass; True is not a dollar amount.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{source} must be a positive number, got {value!r}")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{source} must be a positive number, got {value!r}")
    return float(value)


class RunSpend:
    """Known LLM spend of one ``sq run`` invocation."""

    def __init__(self, cap: CostCap | None) -> None:
        self._cap = cap
        self._known_usd = 0.0
        self._unreadable_steps: list[str] = []
        self._unpriced_aliases_warned: set[str | None] = set()

    @property
    def known_usd(self) -> float:
        """Total of every action cost seen so far; actions with no cost are not in it."""
        return self._known_usd

    def cap_error(self) -> str | None:
        """The failure text once known spend exceeds the cap; ``None`` while under it or uncapped."""
        if self._cap is None:
            return None
        if self._unreadable_steps:
            # A capped run must not run on a tally it cannot trust: fail closed.
            return (
                f"cannot enforce {self._cap.source}: unreadable usage record from step(s) "
                f"{', '.join(self._unreadable_steps)}"
            )
        if self._known_usd <= self._cap.usd:
            return None
        return (
            f"run spent ${self._known_usd:.2f} this invocation, over {self._cap.source} "
            f"${self._cap.usd:.2f}; raise the cap and resume to continue"
        )

    def add(self, raw_usage: object, *, step_name: str) -> None:
        """Fold one action's ``metadata[USAGE_KEY]`` into the total.

        ``None`` means the action spent nothing and adds nothing. An unreadable
        record is logged at ERROR and adds nothing: tallying must not crash the run.
        With a cap configured it also makes ``cap_error`` fail the run, since the
        tally can no longer be trusted.
        A record with no cost adds nothing and warns once per alias.
        """
        if raw_usage is None:
            return
        try:
            if not isinstance(raw_usage, Mapping):
                raise ValueError(f"usage is not a mapping: {raw_usage!r:.200}")
            record = UsageRecord.from_dict(cast("Mapping[str, object]", raw_usage))
        except ValueError:
            # Logged and not counted, the same posture as usage-stamp; a capped run
            # then fails in cap_error rather than running on an undercount.
            _logger.exception("step %s has an unreadable usage record; not counted in spend", step_name)
            self._unreadable_steps.append(step_name)
            return
        if record.cost_usd is None:
            self._warn_unpriced(step_name, record.alias)
            return
        self._known_usd += record.cost_usd

    def _warn_unpriced(self, step_name: str, alias: str | None) -> None:
        if alias in self._unpriced_aliases_warned:
            return
        self._unpriced_aliases_warned.add(alias)
        _logger.warning(
            "step %s (alias %s) reported no cost; the run's spend is a lower bound",
            step_name,
            alias,
        )
