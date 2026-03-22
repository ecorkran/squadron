"""Model alias registry — maps short names to (profile, model_id) tuples.

Built-in defaults cover common Claude, OpenAI, and other models.
Users can add or override aliases via ~/.config/squadron/models.toml.
"""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Any, TypedDict, cast

_logger = logging.getLogger(__name__)


class ModelAlias(TypedDict):
    """A model alias mapping a short name to a profile and full model ID."""

    profile: str
    model: str


BUILT_IN_ALIASES: dict[str, ModelAlias] = {
    "opus": {"profile": "sdk", "model": "claude-opus-4-6"},
    "sonnet": {"profile": "sdk", "model": "claude-sonnet-4-6"},
    "haiku": {"profile": "sdk", "model": "claude-haiku-4-5-20251001"},
    "gpt4o": {"profile": "openai", "model": "gpt-4o"},
    "o3": {"profile": "openai", "model": "o3-mini"},
    "o1": {"profile": "openai", "model": "o1-preview"},
}


def models_toml_path() -> Path:
    """Return the path to the user's models.toml configuration file."""
    return Path.home() / ".config" / "squadron" / "models.toml"


def load_user_aliases() -> dict[str, ModelAlias]:
    """Load user-defined aliases from models.toml.

    Returns an empty dict if the file is missing or has no [aliases] section.
    """
    path = models_toml_path()
    if not path.is_file():
        return {}

    try:
        data = tomllib.loads(path.read_text())
    except (tomllib.TOMLDecodeError, OSError) as exc:
        _logger.warning("Failed to parse %s: %s", path, exc)
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
            result[name] = ModelAlias(profile=profile_val, model=model_val)
        else:
            _logger.warning(
                "Skipping alias '%s' in %s — "
                "expected string values for 'profile' and 'model'",
                name,
                path,
            )
    return result


def get_all_aliases() -> dict[str, ModelAlias]:
    """Return merged aliases: built-in defaults + user overrides.

    User entries override built-in aliases by name.
    """
    merged = dict(BUILT_IN_ALIASES)
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
