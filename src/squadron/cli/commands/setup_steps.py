"""Pure conversion layer: CheckResult → SetupStep. No I/O."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from squadron.cli.commands.doctor_checks import (
    SECTION_INSTALL,
    SECTION_INTEGRATIONS,
    SECTION_PROVIDERS,
    CheckResult,
    CheckStatus,
    check_at_least_one_provider,
    check_codex_cli,
    check_context_forge,
    check_git_hooks,
    check_models_toml,
    check_project_env,
    check_provider_profiles,
    check_providers_toml,
    check_slash_commands,
    check_squadron_install,
)
from squadron.providers.profiles import get_all_profiles

logger = logging.getLogger(__name__)


class StepKind(StrEnum):
    ALREADY_DONE = "already-done"
    INSTALL = "install"
    CONFIGURE = "configure"
    OPTIONAL = "optional"


@dataclass(frozen=True)
class SetupStep:
    title: str
    kind: StepKind
    section: str
    detail: str
    command: str | None = None
    explanation: str | None = None
    docs_anchor: str | None = None
    recheck: Callable[[], CheckResult] | None = None
    check_name: str = ""


# Map known check names to their single-check recheck functions.
# Per-profile rows are NOT pre-populated; build_steps synthesises a lambda per row.
_RECHECK_MAP: dict[str, Callable[[], CheckResult]] = {
    "squadron": check_squadron_install,
    "slash commands": check_slash_commands,
    "context-forge": check_context_forge,
    "codex CLI": check_codex_cli,
    # "Claude Code CLI" is intentionally absent: it is informational only
    # (no in-loop recheck), so setup renders it and moves on without prompting.
    "providers.toml": check_providers_toml,
    "models.toml": check_models_toml,
    "project .env": check_project_env,
}


def _recheck_aggregate() -> CheckResult:
    """Re-run provider profiles and return the aggregate result."""
    profile_results = check_provider_profiles()
    return check_at_least_one_provider(profile_results)


_RECHECK_MAP["at least one provider OK"] = _recheck_aggregate


def _recheck_git_hooks() -> CheckResult:
    """Re-resolve core.hooksPath and cf availability for the gate step."""
    import shutil

    # Imported here rather than at module scope: doctor.py is a command module
    # and this file is the pure conversion layer — the I/O happens only when
    # the recheck actually runs.
    from squadron.cli.commands.doctor import resolve_git_hooks_path

    return check_git_hooks(
        resolve_git_hooks_path(),
        cf_available=shutil.which("cf") is not None,
    )


_RECHECK_MAP["git pre-commit hook"] = _recheck_git_hooks


# Anchor map: check name → QUICKSTART section anchor.
#
# Every value must resolve to a real heading in docs/QUICKSTART.md;
# tests/cli/test_setup.py asserts this, because a remediation link that goes
# nowhere is worse than none at all — it sends a stuck user somewhere and
# strands them. The previous map pointed at "step-N-..." headings that never
# existed in that document.
#
# The providers all share one anchor deliberately: QUICKSTART documents them
# in a single comparison table, not per-provider subsections, so pointing
# each at its own heading would recreate the same dead-link problem.
DOCS_ANCHOR: dict[str, str] = {
    "slash commands": "docs/QUICKSTART.md#install",
    "context-forge": "docs/QUICKSTART.md#prerequisites",
    "codex CLI": "docs/QUICKSTART.md#configure-a-provider",
    "openai": "docs/QUICKSTART.md#configure-a-provider",
    "openrouter": "docs/QUICKSTART.md#configure-a-provider",
    "gemini": "docs/QUICKSTART.md#configure-a-provider",
    "anthropic": "docs/QUICKSTART.md#configure-a-provider",
}

# Explanation strings (1-2 sentences) shown with --verbose in interactive mode.
_EXPLANATION: dict[str, str] = {
    "squadron": "Squadron is the core CLI tool. If you're running this, it's already installed.",
    "slash commands": (
        "Slash commands let you invoke Squadron from inside a Claude Code session "
        "with /sq:run, /sq:review, etc."
    ),
    "context-forge": (
        "Squadron uses Context Forge (the cf CLI) to drive pipeline runs. "
        "Without it, sq run cannot dispatch slices."
    ),
    "codex CLI": (
        "The Codex CLI enables the codex provider for AI-assisted shell tasks. "
        "Only required if you plan to use the openai/codex provider."
    ),
    "git pre-commit hook": (
        "A tracked pre-commit hook that runs cf validate frontmatter against "
        "staged markdown, refusing commits with invalid frontmatter. Installed "
        "into the repo you run setup from."
    ),
    "Claude Code CLI": (
        "The sdk provider authenticates through the Claude Code CLI's stored credentials, "
        "so it needs the CLI installed. Optional — other providers work without it."
    ),
    "at least one provider OK": (
        "Squadron needs at least one authenticated provider profile to run pipelines. "
        "Configure one of the profiles listed above."
    ),
    "providers.toml": (
        "providers.toml configures your provider profiles. If present, it must be valid TOML."
    ),
    "models.toml": ("models.toml defines your model aliases. If present, it must be valid TOML."),
    "project .env": (
        "A project-local .env file lets you set per-project environment overrides "
        "such as OPENAI_API_KEY without touching your shell profile."
    ),
}


def _classify(result: CheckResult) -> StepKind:
    """Map a CheckResult to a StepKind. Pure function."""
    if result.status == CheckStatus.OK:
        return StepKind.ALREADY_DONE
    if result.status == CheckStatus.WARN:
        return StepKind.OPTIONAL
    # MISSING — section determines install vs configure
    if result.section in {SECTION_INSTALL, SECTION_INTEGRATIONS}:
        return StepKind.INSTALL
    return StepKind.CONFIGURE


def _make_profile_recheck(profile_name: str) -> Callable[[], CheckResult]:
    """Return a callable that re-runs provider checks for a single named profile."""

    def _recheck() -> CheckResult:
        profiles = check_provider_profiles()
        match = next((r for r in profiles if r.name == profile_name), None)
        if match is not None:
            return match
        # Profile disappeared — synthesise a WARN so we degrade gracefully.
        return CheckResult(
            name=profile_name,
            status=CheckStatus.WARN,
            detail="profile no longer found",
            section=SECTION_PROVIDERS,
            required=False,
        )

    return _recheck


def _human_title(result: CheckResult) -> str:
    """Derive a human-readable step title from a CheckResult."""
    _TITLE_MAP: dict[str, str] = {
        "squadron": "Squadron installed",
        "slash commands": "Install slash commands",
        "git pre-commit hook": "Install frontmatter pre-commit gate",
        "context-forge": "Install Context Forge",
        "codex CLI": "Install Codex CLI",
        "Claude Code CLI": "Claude Code CLI",
        "at least one provider OK": "At least one provider authenticated",
        "providers.toml": "providers.toml valid",
        "models.toml": "models.toml valid",
        "project .env": "Project .env file",
    }
    return _TITLE_MAP.get(result.name, result.name)


def build_steps(results: list[CheckResult], profile: str | None = None) -> list[SetupStep]:
    """Convert a list of CheckResults into ordered SetupSteps.

    Args:
        results: Output of run_all_checks().
        profile: If set, filter Providers section to this profile + aggregate.

    Raises:
        ValueError: If profile is not in get_all_profiles().
    """
    if profile is not None:
        known_profiles = set(get_all_profiles().keys())
        if profile not in known_profiles:
            raise ValueError(
                f"Unknown profile {profile!r}. "
                f"Available: {', '.join(sorted(known_profiles)) or '(none)'}"
            )

    steps: list[SetupStep] = []
    for result in results:
        # Apply profile filter: drop non-matching per-profile Providers rows.
        if profile is not None and result.section == SECTION_PROVIDERS:
            is_aggregate = result.name == "at least one provider OK"
            if not is_aggregate and result.name != profile:
                continue

        kind = _classify(result)

        # Determine recheck callable.
        recheck: Callable[[], CheckResult] | None = _RECHECK_MAP.get(result.name)
        if (
            recheck is None
            and result.section == SECTION_PROVIDERS
            and result.name != "at least one provider OK"
        ):
            recheck = _make_profile_recheck(result.name)

        step = SetupStep(
            title=_human_title(result),
            kind=kind,
            section=result.section,
            detail=result.detail,
            command=result.fix_hint,
            explanation=_EXPLANATION.get(result.name),
            docs_anchor=DOCS_ANCHOR.get(result.name),
            recheck=recheck,
            check_name=result.name,
        )
        steps.append(step)

    return steps
