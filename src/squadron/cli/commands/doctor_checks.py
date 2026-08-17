"""Pure check functions for `sq doctor`. Each returns CheckResult(s); no network, no subprocesses."""

from __future__ import annotations

import logging
import shutil
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from squadron.models.aliases import models_toml_path
from squadron.providers.auth import resolve_auth_strategy_for_profile
from squadron.providers.profiles import get_all_profiles, providers_toml_path
from squadron.skills.manifest import load_effective

logger = logging.getLogger(__name__)

SECTION_INSTALL = "Install"
SECTION_PROVIDERS = "Providers and Auth"
SECTION_INTEGRATIONS = "Integrations"
SECTION_SKILLS = "Skill Packs"
SECTION_CONFIG = "Configuration"

# Default install location for skill packs. Defined locally (rather than imported
# from cli.commands.skills) to keep the pure check layer free of CLI coupling.
_DEFAULT_COMMANDS_DIR = Path.home() / ".claude" / "commands"

#: The npm package providing the ``cf`` binary. Defined once and referenced
#: everywhere so a rename cannot leave a stale name in one surface — the
#: previous value (``@manta-digital/context-forge``) 404'd on npm, so every
#: user following our own instructions hit a dead package.
#:
#: ``@context-forge/cli`` is the package that declares ``bin: {cf}``. Its
#: sibling ``@context-forge/core`` is a shared library with no binary and
#: installs as a transitive dependency of this one, and the *unscoped*
#: ``context-forge`` on npm is an unrelated third party's project.
CONTEXT_FORGE_PACKAGE = "@context-forge/cli"
CONTEXT_FORGE_INSTALL_CMD = f"npm i -g {CONTEXT_FORGE_PACKAGE}"


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
        except ModuleNotFoundError:
            # We are executing inside the "squadron" package right now, so
            # this import can only fail if the package layout is broken —
            # ModuleNotFoundError is the only realistic outcome.
            source_path = "(unknown path)"
        detail = f"(dev install) at {source_path}"

    return CheckResult(
        name="squadron",
        status=CheckStatus.OK,
        detail=detail,
        section=SECTION_INSTALL,
        required=True,
    )


#: The hooksPath value that installs the frontmatter-validation pre-commit
#: gate. Defined once so the check and its fix_hint cannot drift apart.
GIT_HOOKS_PATH = ".githooks"


