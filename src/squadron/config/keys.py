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
    "metrology.graduate_match_rate": ConfigKey(
        name="metrology.graduate_match_rate",
        type_=float,
        default=0.9,
        description=(
            "Agreement at or above which, and at or above metrology.min_evidence_n, "
            "a (template, model) pairing is recommended for GRADUATE."
        ),
    ),
    "metrology.tighten_match_rate": ConfigKey(
        name="metrology.tighten_match_rate",
        type_=float,
        default=0.6,
        description=(
            "Agreement at or below which a TIGHTEN warning is emitted, "
            "regardless of evidence volume (not floor-gated)."
        ),
    ),
    "metrology.residual_sample_rate": ConfigKey(
        name="metrology.residual_sample_rate",
        type_=float,
        default=0.1,
        description=(
            "Fraction of a graduated config's unsampled judge results offered "
            "for continued residual spot-checking via 'sq metrology offers'."
        ),
    ),
    "metrology.audit_variance_runs": ConfigKey(
        name="metrology.audit_variance_runs",
        type_=int,
        default=3,
        description=(
            "Runs per project in an audit variance series. Three observes a "
            "spread without claiming statistical rigor; raise it to buy "
            "confidence in the measured noise floor."
        ),
    ),
    "metrology.audit_timeout_s": ConfigKey(
        name="metrology.audit_timeout_s",
        type_=int,
        default=3600,
        description=(
            "Wall-clock cap per audit run, in seconds. Bounds pathology (a "
            "hung or stalled agent stream); it does not pace normal runs, "
            "which on a large fanned-out repo are legitimately slow."
        ),
    ),
    "metrology.audit_rate_limit_retries": ConfigKey(
        name="metrology.audit_rate_limit_retries",
        type_=int,
        default=10,
        description=(
            "How many times a rate-limited audit retries before giving up. "
            "Ten was exactly sufficient on a small repo, so larger repos with "
            "subagent fan-out may need more."
        ),
    ),
    "metrology.audit_rate_limit_cap_s": ConfigKey(
        name="metrology.audit_rate_limit_cap_s",
        type_=int,
        default=60,
        description=(
            "Ceiling on the exponential rate-limit backoff, in seconds. The "
            "delay doubles per attempt until it reaches this value."
        ),
    ),
    "metrology.audit_run_cooldown_s": ConfigKey(
        name="metrology.audit_run_cooldown_s",
        type_=int,
        default=60,
        description=(
            "Pause between runs in a variance series, in seconds. Lowers the "
            "request rate a campaign presents rather than absorbing throttles "
            "after the fact. Not applied before the first run or after the last."
        ),
    ),
    "metrology.audit_profile": ConfigKey(
        name="metrology.audit_profile",
        type_=str,
        default=None,
        description=("Provider profile for audit runs. Unset falls back to the review default."),
    ),
    "metrology.audit_model": ConfigKey(
        name="metrology.audit_model",
        type_=str,
        default=None,
        description=(
            "Model for audit runs. Unset sends no --model, so the CLI picks "
            "its own default — measured as a 1M-context Opus, the most "
            "expensive option available. Pin it: an unpinned model is not a "
            "fixed instrument, so a floor measured today is not comparable "
            "to one measured after that default shifts."
        ),
    ),
    "metrology.preemption_fragment_dir": ConfigKey(
        name="metrology.preemption_fragment_dir",
        type_=str,
        default="~/.config/squadron/metrology/preemption",
        description=(
            "Directory 'sq metrology preempt generate' writes pre-emption "
            "fragment files into, one per project. A pipeline opts into a "
            "fragment by naming its path explicitly, so moving this only "
            "affects where generation writes — never what dispatch reads."
        ),
    ),
    "events.timeout_seconds": ConfigKey(
        name="events.timeout_seconds",
        type_=int,
        default=30,
        description=(
            "Per-action timeout (seconds) for event action execution. "
            "Exceeding it is treated as a Fail, attributed to the action."
        ),
    ),
    "agent.max_tool_iterations": ConfigKey(
        name="agent.max_tool_iterations",
        type_=int,
        default=20,
        description=(
            "Max agentic-loop turns for OpenAI-compatible agents before the "
            "max-iterations guard fires a ProviderError."
        ),
    ),
    "agent.max_history_chars": ConfigKey(
        name="agent.max_history_chars",
        type_=int,
        default=400_000,
        description=(
            "Accumulated message-history size (characters) that triggers the "
            "agentic loop's history-budget guard for OpenAI-compatible agents."
        ),
    ),
    "cf.mcp_command": ConfigKey(
        name="cf.mcp_command",
        type_=str,
        default="npx -y @context-forge/mcp",
        description=(
            "Launch command for the context-forge MCP stdio server, split with "
            "shlex.split. Override for local-dev builds or to pin a version."
        ),
    ),
    "cf.mcp_timeout_s": ConfigKey(
        name="cf.mcp_timeout_s",
        type_=int,
        default=60,
        description=(
            "Wall-clock cap in seconds per context-forge MCP bridge call, "
            "covering spawn, initialize, and the tool call together."
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
