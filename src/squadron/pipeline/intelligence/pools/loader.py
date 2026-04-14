"""Pool loader, validator, state persistence, and select_from_pool.

Round-robin state is stored in ``~/.config/squadron/pool-state.toml``.
Pool definitions are loaded from the shipped ``src/squadron/data/pools.toml``
and user overrides from ``~/.config/squadron/pools.toml``.
"""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Any

import tomli_w

from squadron.pipeline.intelligence.pools.models import (
    ModelPool,
    PoolNotFoundError,
    PoolState,
    PoolValidationError,
    SelectionContext,
)
from squadron.pipeline.intelligence.pools.strategies import get_strategy

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config directory (extracted for monkeypatching in tests)
# ---------------------------------------------------------------------------


def _config_dir() -> Path:
    """Return the squadron config directory."""
    return Path.home() / ".config" / "squadron"


# ---------------------------------------------------------------------------
# Round-robin state persistence
# ---------------------------------------------------------------------------

_STATE_FILENAME = "pool-state.toml"


def _state_file_path() -> Path:
    return _config_dir() / _STATE_FILENAME


def load_pool_state(pool_name: str) -> PoolState:
    """Load the round-robin state for ``pool_name``.

    Returns ``PoolState(last_index=0)`` if the file is absent or the
    pool has no entry yet.
    """
    path = _state_file_path()
    if not path.is_file():
        return PoolState(last_index=0)

    try:
        data = tomllib.loads(path.read_text())
    except (tomllib.TOMLDecodeError, OSError) as exc:
        _logger.warning("Failed to read pool state from %s: %s", path, exc)
        return PoolState(last_index=0)

    pools_section: dict[str, Any] = data.get("pools", {})
    pool_entry: dict[str, Any] = pools_section.get(pool_name, {})
    last_index = pool_entry.get("last_index", 0)
    if not isinstance(last_index, int):
        _logger.warning(
            "Invalid last_index for pool %r in %s — using 0", pool_name, path
        )
        return PoolState(last_index=0)
    return PoolState(last_index=last_index)


def save_pool_state(pool_name: str, state: PoolState) -> None:
    """Persist the round-robin state for ``pool_name``.

    Reads the current file, updates the pool entry, and writes back.
    Creates the file and parent directories if absent.
    """
    path = _state_file_path()
    if path.is_file():
        try:
            data: dict[str, Any] = tomllib.loads(path.read_text())
        except (tomllib.TOMLDecodeError, OSError) as exc:
            _logger.warning(
                "Could not read existing pool state from %s: %s; starting fresh",
                path,
                exc,
            )
            data = {}
    else:
        data = {}

    pools_section: dict[str, Any] = data.setdefault("pools", {})
    pools_section[pool_name] = {"last_index": state.last_index}

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomli_w.dumps(data))


def clear_pool_state(pool_name: str) -> None:
    """Remove the round-robin state entry for ``pool_name``.

    No-op if the file is absent or the pool has no entry.
    """
    path = _state_file_path()
    if not path.is_file():
        return

    try:
        data: dict[str, Any] = tomllib.loads(path.read_text())
    except (tomllib.TOMLDecodeError, OSError) as exc:
        _logger.warning("Could not read pool state from %s: %s", path, exc)
        return

    pools_section: dict[str, Any] = data.get("pools", {})
    if pool_name not in pools_section:
        return

    del pools_section[pool_name]
    path.write_text(tomli_w.dumps(data))


# ---------------------------------------------------------------------------
# Pool loading
# ---------------------------------------------------------------------------

_POOLS_FILENAME = "pools.toml"


def _user_pools_path() -> Path:
    return _config_dir() / _POOLS_FILENAME


