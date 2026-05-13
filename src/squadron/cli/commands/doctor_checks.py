"""Pure check functions for `sq doctor`. Each returns CheckResult(s); no network, no subprocesses."""

from __future__ import annotations

import logging
import os
import shutil
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from squadron.models.aliases import models_toml_path
from squadron.providers.auth import resolve_auth_strategy_for_profile
from squadron.providers.profiles import get_all_profiles, providers_toml_path

logger = logging.getLogger(__name__)

SECTION_INSTALL = "Install"
SECTION_PROVIDERS = "Providers and Auth"
SECTION_INTEGRATIONS = "Integrations"
SECTION_CONFIG = "Configuration"


class CheckStatus(StrEnum):
    OK = "ok"
    MISSING = "missing"
    WARN = "warn"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: CheckStatus
    detail: str
    fix_hint: str | None = None
    section: str = ""
    required: bool = True


def check_squadron_install() -> CheckResult:
    """Report squadron package version for paste-into-issue ergonomics."""
    import importlib.metadata
    import importlib.resources
    from importlib.metadata import PackageNotFoundError

    try:
        version = importlib.metadata.version("squadron-ai")
        detail = f"version {version}"
    except PackageNotFoundError:
        try:
            source_path = str(importlib.resources.files("squadron"))
        except Exception:
            source_path = "(unknown path)"
        detail = f"(dev install) at {source_path}"

    return CheckResult(
        name="squadron",
        status=CheckStatus.OK,
        detail=detail,
        section=SECTION_INSTALL,
        required=True,
    )


def check_slash_commands(target: Path | None = None) -> CheckResult:
    """Check if sq slash commands are installed."""
    if target is None:
        target = Path("~/.claude/commands/sq").expanduser()

    if target.exists() and any(target.glob("*.md")):
        count = sum(1 for _ in target.glob("*.md"))
        return CheckResult(
            name="slash commands",
            status=CheckStatus.OK,
            detail=f"{count} command(s) at {target}",
            section=SECTION_INSTALL,
            required=False,
        )

    return CheckResult(
        name="slash commands",
        status=CheckStatus.WARN,
        detail=f"not installed at {target}",
        fix_hint="sq install-commands",
        section=SECTION_INSTALL,
        required=False,
    )


def check_provider_profiles() -> list[CheckResult]:
    """Check auth validity for each provider profile."""
    results: list[CheckResult] = []
    for name, profile in get_all_profiles().items():
        try:
            strategy = resolve_auth_strategy_for_profile(profile)
            if strategy.is_valid():
                detail = strategy.active_source or "authenticated"
                status = CheckStatus.OK
                fix_hint = None
            else:
                detail = "no credential found"
                status = CheckStatus.WARN
                fix_hint = strategy.setup_hint
        except Exception as exc:
            logger.exception("check_provider_profiles: error resolving %s", name)
            results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.WARN,
                    detail=f"internal error: {exc.__class__.__name__}",
                    fix_hint=None,
                    section=SECTION_PROVIDERS,
                    required=False,
                )
            )
            continue

        results.append(
            CheckResult(
                name=name,
                status=status,
                detail=detail,
                fix_hint=fix_hint,
                section=SECTION_PROVIDERS,
                required=False,
            )
        )

    results.sort(key=lambda r: r.name)
    return results


def check_at_least_one_provider(profile_results: list[CheckResult]) -> CheckResult:
    """Aggregate: at least one provider profile must be authenticated."""
    ok_count = sum(1 for r in profile_results if r.status == CheckStatus.OK)
    total = len(profile_results)

    if ok_count >= 1:
        return CheckResult(
            name="at least one provider OK",
            status=CheckStatus.OK,
            detail=f"{ok_count} of {total} profiles authenticated",
            section=SECTION_PROVIDERS,
            required=True,
        )

    return CheckResult(
        name="at least one provider OK",
        status=CheckStatus.MISSING,
        detail="no provider profile has usable credentials",
        fix_hint="see fix hints above, or run 'sq auth status' for details",
        section=SECTION_PROVIDERS,
        required=True,
    )


def check_context_forge() -> CheckResult:
    """Check if context-forge CLI (cf) is on PATH."""
    path = shutil.which("cf")
    if path:
        return CheckResult(
            name="context-forge",
            status=CheckStatus.OK,
            detail=f"cf at {path}",
            section=SECTION_INTEGRATIONS,
            required=False,
        )

    return CheckResult(
        name="context-forge",
        status=CheckStatus.WARN,
        detail="not on PATH",
        fix_hint="npm i -g @manta-digital/context-forge",
        section=SECTION_INTEGRATIONS,
        required=False,
    )


