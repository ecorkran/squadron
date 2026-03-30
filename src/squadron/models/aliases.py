"""Model alias registry — maps short names to (profile, model_id) tuples.

Built-in defaults are loaded from ``src/squadron/data/models.toml``.
Users can add or override aliases via ~/.config/squadron/models.toml.
"""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Any, TypedDict, cast

_logger = logging.getLogger(__name__)


class ModelPricing(TypedDict, total=False):
    """Per-token pricing for a model, all values in USD per 1M tokens."""

    input: float
    output: float
    cache_read: float
    cache_write: float


class _ModelAliasRequired(TypedDict):
    """Required fields for a model alias."""

    profile: str
    model: str


class ModelAlias(_ModelAliasRequired, total=False):
    """A model alias mapping a short name to a profile and full model ID.

    ``profile`` and ``model`` are always required.  The remaining fields
    are optional metadata added by slice 121.
    """

    private: bool
    cost_tier: str
    notes: str
    pricing: ModelPricing


def models_toml_path() -> Path:
    """Return the path to the user's models.toml configuration file."""
    return Path.home() / ".config" / "squadron" / "models.toml"


def _extract_metadata(
    alias: ModelAlias,
    table: dict[str, Any],
    name: str,
    path: Path,
) -> None:
    """Extract optional metadata and pricing fields from a TOML alias table."""
    private_val = table.get("private")
    if isinstance(private_val, bool):
        alias["private"] = private_val

    cost_tier_val = table.get("cost_tier")
    if isinstance(cost_tier_val, str):
        alias["cost_tier"] = cost_tier_val

    notes_val = table.get("notes")
    if isinstance(notes_val, str):
        alias["notes"] = notes_val

    pricing_val = table.get("pricing")
    if isinstance(pricing_val, dict):
        pricing = _extract_pricing(cast(dict[str, Any], pricing_val), name, path)
        if pricing:
            alias["pricing"] = pricing


def _extract_pricing(
    raw: dict[str, Any],
    name: str,
    path: Path,
) -> ModelPricing | None:
    """Build a ModelPricing dict from raw TOML pricing values."""
    pricing = ModelPricing()
    for field in ("input", "output", "cache_read", "cache_write"):
        val = raw.get(field)
        if val is None:
            continue
        if isinstance(val, (int, float)):
            pricing[field] = float(val)  # type: ignore[literal-required]
        else:
            _logger.warning(
                "Skipping pricing field '%s' for alias '%s' in %s — expected a number",
                field,
                name,
                path,
            )
    return pricing if pricing else None


def _load_aliases_from_file(path: Path) -> dict[str, ModelAlias]:
    """Parse an aliases TOML file and return a dict of ModelAlias entries.

    Returns an empty dict if the file is missing or has no [aliases] section.
    Raises ValueError on TOML parse errors.
    """
    if not path.is_file():
        return {}

    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(
            f"Invalid TOML in {path}: {exc}. "
            "Fix the file or remove it to use built-in defaults."
        ) from exc
    except OSError as exc:
        _logger.warning("Failed to read %s: %s", path, exc)
        return {}

    aliases_section = cast(dict[str, Any], data.get("aliases", {}))
    result: dict[str, ModelAlias] = {}
    for name, entry in aliases_section.items():
        if not isinstance(entry, dict):
            _logger.warning(
                "Skipping invalid alias '%s' in %s — expected a table",
                name,
                path,
            )
            continue
        table = cast(dict[str, Any], entry)
        profile_val = table.get("profile")
        model_val = table.get("model")
        if isinstance(profile_val, str) and isinstance(model_val, str):
            alias: ModelAlias = ModelAlias(profile=profile_val, model=model_val)
            _extract_metadata(alias, table, name, path)
            result[name] = alias
        else:
            _logger.warning(
                "Skipping alias '%s' in %s — "
                "expected string values for 'profile' and 'model'",
                name,
                path,
            )
    return result


def _load_builtin_aliases() -> dict[str, ModelAlias]:
    """Load built-in aliases from the shipped data/models.toml."""
    from squadron.data import data_dir

    return _load_aliases_from_file(data_dir() / "models.toml")


def load_user_aliases() -> dict[str, ModelAlias]:
    """Load user-defined aliases from models.toml.

    Returns an empty dict if the file is missing or has no [aliases] section.
    """
    return _load_aliases_from_file(models_toml_path())


def get_all_aliases() -> dict[str, ModelAlias]:
    """Return merged aliases: built-in defaults + user overrides.

    User entries override built-in aliases by name.
    """
    merged = _load_builtin_aliases()
    merged.update(load_user_aliases())
    return merged


def resolve_model_alias(name: str) -> tuple[str, str | None]:
    """Resolve a model alias to (full_model_id, profile_or_none).

    If the name matches a known alias (built-in or user), returns the
    alias's (model, profile). If not, returns (name, None) — treating
    the input as a literal model ID with no profile inference.
    """
    aliases = get_all_aliases()
    alias = aliases.get(name)
    if alias is not None:
        return alias["model"], alias["profile"]
    return name, None


def estimate_cost(
    alias_name: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
) -> float | None:
    """Estimate USD cost for a model given token counts.

    Returns None if the alias has no pricing data or insufficient
    pricing fields for the calculation.
    """
    aliases = get_all_aliases()
    alias = aliases.get(alias_name)
    if alias is None:
        return None

    pricing = alias.get("pricing")
    if pricing is None:
        return None

    input_price = pricing.get("input")
    output_price = pricing.get("output")
    if input_price is None or output_price is None:
        return None

    total = (
        input_tokens / 1_000_000 * input_price
        + output_tokens / 1_000_000 * output_price
    )

    if cached_tokens > 0:
        cache_read_price = pricing.get("cache_read")
        if cache_read_price is not None:
            total += cached_tokens / 1_000_000 * cache_read_price

    return total