def _parse_pools_from_toml(
    path: Path,
    text: str,
) -> dict[str, ModelPool]:
    """Parse pool definitions from TOML text.

    Validates required fields and strategy names.  Alias validation is
    done separately in ``_validate_pool_aliases``.

    Raises:
        PoolValidationError: on any structural or strategy-name failure.
    """
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise PoolValidationError(f"Invalid TOML in {path}: {exc}") from exc

    pools_section: dict[str, Any] = data.get("pools", {})
    result: dict[str, ModelPool] = {}

    for pool_name, raw in pools_section.items():
        if not isinstance(raw, dict):
            raise PoolValidationError(
                f"Pool {pool_name!r} in {path} must be a TOML table"
            )
        entry: dict[str, Any] = raw

        models_val = entry.get("models")
        if not isinstance(models_val, list) or len(models_val) == 0:
            raise PoolValidationError(
                f"Pool {pool_name!r} in {path}: "
                "'models' must be a non-empty list of alias names"
            )
        models: list[str] = [str(m) for m in models_val]

        strategy_val = entry.get("strategy")
        if not isinstance(strategy_val, str):
            raise PoolValidationError(
                f"Pool {pool_name!r} in {path}: 'strategy' must be a string"
            )
        # Raises StrategyNotFoundError if unknown — let it propagate as-is.
        try:
            get_strategy(strategy_val)
        except Exception as exc:
            raise PoolValidationError(
                f"Pool {pool_name!r} in {path}: "
                f"unknown strategy {strategy_val!r}. {exc}"
            ) from exc

        description: str = str(entry.get("description", ""))

        weights: dict[str, float] | None = None
        weights_val = entry.get("weights")
        if isinstance(weights_val, dict):
            _validate_weights(pool_name, weights_val, models, path)
            weights = {k: float(v) for k, v in weights_val.items()}

        result[pool_name] = ModelPool(
            name=pool_name,
            description=description,
            models=models,
            strategy=strategy_val,
            weights=weights,
        )

    return result


def _validate_weights(
    pool_name: str,
    weights: dict[str, Any],
    models: list[str],
    path: Path,
) -> None:
    """Validate that all weight keys are present in models."""
    model_set = set(models)
    unknown = [k for k in weights if k not in model_set]
    if unknown:
        raise PoolValidationError(
            f"Pool {pool_name!r} in {path}: weight keys not in models: {unknown}"
        )


def _validate_pool_aliases(
    pool_name: str,
    pool: ModelPool,
    valid_aliases: dict,
) -> None:
    """Validate that every model entry in pool is a known alias.

    Raises:
        PoolValidationError: naming the bad member and listing up to 20
            valid aliases.
    """
    for member in pool.models:
        if member not in valid_aliases:
            sample = sorted(valid_aliases)[:20]
            raise PoolValidationError(
                f"Pool {pool_name!r}: unknown alias {member!r}. "
                f"Known aliases (first 20): {sample}"
            )


def load_builtin_pools() -> dict[str, ModelPool]:
    """Load and validate the shipped default pools from ``data/pools.toml``."""
    from squadron.data import data_dir
    from squadron.models.aliases import get_all_aliases

    path = data_dir() / _POOLS_FILENAME
    text = path.read_text()
    pools = _parse_pools_from_toml(path, text)
    aliases = get_all_aliases()
    for name, pool in pools.items():
        _validate_pool_aliases(name, pool, aliases)
    return pools


def load_user_pools() -> dict[str, ModelPool]:
    """Load user pool overrides from ``~/.config/squadron/pools.toml``.

    Returns ``{}`` if the file is absent.
    """
    from squadron.models.aliases import get_all_aliases

    path = _user_pools_path()
    if not path.is_file():
        return {}

    text = path.read_text()
    pools = _parse_pools_from_toml(path, text)
    aliases = get_all_aliases()
    for name, pool in pools.items():
        _validate_pool_aliases(name, pool, aliases)
    return pools


def get_all_pools() -> dict[str, ModelPool]:
    """Return merged pools: built-in defaults + user overrides.

    User entries override built-in pools by name.
    """
    merged = load_builtin_pools()
    merged.update(load_user_pools())
    return merged


def get_pool(name: str) -> ModelPool:
    """Return the named pool.

    Raises:
        PoolNotFoundError: if no pool with that name exists.
    """
    pools = get_all_pools()
    if name not in pools:
        raise PoolNotFoundError(
            f"No pool named {name!r}. Available pools: {sorted(pools)}"
        )
    return pools[name]


# ---------------------------------------------------------------------------
# Convenience selection wrapper
# ---------------------------------------------------------------------------

_ROUND_ROBIN_STRATEGY = "round-robin"


def select_from_pool(pool: ModelPool) -> str:
    """Select a model alias from ``pool`` using the pool's strategy.

    Builds a ``SelectionContext`` with resolved aliases and (for
    round-robin) the current pool state.  After a round-robin selection,
    persists the updated state.

    Returns:
        The alias name of the selected model.
    """
    from squadron.models.aliases import get_all_aliases

    aliases = get_all_aliases()
    pool_state = (
        load_pool_state(pool.name) if pool.strategy == _ROUND_ROBIN_STRATEGY else None
    )
    context = SelectionContext(
        pool_name=pool.name,
        action_type="select",
        aliases=aliases,
        pool_state=pool_state,
    )
    strategy = get_strategy(pool.strategy)
    selected: str = strategy.select(pool, context)  # type: ignore[union-attr]

    if pool.strategy == _ROUND_ROBIN_STRATEGY and context.pool_state is not None:
        save_pool_state(pool.name, context.pool_state)

    return selected
