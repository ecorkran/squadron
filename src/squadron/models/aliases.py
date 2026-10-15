"""Model alias registry — maps short names to (profile, model_id) tuples.

Built-in defaults are loaded from ``src/squadron/data/models.toml``.
Users can add or override aliases via ~/.config/squadron/models.toml.
"""

from __future__ import annotations

import difflib
import logging
import tomllib
from pathlib import Path
from typing import Any, TypedDict, cast

from squadron.core.models import Effort
from squadron.core.usage import CostBasis, TokenUsage

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
    are optional metadata added by slice 121, plus ``tool_use`` (slice 266).

    ``tool_use`` is absent by default and absence means allow: a model that
    does not name the field keeps offering tools.  Absence therefore stays
    distinguishable from an explicit ``true`` and no default is written in.
    """

    private: bool
    cost_tier: str
    notes: str
    pricing: ModelPricing
    tool_use: bool
    # Slice 924 D4: absent means no budget is sent (the backend default applies).
    max_output_tokens: int
    # Slice 931 D1, D2: absent means no effort is sent (the backend default applies).
    # The alias is the per-invocation and per-step selector; there is no --effort flag.
    effort: Effort


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

    tool_use_val = table.get("tool_use")
    if isinstance(tool_use_val, bool):
        alias["tool_use"] = tool_use_val

    budget_val = table.get("max_output_tokens")
    if budget_val is not None:
        # bool is an int subclass, so `true` would otherwise read as a budget of 1.
        if isinstance(budget_val, int) and not isinstance(budget_val, bool) and budget_val >= 1:
            alias["max_output_tokens"] = budget_val
        else:
            _logger.warning(
                "Skipping max_output_tokens for alias '%s' in %s — expected an integer >= 1, got %r",
                name,
                path,
                budget_val,
            )

    effort_val = table.get("effort")
    if effort_val is not None:
        effort = _parse_effort(effort_val)
        if effort is not None:
            alias["effort"] = effort
        else:
            _logger.warning(
                "Skipping effort for alias '%s' in %s — expected one of %s "
                "(minimal and max are not supported), got %r",
                name,
                path,
                ", ".join(Effort),
                effort_val,
            )

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


def _parse_effort(raw: object) -> Effort | None:
    """``raw`` as an Effort, matched by value; ``None`` when it is not one."""
    if not isinstance(raw, str):
        return None
    try:
        return Effort(raw)
    except ValueError:
        # Not in the vocabulary; the caller logs the skip with the alias and file.
        return None


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
            f"Invalid TOML in {path}: {exc}. Fix the file or remove it to use built-in defaults."
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
                "Skipping alias '%s' in %s — expected string values for 'profile' and 'model'",
                name,
                path,
            )
    return result


def load_builtin_aliases() -> dict[str, ModelAlias]:
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
    merged = load_builtin_aliases()
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


class UnknownModelAliasError(ValueError):
    """A model name is neither an alias, a known model id, nor profile-backed (#175)."""

    def __init__(self, name: str, close_matches: list[str]) -> None:
        self.name = name
        self.close_matches = close_matches
        suggestion = f"; did you mean: {', '.join(close_matches)}?" if close_matches else ""
        super().__init__(
            f"unknown model alias '{name}'{suggestion} If this is a literal model ID, set a profile."
        )


class UnknownReviewTemplateError(ValueError):
    """A review step names a template that is not registered (#175, #184)."""

    def __init__(self, name: str, close_matches: list[str]) -> None:
        self.name = name
        self.close_matches = close_matches
        suggestion = f"; did you mean: {', '.join(close_matches)}?" if close_matches else ""
        super().__init__(f"unknown review template '{name}'{suggestion}")


def require_known_model(name: str, *, profile_source: bool) -> None:
    """Raise ``UnknownModelAliasError`` unless ``name`` can be resolved (#175).

    Passes when ``name`` is an alias, when it is a model id some alias resolves
    to (so a literal id keeps working), or when a profile source exists.
    """
    if profile_source:
        return
    aliases = get_all_aliases()
    if name in aliases or any(alias["model"] == name for alias in aliases.values()):
        return
    raise UnknownModelAliasError(name, difflib.get_close_matches(name, list(aliases), n=3))


def model_allows_tools(name: str | None) -> bool:
    """Return whether ``name`` may be offered tool schemas (slice 266).

    Absence means allow, so an unknown name, a ``None`` name, and an alias that
    does not set ``tool_use`` all return ``True`` — only an explicit
    ``tool_use = false`` denies. This is the single reader of the capability;
    call sites gate through :func:`squadron.tools.resolve_effective_tools`
    rather than testing the field themselves.
    """
    if name is None:
        return True
    alias = get_all_aliases().get(name)
    if alias is None:
        return True
    return alias.get("tool_use", True)


def model_max_output_tokens(name: str | None) -> int | None:
    """Return the per-request output budget for ``name`` (slice 924 D4).

    An unknown name, a ``None`` name, and an alias that does not set
    ``max_output_tokens`` all return ``None``: no budget is sent. This is the
    single reader of the field.
    """
    if name is None:
        return None
    alias = get_all_aliases().get(name)
    if alias is None:
        return None
    return alias.get("max_output_tokens")


def model_effort(name: str | None) -> Effort | None:
    """Return the reasoning effort for ``name`` (slice 931 D1).

    An unknown name, a ``None`` name, and an alias that does not set ``effort``
    all return ``None``: no effort is sent. This is the single reader of the field.
    """
    if name is None:
        return None
    alias = get_all_aliases().get(name)
    if alias is None:
        return None
    return alias.get("effort")


def price_usage(alias_name: str | None, usage: TokenUsage, warned: set[str]) -> float | None:
    """Price ``usage`` from ``alias_name``'s pricing table, in USD (slice 175 D3 rule 2).

    Uncached input is ``prompt - cached - cache_write``; each class is priced at its own
    ``ModelPricing`` key. Reasoning is inside ``completion`` (D1) and not priced apart.
    Returns ``None`` rather than a partial total when the alias is unknown or unpriced,
    a class with a nonzero count has no price, or the counts are missing or inconsistent.
    The missing-price and inconsistent-count cases log one WARNING per alias per
    ``warned`` set (the caller's dedupe set).
    """
    if alias_name is None:
        return None
    alias = get_all_aliases().get(alias_name)
    if alias is None:
        return None
    pricing = alias.get("pricing")
    if pricing is None or usage.prompt is None or usage.completion is None:
        return None
    cached = usage.cached or 0
    cache_write = usage.cache_write or 0
    uncached = usage.prompt - cached - cache_write
    if uncached < 0:
        _warn_once(
            alias_name,
            warned,
            "Cannot price alias '%s': cached (%d) + cache_write (%d) exceeds prompt (%d)",
            cached,
            cache_write,
            usage.prompt,
        )
        return None
    classes: tuple[tuple[str, int], ...] = (
        ("input", uncached),
        ("cache_read", cached),
        ("cache_write", cache_write),
        ("output", usage.completion),
    )
    total = 0.0
    for key, count in classes:
        if count == 0:
            continue
        price = pricing.get(key)
        if price is None:
            _warn_once(alias_name, warned, "Cannot price alias '%s': no '%s' price", key)
            return None
        total += count / 1_000_000 * price
    return total


def _warn_once(alias_name: str, warned: set[str], fmt: str, *args: object) -> None:
    """Log ``fmt`` once per alias per ``warned`` set."""
    if alias_name in warned:
        return
    warned.add(alias_name)
    _logger.warning(fmt, alias_name, *args)


def resolve_cost(
    alias_name: str | None,
    usage: TokenUsage,
    provider_cost: float | None,
    warned: set[str],
) -> tuple[float | None, CostBasis | None]:
    """Apply D3 precedence: provider-reported cost, else alias pricing, else none.

    The one place the precedence lives; a reported ``0.0`` is a real provider cost.
    """
    if provider_cost is not None:
        return provider_cost, CostBasis.PROVIDER
    priced = price_usage(alias_name, usage, warned)
    if priced is not None:
        return priced, CostBasis.ALIAS_PRICING
    return None, None
