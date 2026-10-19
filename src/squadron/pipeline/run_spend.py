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
from typing import cast

from squadron.config.keys import COST_CAP_KEY
from squadron.config.manager import get_config
from squadron.core.usage import UsageRecord

__all__ = ["RunSpend", "read_cost_cap"]

_logger = logging.getLogger(__name__)


def read_cost_cap(cwd: str) -> float | None:
    """The configured dollar cap, or ``None`` when unset (no cap).

    Raises ``ValueError`` naming the key when it is set to anything but a
    positive, finite number, so a mistyped cap fails the run at start.
    """
    value = get_config(COST_CAP_KEY, cwd=cwd)
    if value is None:
        return None
    # bool is an int subclass; True is not a dollar amount.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{COST_CAP_KEY} must be a positive number, got {value!r}")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{COST_CAP_KEY} must be a positive number, got {value!r}")
    return float(value)


class RunSpend:
    """Known LLM spend of one ``sq run`` invocation."""

    def __init__(self, cap_usd: float | None) -> None:
        self._cap_usd = cap_usd
        self._known_usd = 0.0
        self._unreadable_steps: list[str] = []
        self._unpriced_aliases_warned: set[str | None] = set()

    @property
    def known_usd(self) -> float:
        """Total of every action cost seen so far; actions with no cost are not in it."""
        return self._known_usd

    def cap_error(self) -> str | None:
        """The failure text once known spend exceeds the cap; ``None`` while under it or uncapped."""
        if self._cap_usd is None:
            return None
        if self._unreadable_steps:
            # A capped run must not run on a tally it cannot trust: fail closed.
            return (
                f"cannot enforce {COST_CAP_KEY}: unreadable usage record from step(s) "
                f"{', '.join(self._unreadable_steps)}"
            )
        if self._known_usd <= self._cap_usd:
            return None
        return (
            f"run spent ${self._known_usd:.2f} this invocation, over {COST_CAP_KEY} "
            f"${self._cap_usd:.2f}; raise the cap and resume to continue"
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