def check_codex_cli() -> CheckResult:
    """Check if codex CLI is on PATH."""
    path = shutil.which("codex")
    if path:
        return CheckResult(
            name="codex CLI",
            status=CheckStatus.OK,
            detail=f"codex at {path}",
            section=SECTION_INTEGRATIONS,
            required=False,
        )

    return CheckResult(
        name="codex CLI",
        status=CheckStatus.WARN,
        detail="not on PATH",
        fix_hint="npm i -g @openai/codex",
        section=SECTION_INTEGRATIONS,
        required=False,
    )


def check_claude_code_session() -> CheckResult:
    """Detect whether running inside a Claude Code session."""
    if os.environ.get("CLAUDECODE") == "1":
        return CheckResult(
            name="Claude Code session",
            status=CheckStatus.OK,
            detail="CLAUDECODE=1",
            section=SECTION_INTEGRATIONS,
            required=False,
        )

    matched = next((k for k in os.environ if k.startswith("CLAUDE_CODE_")), None)
    if matched:
        return CheckResult(
            name="Claude Code session",
            status=CheckStatus.OK,
            detail=f"{matched} set",
            section=SECTION_INTEGRATIONS,
            required=False,
        )

    return CheckResult(
        name="Claude Code session",
        status=CheckStatus.WARN,
        detail="not running inside Claude Code",
        fix_hint=None,
        section=SECTION_INTEGRATIONS,
        required=False,
    )


def check_providers_toml() -> CheckResult:
    """Check parseability of providers.toml (MISSING iff present but malformed)."""
    path = providers_toml_path()
    if not path.exists():
        return CheckResult(
            name="providers.toml",
            status=CheckStatus.OK,
            detail=f"not present at {path}",
            section=SECTION_CONFIG,
            required=True,
        )

    try:
        with open(path, "rb") as fh:
            tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        return CheckResult(
            name="providers.toml",
            status=CheckStatus.MISSING,
            detail=f"malformed: {exc}",
            fix_hint=f"repair or remove {path}",
            section=SECTION_CONFIG,
            required=True,
        )

    return CheckResult(
        name="providers.toml",
        status=CheckStatus.OK,
        detail=f"loaded from {path}",
        section=SECTION_CONFIG,
        required=True,
    )


def check_models_toml() -> CheckResult:
    """Check parseability of models.toml (MISSING iff present but malformed)."""
    path = models_toml_path()
    if not path.exists():
        return CheckResult(
            name="models.toml",
            status=CheckStatus.OK,
            detail=f"not present at {path}",
            section=SECTION_CONFIG,
            required=True,
        )

    try:
        with open(path, "rb") as fh:
            tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        return CheckResult(
            name="models.toml",
            status=CheckStatus.MISSING,
            detail=f"malformed: {exc}",
            fix_hint=f"repair or remove {path}",
            section=SECTION_CONFIG,
            required=True,
        )

    return CheckResult(
        name="models.toml",
        status=CheckStatus.OK,
        detail=f"loaded from {path}",
        section=SECTION_CONFIG,
        required=True,
    )


def check_project_env() -> CheckResult:
    """Check for project-local .env file in cwd."""
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        return CheckResult(
            name="project .env",
            status=CheckStatus.OK,
            detail="loaded from ./.env",
            section=SECTION_CONFIG,
            required=False,
        )

    return CheckResult(
        name="project .env",
        status=CheckStatus.WARN,
        detail="no project .env",
        fix_hint=None,
        section=SECTION_CONFIG,
        required=False,
    )


def run_all_checks() -> list[CheckResult]:
    """Run all doctor checks in section order; each wrapped in a process-boundary catch."""
    results: list[CheckResult] = []

    def _run(name: str, fn: object, *args: object) -> None:
        """Call fn(*args), appending result(s); emit synthetic WARN row on unexpected exception."""
        try:
            import collections.abc

            output = fn(*args)  # type: ignore[operator]
            if isinstance(output, collections.abc.Sequence) and not isinstance(output, CheckResult):
                results.extend(output)  # type: ignore[arg-type]
            else:
                results.append(output)  # type: ignore[arg-type]
        except Exception as exc:
            logger.exception("doctor check '%s' failed", name)
            results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.WARN,
                    detail=f"check failed: {exc.__class__.__name__}",
                    section="",
                    required=False,
                )
            )

    _run("squadron", check_squadron_install)
    _run("slash commands", check_slash_commands)

    profile_results: list[CheckResult] = []
    try:
        profile_results = check_provider_profiles()
        results.extend(profile_results)
    except Exception as exc:
        logger.exception("doctor check 'provider profiles' failed")
        results.append(
            CheckResult(
                name="provider profiles",
                status=CheckStatus.WARN,
                detail=f"check failed: {exc.__class__.__name__}",
                section=SECTION_PROVIDERS,
                required=False,
            )
        )

    _run("at least one provider OK", check_at_least_one_provider, profile_results)
    _run("context-forge", check_context_forge)
    _run("codex CLI", check_codex_cli)
    _run("Claude Code session", check_claude_code_session)
    _run("providers.toml", check_providers_toml)
    _run("models.toml", check_models_toml)
    _run("project .env", check_project_env)

    return results
