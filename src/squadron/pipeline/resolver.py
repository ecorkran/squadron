"""ModelResolver — 5-level cascade model selection for pipeline execution.

Resolution priority (highest to lowest):
  1. CLI override (--model flag)
  2. Action-level model (per-action config)
  3. Step-level model (per-step config)
  4. Pipeline-level model (pipeline definition header)
  5. Config default (squadron.toml / environment default)

Pool-based model selection (pool: prefix) is reserved for slice 160.
"""

from __future__ import annotations

from squadron.models.aliases import resolve_model_alias


class ModelResolutionError(Exception):
    """Raised when no model can be resolved from any cascade level."""


class ModelPoolNotImplemented(Exception):
    """Raised when a pool: model reference is encountered.

    Pool-based model selection is out of scope until slice 160.
    """


class ModelResolver:
    """Resolves the active model for a pipeline action via a 5-level cascade."""

    def __init__(
        self,
        cli_override: str | None = None,
        pipeline_model: str | None = None,
        config_default: str | None = None,
    ) -> None:
        self._cli_override = cli_override
        self._pipeline_model = pipeline_model
        self._config_default = config_default

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
                ``pool:``.
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
            if candidate.startswith("pool:"):
                raise ModelPoolNotImplemented(
                    f"Pool-based model selection is not yet implemented "
                    f"(slate 160): '{candidate}'"
                )
            return resolve_model_alias(candidate)

        raise ModelResolutionError(
            "No model could be resolved: all cascade levels are None. "
            "Set a pipeline model, config default, or pass --model."
        )
