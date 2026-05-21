"""Tests for `sq setup` Typer command."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.doctor_checks import (
    SECTION_CONFIG,
    SECTION_INSTALL,
    SECTION_INTEGRATIONS,
    SECTION_PROVIDERS,
    CheckResult,
    CheckStatus,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _ok(name: str, section: str) -> CheckResult:
    return CheckResult(name=name, status=CheckStatus.OK, detail=f"{name} ok", section=section)


def _warn(name: str, section: str, fix_hint: str | None = None) -> CheckResult:
    return CheckResult(
        name=name, status=CheckStatus.WARN, detail=f"{name} warn", fix_hint=fix_hint, section=section
    )


def _missing(
    name: str, section: str, fix_hint: str | None = "fix it", required: bool = True
) -> CheckResult:
    return CheckResult(
        name=name,
        status=CheckStatus.MISSING,
        detail=f"{name} missing",
        fix_hint=fix_hint,
        section=section,
        required=required,
    )


_MIXED_RESULTS = [
    _ok("squadron", SECTION_INSTALL),
    _warn("slash commands", SECTION_INSTALL, fix_hint="sq install-commands"),
    _missing("context-forge", SECTION_INTEGRATIONS, fix_hint="npm i -g cf"),
    _ok("openai", SECTION_PROVIDERS),
    _ok("at least one provider OK", SECTION_PROVIDERS),
    _missing("providers.toml", SECTION_CONFIG),
]

_ALL_OK_RESULTS = [
    _ok("squadron", SECTION_INSTALL),
    _ok("slash commands", SECTION_INSTALL),
    _ok("context-forge", SECTION_INTEGRATIONS),
    _ok("openai", SECTION_PROVIDERS),
    _ok("at least one provider OK", SECTION_PROVIDERS),
    _ok("providers.toml", SECTION_CONFIG),
]

_ALL_MISSING_RESULTS = [
    _ok("squadron", SECTION_INSTALL),
    _missing("slash commands", SECTION_INSTALL, fix_hint="sq install-commands", required=False),
    _missing("context-forge", SECTION_INTEGRATIONS, fix_hint="npm i -g @manta-digital/context-forge"),
    _missing("at least one provider OK", SECTION_PROVIDERS, fix_hint="configure a profile"),
    _missing("providers.toml", SECTION_CONFIG),
]


# ---------------------------------------------------------------------------
# T18a -- check-only mode with mixed fixture (MISSING present -> exit 1)
# ---------------------------------------------------------------------------


def test_check_only_mixed_exits_1() -> None:
    with patch("squadron.cli.commands.setup.run_all_checks", return_value=_MIXED_RESULTS):
        result = runner.invoke(app, ["setup", "--check-only"])
    assert result.exit_code == 1
    non_empty_lines = [line for line in result.output.splitlines() if line.strip()]
    assert len(non_empty_lines) == len(_MIXED_RESULTS)
    assert "$ " not in result.output


# ---------------------------------------------------------------------------
# T18b -- check-only mode with all-OK fixture -> exit 0 (SC4)
# ---------------------------------------------------------------------------


def test_check_only_all_ok_exits_0() -> None:
    with patch("squadron.cli.commands.setup.run_all_checks", return_value=_ALL_OK_RESULTS):
        result = runner.invoke(app, ["setup", "--check-only"])
    assert result.exit_code == 0
    non_empty_lines = [line for line in result.output.splitlines() if line.strip()]
    assert len(non_empty_lines) == len(_ALL_OK_RESULTS)
    assert "$ " not in result.output


# ---------------------------------------------------------------------------
# T19 -- non-interactive mode
# ---------------------------------------------------------------------------


def test_non_interactive_shows_commands() -> None:
    with patch("squadron.cli.commands.setup.run_all_checks", return_value=_ALL_MISSING_RESULTS):
        result = runner.invoke(app, ["setup", "--non-interactive"])
    assert result.exit_code == 1
    assert "$ npm i -g @manta-digital/context-forge" in result.output


def test_non_interactive_all_ok_exits_0() -> None:
    with patch("squadron.cli.commands.setup.run_all_checks", return_value=_ALL_OK_RESULTS):
        result = runner.invoke(app, ["setup", "--non-interactive"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# T20 -- --profile filter
# ---------------------------------------------------------------------------


_PROVIDER_RESULTS_WITH_PROFILES = [
    _ok("squadron", SECTION_INSTALL),
    CheckResult(
        name="openai",
        status=CheckStatus.WARN,
        detail="no cred",
        fix_hint="set OPENAI_API_KEY",
        section=SECTION_PROVIDERS,
        required=False,
    ),
    CheckResult(
        name="openrouter",
        status=CheckStatus.WARN,
        detail="no cred",
        fix_hint="set OPENROUTER_API_KEY",
        section=SECTION_PROVIDERS,
        required=False,
    ),
    CheckResult(
        name="gemini",
        status=CheckStatus.WARN,
        detail="no cred",
        fix_hint="set GEMINI_API_KEY",
        section=SECTION_PROVIDERS,
        required=False,
    ),
    _missing("at least one provider OK", SECTION_PROVIDERS, fix_hint="configure a profile"),
]


def test_profile_filter_shows_only_matching_provider() -> None:
    from squadron.providers.base import ProfileName, ProviderType
    from squadron.providers.profiles import ProviderProfile

    _profiles = {
        "openai": ProviderProfile(
            name=ProfileName.OPENAI, provider=ProviderType.OPENAI, api_key_env="OPENAI_API_KEY"
        ),
        "openrouter": ProviderProfile(
            name=ProfileName.OPENROUTER,
            provider=ProviderType.OPENAI,
            api_key_env="OPENROUTER_API_KEY",
        ),
        "gemini": ProviderProfile(
            name=ProfileName.GEMINI, provider=ProviderType.OPENAI, api_key_env="GEMINI_API_KEY"
        ),
    }
    with (
        patch(
            "squadron.cli.commands.setup.run_all_checks",
            return_value=_PROVIDER_RESULTS_WITH_PROFILES,
        ),
        patch("squadron.cli.commands.setup_steps.get_all_profiles", return_value=_profiles),
    ):
        result = runner.invoke(app, ["setup", "--profile", "openai", "--check-only"])

    assert "openai" in result.output
    assert "openrouter" not in result.output
    assert "gemini" not in result.output


def test_profile_unknown_exits_64() -> None:
    from squadron.providers.base import ProfileName, ProviderType
    from squadron.providers.profiles import ProviderProfile

    _profiles = {
        "openai": ProviderProfile(
            name=ProfileName.OPENAI, provider=ProviderType.OPENAI, api_key_env="OPENAI_API_KEY"
        ),
    }
    with (
        patch("squadron.cli.commands.setup.run_all_checks", return_value=_ALL_OK_RESULTS),
        patch("squadron.cli.commands.setup_steps.get_all_profiles", return_value=_profiles),
    ):
        result = runner.invoke(app, ["setup", "--profile", "nonexistent", "--check-only"])
    assert result.exit_code == 64


# ---------------------------------------------------------------------------
# T21 -- --verbose reveals OPTIONAL steps
# ---------------------------------------------------------------------------


_WARN_ONLY_RESULTS = [
    _ok("squadron", SECTION_INSTALL),
    _warn("project .env", SECTION_CONFIG),
]


def test_verbose_reveals_optional_in_non_interactive() -> None:
    with patch("squadron.cli.commands.setup.run_all_checks", return_value=_WARN_ONLY_RESULTS):
        result_default = runner.invoke(app, ["setup", "--non-interactive"])
        result_verbose = runner.invoke(app, ["setup", "--non-interactive", "--verbose"])

    default_lines = result_default.output.count("\n")
    verbose_lines = result_verbose.output.count("\n")
    assert verbose_lines > default_lines


# ---------------------------------------------------------------------------
# T22 -- interactive q-quit exits 2
# ---------------------------------------------------------------------------


def test_interactive_q_exits_2() -> None:
    with patch("squadron.cli.commands.setup.run_all_checks", return_value=_ALL_MISSING_RESULTS):
        result = runner.invoke(app, ["setup"], input="q\n")
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# T23 -- interactive recheck loop (MISSING -> OK on second call)
# ---------------------------------------------------------------------------


def test_interactive_recheck_resolves_step() -> None:
    """First recheck returns MISSING; second returns OK -> step resolves, exit 0."""
    call_count = 0

    def mock_check_context_forge() -> CheckResult:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return CheckResult(
                name="context-forge",
                status=CheckStatus.MISSING,
                detail="not found",
                section=SECTION_INTEGRATIONS,
            )
        return CheckResult(
            name="context-forge",
            status=CheckStatus.OK,
            detail="cf at /usr/local/bin/cf",
            section=SECTION_INTEGRATIONS,
        )

    single_missing = [
        CheckResult(
            name="context-forge",
            status=CheckStatus.MISSING,
            detail="not found",
            fix_hint="npm i -g cf",
            section=SECTION_INTEGRATIONS,
        )
    ]

    # Final run_all_checks call returns all OK
    all_ok_final = [_ok("context-forge", SECTION_INTEGRATIONS)]

    with (
        patch(
            "squadron.cli.commands.setup.run_all_checks",
            side_effect=[single_missing, all_ok_final],
        ),
        patch(
            "squadron.cli.commands.setup_steps._RECHECK_MAP",
            {"context-forge": mock_check_context_forge},
        ),
    ):
        # Enter once -> MISSING recheck, enter again -> OK recheck
        result = runner.invoke(app, ["setup"], input="\n\n")

    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# T24 -- internal-error path exits 3
# ---------------------------------------------------------------------------


def test_internal_error_exits_3() -> None:
    with patch("squadron.cli.commands.setup.run_all_checks", side_effect=RuntimeError("boom")):
        result = runner.invoke(app, ["setup", "--check-only"])
    assert result.exit_code == 3
    combined = result.output + (result.stderr or "")
    assert "sq doctor" in combined
