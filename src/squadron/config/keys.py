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
        description=("Default provider profile for review commands (e.g. openrouter, sdk)"),
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
            "Compaction template name for summary and compaction commands. "
            "Resolved against ~/.config/squadron/compaction/ then "
            "src/squadron/data/compaction/."
        ),
    ),
    "compact.instructions": ConfigKey(
        name="compact.instructions",
        type_=str,
        default=None,
        description=(
            "Literal compaction instructions for summary and compaction commands. "
            "If set, overrides compact.template. Param substitution still applies."
        ),
    ),
    "review.max_file_size_bytes": ConfigKey(
        name="review.max_file_size_bytes",
        type_=int,
        default=100_000,
        description=(
            "Per-file injection cap (bytes) for providers that can't read files "
            "directly. Content beyond this is truncated with a marker."
        ),
    ),
    "review.max_total_injection_bytes": ConfigKey(
        name="review.max_total_injection_bytes",
        type_=int,
        default=500_000,
        description=(
            "Total injection cap (bytes) across all files/diff content for "
            "providers that can't read files directly."
        ),
    ),
    "metrology.store_dir": ConfigKey(
        name="metrology.store_dir",
        type_=str,
        default=None,
        description=(
            "Metrology store location override (defaults to "
            "~/.config/squadron/metrology/). Mainly for tests."
        ),
    ),
    "metrology.sample_budget": ConfigKey(
        name="metrology.sample_budget",
        type_=int,
        default=20,
        description=(
            "Per-project ceiling on human sample verdicts the capture "
            "surface will write. At or above this count, capture reports the "
            "ceiling and records nothing (a normal outcome, not an error)."
        ),
    ),
    "metrology.project_id": ConfigKey(
        name="metrology.project_id",
        type_=str,
        default=None,
        description=(
            "Recorded fallback project identity for repos with no git remote "
            "(project-level, via .squadron.toml). Never a filesystem path."
        ),
    ),
    "metrology.min_evidence_n": ConfigKey(
        name="metrology.min_evidence_n",
        type_=int,
        default=5,
        description=(
            "Minimum-evidence floor for metrology reports: a report cell "
            "with n below this is marked below_floor. Reported by 321, "
            "consumed by 322 to gate recommendations."
        ),
    ),
    "metrology.trend_bucket": ConfigKey(
        name="metrology.trend_bucket",
        type_=str,
        default="month",
        description=("Default time-bucket grain for 'sq metrology report trend' (--bucket overrides)."),
    ),
}


def get_default(key: str) -> object:
    """Return the default value for a config key.

    Raises KeyError if the key is not defined.
    """
    if key not in CONFIG_KEYS:
        raise KeyError(f"Unknown config key: {key}")
    return CONFIG_KEYS[key].default
