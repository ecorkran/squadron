"""Data models for model pool infrastructure.

``ModelPool`` — frozen dataclass representing a named pool of model aliases.
``SelectionContext`` — metadata passed to PoolStrategy.select().
``PoolState`` — persistent state for round-robin rotation.
Custom exceptions: PoolValidationError, PoolNotFoundError, StrategyNotFoundError.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from squadron.models.aliases import ModelAlias


class PoolValidationError(Exception):
    """Raised when a pool definition fails validation."""


class PoolNotFoundError(Exception):
    """Raised when a named pool is not found in the registry."""


class StrategyNotFoundError(Exception):
    """Raised when a strategy name is not registered."""


@dataclass(frozen=True)
class ModelPool:
    """A named group of model aliases with a selection strategy.

    ``models`` contains alias names (not raw model IDs).
    All entries are validated against the alias registry at load time.
    """

    name: str
    description: str
    models: list[str]
    strategy: str
    weights: dict[str, float] | None = None


@dataclass
class PoolState:
    """Persistent state for a single pool's round-robin rotation."""

    last_index: int = 0


@dataclass
class SelectionContext:
    """Metadata passed to PoolStrategy.select().

    ``aliases`` carries resolved alias metadata for cost-tier strategies.
    ``pool_state`` carries round-robin rotation state.
    ``task_description`` is reserved for a future capability-match strategy.
    """

    pool_name: str
    action_type: str
    run_id: str | None = None
    aliases: dict[str, ModelAlias] | None = None
    pool_state: PoolState | None = None
    task_description: str | None = None
