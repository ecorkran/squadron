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
    "default_model_arch": ConfigKey(
        name="default_model_arch",
        type_=str,
        default=None,
        description="Default model for 'review arch' (overrides default_model)",
    ),
    "default_model_slice": ConfigKey(
        name="default_model_slice",
        type_=str,
        default=None,
        description="Default model for 'review slice' (overrides default_model)",
    ),
    "default_model_tasks": ConfigKey(
        name="default_model_tasks",
        type_=str,
        default=None,
        description="Default model for 'review tasks' (overrides default_model)",
    ),
    "default_model_code": ConfigKey(
        name="default_model_code",
        type_=str,
        default=None,
        description="Default model for 'review code' (overrides default_model)",
    ),
    "rules_dir": ConfigKey(
        name="rules_dir",
        type_=str,
        default=None,
        description="Default rules directory for auto-detected language rules",
    ),
    "compact.template": ConfigKey(
        name="compact.template",
        type_=str,
        default="minimal",
        description=(
            "Compaction template name for the interactive PreCompact hook. "
            "Resolved against ~/.config/squadron/compaction/ then "
            "src/squadron/data/compaction/."
        ),
    ),
    "compact.instructions": ConfigKey(
        name="compact.instructions",
        type_=str,
        default=None,
        description=(
            "Literal compaction instructions for the interactive PreCompact hook. "
            "If set, overrides compact.template. Param substitution still applies."
        ),
    ),
}


def get_default(key: str) -> object:
    """Return the default value for a config key.

    Raises KeyError if the key is not defined.
    """
    if key not in CONFIG_KEYS:
        raise KeyError(f"Unknown config key: {key}")
    return CONFIG_KEYS[key].default
