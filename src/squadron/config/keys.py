"""Typed config key definitions and defaults for persistent configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigKey:
    """Definition of a persistent configuration key."""

    name: str
    type_: type
    default: object
    description: str


CONFIG_KEYS: dict[str, ConfigKey] = {
    "cwd": ConfigKey(
        name="cwd",
        type_=str,
        default=".",
        description="Default working directory for review commands",
    ),
    "verbosity": ConfigKey(
        name="verbosity",
        type_=int,
        default=0,
        description="Default verbosity (0=summary, 1=findings, 2=tool details)",
    ),
    "default_rules": ConfigKey(
        name="default_rules",
        type_=str,
        default=None,
        description="Default rules file path for code reviews",
    ),
    "default_review_profile": ConfigKey(
        name="default_review_profile",
        type_=str,
        default=None,
        description=(
            "Default provider profile for review commands (e.g. openrouter, sdk)"
        ),
    ),
    "default_model": ConfigKey(
        name="default_model",
        type_=str,
        default=None,
        description="Default model for review and spawn commands (e.g. opus, sonnet)",
    ),
    "rules_dir": ConfigKey(
        name="rules_dir",
        type_=str,
        default=None,
        description="Default rules directory for auto-detected language rules",
    ),
}


def get_default(key: str) -> object:
    """Return the default value for a config key.

    Raises KeyError if the key is not defined.
    """
    if key not in CONFIG_KEYS:
        raise KeyError(f"Unknown config key: {key}")
    return CONFIG_KEYS[key].default