def check_git_hooks(hooks_path: str | None, *, cf_available: bool) -> CheckResult:
    """Report whether ``core.hooksPath`` is set to the tracked hooks directory.

    Pure — the caller resolves ``hooks_path`` via ``run_git`` and passes it
    in; this module's docstring promises no subprocesses. Not being in a git
    repository (``hooks_path is None``) is not an error — outside a repo
    there is nothing to gate. An empty string means the repo exists but the
    key is unset, which is the ordinary "not installed yet" case.

    ``cf_available`` is whether the ``cf`` binary is on PATH. The hook runs
    ``cf validate frontmatter``, so an installed hook without ``cf`` is a
    gate that cannot run — reported as WARN rather than letting an OK row
    claim a working gate.
    """
    if hooks_path is None:
        return CheckResult(
            name="git pre-commit hook",
            status=CheckStatus.OK,
            detail="not a git repository",
            section=SECTION_INSTALL,
            required=False,
        )

    if hooks_path == GIT_HOOKS_PATH:
        if not cf_available:
            return CheckResult(
                name="git pre-commit hook",
                status=CheckStatus.WARN,
                detail=(
                    f"core.hooksPath = {GIT_HOOKS_PATH}, but 'cf' is not on PATH — "
                    "the frontmatter gate cannot run"
                ),
                fix_hint=CONTEXT_FORGE_INSTALL_CMD,
                section=SECTION_INSTALL,
                required=False,
            )
        return CheckResult(
            name="git pre-commit hook",
            status=CheckStatus.OK,
            detail=f"core.hooksPath = {GIT_HOOKS_PATH}",
            section=SECTION_INSTALL,
            required=False,
        )

    return CheckResult(
        name="git pre-commit hook",
        status=CheckStatus.WARN,
        detail=f"core.hooksPath is {hooks_path!r}, not {GIT_HOOKS_PATH!r}",
        fix_hint=f"git config core.hooksPath {GIT_HOOKS_PATH}",
        section=SECTION_INSTALL,
        required=False,
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
    """Check if context-forge CLI (cf) is on PATH.

    Required, not optional. Context Forge assembles the prompts every
    dispatch sends, so ``sq run`` cannot drive a slice without it — an
    install missing ``cf`` is not a reduced install, it is a broken one.
    Reporting it as an optional integration understated that and let users
    reach a half-working state believing they were done.
    """
    path = shutil.which("cf")
    if path:
        return CheckResult(
            name="context-forge",
            status=CheckStatus.OK,
            detail=f"cf at {path}",
            section=SECTION_INTEGRATIONS,
            required=True,
        )

    return CheckResult(
        name="context-forge",
        status=CheckStatus.MISSING,
        detail="not on PATH",
        fix_hint=CONTEXT_FORGE_INSTALL_CMD,
        section=SECTION_INTEGRATIONS,
        required=True,
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


def check_claude_code_cli() -> CheckResult:
    """Check if the Claude Code CLI is installed (the SDK provider's dependency).

    The ``sdk`` provider authenticates through the Claude Code CLI's stored
    credentials, so its availability is gated on the CLI being installed -- not
    on whether the current shell is itself a Claude Code session. Informational
    only: absence means the SDK provider is unavailable, other providers still work.
    """
    path = shutil.which("claude")
    if path:
        return CheckResult(
            name="Claude Code CLI",
            status=CheckStatus.OK,
            detail=f"SDK provider available (claude at {path})",
            section=SECTION_INTEGRATIONS,
            required=False,
        )

    return CheckResult(
        name="Claude Code CLI",
        status=CheckStatus.WARN,
        detail="not installed; SDK provider unavailable (other providers OK)",
        fix_hint="npm i -g @anthropic-ai/claude-code",
        section=SECTION_INTEGRATIONS,
        required=False,
    )


def check_skill_packs(
    commands_dir: Path | None = None,
    cwd: Path | None = None,
) -> list[CheckResult]:
    """Report install status for every pack in the effective manifest.

    Pure: reads the manifest and the filesystem only. An uninstalled pack is a
    WARN (informational + actionable), not a MISSING — no pack is required.
    """
    if commands_dir is None:
        commands_dir = _DEFAULT_COMMANDS_DIR

    manifest = load_effective(cwd=cwd or Path.cwd())
    if manifest is None:
        return [
            CheckResult(
                name="skills.toml",
                status=CheckStatus.OK,
                detail="no manifest found; using defaults",
                section=SECTION_SKILLS,
                required=False,
            )
        ]

    results: list[CheckResult] = []
    for name, entry in manifest.packs.items():
        if entry.prefix is not None:
            dest = commands_dir / entry.prefix
            installed = dest.is_dir() and any(dest.iterdir())
        else:
            dest = commands_dir / "sq" / f"{entry.dispatch_file}.md"
            installed = dest.is_file()

        if installed:
            results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.OK,
                    detail=f"installed at {dest}",
                    section=SECTION_SKILLS,
                    required=False,
                )
            )
        else:
            results.append(
                CheckResult(
                    name=name,
                    status=CheckStatus.WARN,
                    detail="not installed",
                    fix_hint=f"sq skills install {name}",
                    section=SECTION_SKILLS,
                    required=False,
                )
            )

    results.sort(key=lambda r: r.name)
    return results


def check_providers_toml() -> CheckResult:
    """Check parseability of providers.toml (MISSING iff present but malformed)."""
    path = providers_toml_path()
    if not path.exists():
        return CheckResult(
            name="providers.toml",
            status=CheckStatus.OK,
            detail=f"using defaults (no file at {path})",
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
            detail=f"using defaults (no file at {path})",
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


def run_all_checks(*, git_hooks_path: str | None = None) -> list[CheckResult]:
    """Run all doctor checks in section order; each wrapped in a process-boundary catch.

    ``git_hooks_path`` is the resolved ``core.hooksPath`` value (or ``None``
    outside a git repo). Resolving it requires a subprocess, which this pure
    module's docstring forbids, so the caller resolves it via ``run_git`` and
    passes it in.
    """
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

    def _check_git_hooks_with_cf(path: str | None) -> CheckResult:
        return check_git_hooks(path, cf_available=shutil.which("cf") is not None)

    _run("git pre-commit hook", _check_git_hooks_with_cf, git_hooks_path)

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
    _run("Claude Code CLI", check_claude_code_cli)
    _run("skill packs", check_skill_packs)
    _run("providers.toml", check_providers_toml)
    _run("models.toml", check_models_toml)
    _run("project .env", check_project_env)

    return results
