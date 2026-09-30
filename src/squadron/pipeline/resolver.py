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

``resolve()`` returns a ``ResolvedModel``, which carries the alias's
``tool_use`` capability alongside the resolved id (slice 266). It unpacks as
the ``(model_id, profile)`` pair it used to be.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, NamedTuple

from squadron.core.models import Effort
from squadron.models.aliases import (
    model_allows_tools,
    model_effort,
    model_max_output_tokens,
    resolve_model_alias,
)

if TYPE_CHECKING:
    from squadron.pipeline.intelligence.pools.backend import PoolBackend
    from squadron.pipeline.intelligence.pools.models import (
        PoolSelection,
    )

_POOL_PREFIX = "pool:"


class ResolvedModel(NamedTuple):
    """A resolved model: its id, its profile, and whether it may use tools.

    ``resolve()`` returns this instead of a bare ``(model_id, profile)`` pair so
    the alias's ``tool_use`` capability survives resolution (slice 266). It is
    the alias table's only reader on this path: once ``resolve_model_alias``
    collapses a name to an id, the capability is unrecoverable — several aliases
    can share one model id and disagree on ``tool_use`` (``codex`` and
    ``codex-agent`` both resolve to ``gpt-5.3-codex``), so there is no sound
    reverse lookup.

    Returned by :meth:`ModelResolver.resolve_full`. :meth:`ModelResolver.resolve`
    keeps its established ``(model_id, profile)`` shape — widening it would break
    every ``model_id, profile = resolve(...)`` unpack in the codebase for the
    benefit of the few call sites that need the capability.
    """

    model_id: str
    profile: str | None
    allows_tools: bool = True
    # Slice 924 D4: the alias's per-request output budget; None sends no budget.
    max_output_tokens: int | None = None
    # Slice 931 D1, D11: the alias's reasoning effort; None sends none.
    effort: Effort | None = None


def _resolved(alias: str) -> ResolvedModel:
    """Resolve an alias to a :class:`ResolvedModel`, capability included.

    The capability is read here, while the alias name is still known — this is
    the last point at which it can be.
    """
    model_id, profile = resolve_model_alias(alias)
    return ResolvedModel(
        model_id,
        profile,
        model_allows_tools(alias),
        model_max_output_tokens(alias),
        model_effort(alias),
    )


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

    def cascade_candidates(
        self,
        action_model: str | None = None,
        step_model: str | None = None,
    ) -> tuple[str | None, ...]:
        """Return the cascade inputs in priority order.

        Mirrors the candidate ordering used by ``resolve()`` but performs
        no alias resolution and no pool selection. Pure read of the
        resolver's configuration plus the two per-call inputs.

        Used by the classification pre-scan (slice 243) to inspect which
        tier wins *before* deciding whether to invoke pool selection.
        Keeping this in the resolver makes the cascade ordering a single
        source of truth: if a future tier is added, ``resolve()`` and
        ``cascade_candidates()`` see it together and the classifier cannot
        silently miss it.
        """
        return (
            self._cli_override,
            action_model,
            step_model,
            self._pipeline_model,
            self._config_default,
        )

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
            ``resolve_model_alias()``. Callers that also need the alias's
            ``tool_use`` capability use :meth:`resolve_full`.

        Raises:
            ModelPoolNotImplemented: If the winning candidate starts with
                ``pool:`` and no ``PoolBackend`` is configured.
            ModelResolutionError: If all levels are None.
        """
        resolved = self.resolve_full(action_model, step_model)
        return resolved.model_id, resolved.profile

    def resolve_full(
        self,
        action_model: str | None = None,
        step_model: str | None = None,
    ) -> ResolvedModel:
        """Resolve as :meth:`resolve` does, keeping the alias's capability.

        The capability can only be read while the alias name is still known:
        ``resolve_model_alias`` collapses a name to a model id, and several
        aliases can share one id while disagreeing on ``tool_use`` (``codex``
        and ``codex-agent`` both resolve to ``gpt-5.3-codex``), so there is no
        sound reverse lookup. Call sites that hand tools to an agent must
        resolve through here (slice 266).
        """
        for candidate in self.cascade_candidates(action_model, step_model):
            if candidate is None:
                continue
            if candidate.startswith(_POOL_PREFIX):
                pool_name = candidate.removeprefix(_POOL_PREFIX)
                return self._resolve_pool(pool_name, action_model, step_model)
            return _resolved(candidate)

        raise ModelResolutionError(
            "No model could be resolved: all cascade levels are None. "
            "Set a pipeline model, config default, or pass --model."
        )

    def _resolve_pool(
        self,
        pool_name: str,
        action_model: str | None,
        step_model: str | None,
    ) -> ResolvedModel:
        """Resolve a pool name to a :class:`ResolvedModel`.

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
        result = _resolved(alias)

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
