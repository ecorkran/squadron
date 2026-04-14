"""ModelResolver — 5-level cascade model selection for pipeline execution.

Resolution priority (highest to lowest):
  1. CLI override (--model flag)
  2. Action-level model (per-action config)
  3. Step-level model (per-step config)
  4. Pipeline-level model (pipeline definition header)
  5. Config default (squadron.toml / environment default)

Pool-based model selection (``pool:`` prefix) is handled transparently:
when a candidate starts with ``pool:``, the named pool is queried via the
configured ``PoolBackend`` to select an alias, and that alias is then
resolved normally through ``resolve_model_alias``.  Pool selection fires
the optional ``on_pool_selection`` callback with a ``PoolSelection`` record.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from squadron.models.aliases import resolve_model_alias

if TYPE_CHECKING:
    from squadron.pipeline.intelligence.pools.backend import PoolBackend
    from squadron.pipeline.intelligence.pools.models import (
        PoolSelection,
    )

_POOL_PREFIX = "pool:"


class ModelResolutionError(Exception):
    """Raised when no model can be resolved from any cascade level."""


class ModelPoolNotImplemented(Exception):
    """Raised when a ``pool:`` candidate is encountered and no ``PoolBackend``
    is configured — typically a test context or a misconfigured runner.
    """


class ModelResolver:
    """Resolves the active model for a pipeline action via a 5-level cascade."""

    def __init__(
        self,
        cli_override: str | None = None,
        pipeline_model: str | None = None,
        config_default: str | None = None,
        pool_backend: PoolBackend | None = None,
        on_pool_selection: Callable[[PoolSelection], None] | None = None,
    ) -> None:
        self._cli_override = cli_override
        self._pipeline_model = pipeline_model
        self._config_default = config_default
        self._pool_backend = pool_backend
        self._on_pool_selection = on_pool_selection

    def resolve(
        self,
        action_model: str | None = None,
        step_model: str | None = None,
    ) -> tuple[str, str | None]:
        """Resolve the model to use for an action.

        Iterates the 5-level cascade and returns the first non-None value
        after alias resolution.

        Args:
            action_model: Action-level model override (highest priority
                          after CLI).
            step_model: Step-level model override.

        Returns:
            A ``(model_id, profile_or_none)`` tuple from
            ``resolve_model_alias()``.

        Raises:
            ModelPoolNotImplemented: If the winning candidate starts with
                ``pool:`` and no ``PoolBackend`` is configured.
            ModelResolutionError: If all levels are None.
        """
        candidates = (
            self._cli_override,
            action_model,
            step_model,
            self._pipeline_model,
            self._config_default,
        )
        for candidate in candidates:
            if candidate is None:
                continue
            if candidate.startswith(_POOL_PREFIX):
                pool_name = candidate.removeprefix(_POOL_PREFIX)
                return self._resolve_pool(pool_name, action_model, step_model)
            return resolve_model_alias(candidate)

        raise ModelResolutionError(
            "No model could be resolved: all cascade levels are None. "
            "Set a pipeline model, config default, or pass --model."
        )

    def _resolve_pool(
        self,
        pool_name: str,
        action_model: str | None,
        step_model: str | None,
    ) -> tuple[str, str | None]:
        """Resolve a pool name to a ``(model_id, profile)`` tuple.

        Selects an alias via the pool backend, then resolves the alias.
        Fires ``on_pool_selection`` with a fully-populated ``PoolSelection``.

        Raises:
            ModelPoolNotImplemented: if no pool backend is configured.
            PoolNotFoundError: if the named pool does not exist (propagates).
        """
        if self._pool_backend is None:
            raise ModelPoolNotImplemented(
                f"Pool-based model selection is not configured: 'pool:{pool_name}'. "
                "Ensure PoolBackend is wired into ModelResolver."
            )

        # Import here to avoid a module-level circular import; resolver.py is
        # imported by many modules, and pools imports aliases which imports
        # resolver-adjacent code.
        from squadron.pipeline.intelligence.pools.models import SelectionContext

        context = SelectionContext(
            pool_name=pool_name,
            action_type=action_model or step_model or "",
        )
        alias = self._pool_backend.select(pool_name, context)
        result = resolve_model_alias(alias)

        if self._on_pool_selection is not None:
            from squadron.pipeline.intelligence.pools.models import PoolSelection

            pool = self._pool_backend.get_pool(pool_name)
            selection = PoolSelection(
                pool_name=pool_name,
                selected_alias=alias,
                strategy=pool.strategy,
                step_name="",
                action_type=action_model or step_model or "",
                timestamp=datetime.now(UTC),
            )
            self._on_pool_selection(selection)

        return result
