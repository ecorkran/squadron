"""Unit tests for doctor_checks module: data model, and each check function."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.cli.commands import doctor_checks
from squadron.cli.commands.doctor_checks import (
    CONTEXT_FORGE_INSTALL_CMD,
    CONTEXT_FORGE_PACKAGE,
    GIT_HOOKS_PATH,
    SECTION_CONFIG,
    SECTION_INSTALL,
    SECTION_INTEGRATIONS,
    SECTION_PROVIDERS,
    SECTION_SKILLS,
    CheckResult,
    CheckStatus,
    check_at_least_one_provider,
    check_claude_code_cli,
    check_codex_cli,
    check_context_forge,
    check_git_hooks,
    check_models_toml,
    check_project_env,
    check_provider_profiles,
    check_providers_toml,
    check_skill_packs,
    check_slash_commands,
    check_squadron_install,
    run_all_checks,
)

# --- T3: data model ---


def test_check_status_string_equality() -> None:
    assert CheckStatus.OK == "ok"
    assert CheckStatus.MISSING == "missing"
    assert CheckStatus.WARN == "warn"


def test_check_result_is_hashable() -> None:
    r = CheckResult(name="x", status=CheckStatus.OK, detail="d")
    assert hash(r) is not None
    s: set[CheckResult] = {r}
    assert r in s


def test_check_result_defaults() -> None:
    r = CheckResult(name="x", status=CheckStatus.OK, detail="d")
    assert r.required is True
    assert r.fix_hint is None
    assert r.section == ""


# --- T5: check_squadron_install ---


def test_check_squadron_install_installed() -> None:
    with patch("importlib.metadata.version", return_value="0.6.0"):
        result = check_squadron_install()
    assert result.status == CheckStatus.OK
    assert "0.6.0" in result.detail


def test_check_squadron_install_dev() -> None:
    from importlib.metadata import PackageNotFoundError

    with patch("importlib.metadata.version", side_effect=PackageNotFoundError("squadron-ai")):
        result = check_squadron_install()
    assert result.status == CheckStatus.OK
    assert "(dev install)" in result.detail


# --- T7: check_slash_commands ---


def test_check_slash_commands_present(tmp_path: Path) -> None:
    cmd_dir = tmp_path / "sq"
    cmd_dir.mkdir()
    (cmd_dir / "foo.md").write_text("# foo")
    result = check_slash_commands(target=cmd_dir)
    assert result.status == CheckStatus.OK


def test_check_slash_commands_empty_dir(tmp_path: Path) -> None:
    cmd_dir = tmp_path / "sq"
    cmd_dir.mkdir()
    result = check_slash_commands(target=cmd_dir)
    assert result.status == CheckStatus.WARN


def test_check_slash_commands_missing_dir(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    result = check_slash_commands(target=missing)
    assert result.status == CheckStatus.WARN
    assert result.fix_hint is not None
    assert "sq install-commands" in result.fix_hint


# --- T9: check_provider_profiles ---


def test_check_provider_profiles_none_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    results = check_provider_profiles()
    # API-key-based profiles should be WARN with no env vars set
    api_key_profiles = [r for r in results if r.name in ("openai", "openrouter", "gemini")]
    assert all(r.status == CheckStatus.WARN for r in api_key_profiles)


def test_check_provider_profiles_openai_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    results = check_provider_profiles()
    openai_row = next((r for r in results if r.name == "openai"), None)
    assert openai_row is not None
    assert openai_row.status == CheckStatus.OK
    assert "OPENAI_API_KEY" in openai_row.detail


def test_check_provider_profiles_stable_order(monkeypatch: pytest.MonkeyPatch) -> None:
    results = check_provider_profiles()
    names = [r.name for r in results]
    assert names == sorted(names)


# --- T11: check_at_least_one_provider ---


def _make_result(status: CheckStatus) -> CheckResult:
    return CheckResult(name="x", status=status, detail="d", section=SECTION_PROVIDERS, required=False)


def test_check_at_least_one_provider_none() -> None:
    results = [_make_result(CheckStatus.WARN), _make_result(CheckStatus.WARN)]
    r = check_at_least_one_provider(results)
    assert r.status == CheckStatus.MISSING


def test_check_at_least_one_provider_one_ok() -> None:
    results = [_make_result(CheckStatus.OK), _make_result(CheckStatus.WARN)]
    r = check_at_least_one_provider(results)
    assert r.status == CheckStatus.OK
    assert "1 of" in r.detail


# --- T13: check_context_forge ---


def test_check_context_forge_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/local/bin/cf")
    result = check_context_forge()
    assert result.status == CheckStatus.OK


def test_check_context_forge_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing cf is a required failure, not an optional warning (#29)."""
    monkeypatch.setattr(shutil, "which", lambda _: None)
    result = check_context_forge()
    assert result.status == CheckStatus.MISSING
    assert result.required is True
    assert result.fix_hint is not None
    assert "npm i -g" in result.fix_hint


def test_check_context_forge_fix_hint_names_a_real_package() -> None:
    """The shipped hint must not point at a package that 404s on npm (#29).

    The previous value, '@manta-digital/context-forge', was not published:
    every user who followed our own output hit a dead package.
    """
    assert CONTEXT_FORGE_PACKAGE == "@context-forge/cli"
    assert CONTEXT_FORGE_INSTALL_CMD == "npm i -g @context-forge/cli"
    assert "manta-digital" not in CONTEXT_FORGE_INSTALL_CMD


# --- T15: check_codex_cli ---


def test_check_codex_cli_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/local/bin/codex")
    result = check_codex_cli()
    assert result.status == CheckStatus.OK


def test_check_codex_cli_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    result = check_codex_cli()
    assert result.status == CheckStatus.WARN
    assert result.fix_hint is not None
    assert "@openai/codex" in result.fix_hint


# --- T17: check_claude_code_cli ---


def test_check_claude_code_cli_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/local/bin/claude")
    result = check_claude_code_cli()
    assert result.status == CheckStatus.OK
    assert "SDK provider available" in result.detail


def test_check_claude_code_cli_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    result = check_claude_code_cli()
    assert result.status == CheckStatus.WARN
    assert result.required is False
    assert result.fix_hint is not None
    assert "claude-code" in result.fix_hint


# --- T19: check_providers_toml ---


def test_check_providers_toml_absent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing = tmp_path / "providers.toml"
    monkeypatch.setattr(
        "squadron.cli.commands.doctor_checks.providers_toml_path",
        lambda: missing,
        raising=False,
    )
    with patch("squadron.cli.commands.doctor_checks.providers_toml_path", return_value=missing):
        result = check_providers_toml()
    assert result.status == CheckStatus.OK
    assert "using defaults" in result.detail


def test_check_providers_toml_valid(tmp_path: Path) -> None:
    p = tmp_path / "providers.toml"
    p.write_text('[section]\nkey = "value"\n')
    with patch("squadron.cli.commands.doctor_checks.providers_toml_path", return_value=p):
        result = check_providers_toml()
    assert result.status == CheckStatus.OK
    assert "loaded from" in result.detail


def test_check_providers_toml_malformed(tmp_path: Path) -> None:
    p = tmp_path / "providers.toml"
    p.write_text('not = toml = "')
    with patch("squadron.cli.commands.doctor_checks.providers_toml_path", return_value=p):
        result = check_providers_toml()
    assert result.status == CheckStatus.MISSING
    assert "malformed" in result.detail
    assert result.fix_hint is not None
    assert str(p) in result.fix_hint


# --- T21: check_models_toml ---


def test_check_models_toml_absent(tmp_path: Path) -> None:
    missing = tmp_path / "models.toml"
    with patch("squadron.cli.commands.doctor_checks.models_toml_path", return_value=missing):
        result = check_models_toml()
    assert result.status == CheckStatus.OK
    assert "using defaults" in result.detail


def test_check_models_toml_valid(tmp_path: Path) -> None:
    p = tmp_path / "models.toml"
    p.write_text('[aliases]\nfoo = "bar"\n')
    with patch("squadron.cli.commands.doctor_checks.models_toml_path", return_value=p):
        result = check_models_toml()
    assert result.status == CheckStatus.OK
    assert "loaded from" in result.detail


def test_check_models_toml_malformed(tmp_path: Path) -> None:
    p = tmp_path / "models.toml"
    p.write_text('not = toml = "')
    with patch("squadron.cli.commands.doctor_checks.models_toml_path", return_value=p):
        result = check_models_toml()
    assert result.status == CheckStatus.MISSING
    assert "malformed" in result.detail
    assert result.fix_hint is not None
    assert str(p) in result.fix_hint


# --- T23: check_project_env ---


def test_check_project_env_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("FOO=bar\n")
    result = check_project_env()
    assert result.status == CheckStatus.OK


def test_check_project_env_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = check_project_env()
    assert result.status == CheckStatus.WARN
    assert result.fix_hint is None


# --- check_skill_packs ---


def test_check_skill_packs_installed(tmp_path: Path) -> None:
    # The shipped-default manifest always declares the analysis prefix pack.
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()
    (analysis_dir / "tech-debt-audit.md").write_text("# audit")

    results = check_skill_packs(commands_dir=tmp_path, cwd=tmp_path)

    analysis = next(r for r in results if r.name == "analysis")
    assert analysis.status == CheckStatus.OK
    assert analysis.section == SECTION_SKILLS
    assert "installed at" in analysis.detail


def test_check_skill_packs_not_installed(tmp_path: Path) -> None:
    # Empty commands_dir → analysis is not installed.
    results = check_skill_packs(commands_dir=tmp_path / "empty", cwd=tmp_path)

    analysis = next(r for r in results if r.name == "analysis")
    assert analysis.status == CheckStatus.WARN
    assert analysis.fix_hint == "sq skills install analysis"
    assert analysis.section == SECTION_SKILLS


def test_check_skill_packs_no_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_checks, "load_effective", lambda cwd=None: None)

    results = check_skill_packs(commands_dir=tmp_path, cwd=tmp_path)

    assert len(results) == 1
    assert results[0].name == "skills.toml"
    assert results[0].status == CheckStatus.OK
    assert results[0].section == SECTION_SKILLS
    assert "no manifest" in results[0].detail


# --- T19: check_git_hooks ---


def test_check_git_hooks_installed() -> None:
    result = check_git_hooks(GIT_HOOKS_PATH, cf_available=True)

    assert result.status == CheckStatus.OK
    assert result.section == SECTION_INSTALL
    assert GIT_HOOKS_PATH in result.detail


def test_check_git_hooks_installed_but_cf_missing_is_unusable() -> None:
    """An installed hook without cf is a gate that cannot run — never an OK row."""
    result = check_git_hooks(GIT_HOOKS_PATH, cf_available=False)

    assert result.status == CheckStatus.WARN
    assert "cf" in result.detail
    assert result.fix_hint is not None


def test_check_git_hooks_wrong_value() -> None:
    result = check_git_hooks("some/other/path", cf_available=True)

    assert result.status == CheckStatus.WARN
    assert result.fix_hint == f"git config core.hooksPath {GIT_HOOKS_PATH}"


def test_check_git_hooks_unset_in_repo() -> None:
    result = check_git_hooks("", cf_available=True)

    assert result.status == CheckStatus.WARN
    assert result.fix_hint == f"git config core.hooksPath {GIT_HOOKS_PATH}"


def test_check_git_hooks_not_a_repo() -> None:
    result = check_git_hooks(None, cf_available=True)

    assert result.status == CheckStatus.OK
    assert "not a git repository" in result.detail


# --- T25: run_all_checks ---


def test_run_all_checks_has_all_sections() -> None:
    results = run_all_checks()
    sections = {r.section for r in results}
    assert SECTION_INSTALL in sections
    assert SECTION_PROVIDERS in sections
    assert SECTION_INTEGRATIONS in sections
    assert SECTION_SKILLS in sections
    assert SECTION_CONFIG in sections


def test_run_all_checks_survives_broken_check(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> CheckResult:
        raise RuntimeError("simulated failure")

    with patch(
        "squadron.cli.commands.doctor_checks.check_squadron_install",
        side_effect=RuntimeError("simulated failure"),
    ):
        results = run_all_checks()

    warn_rows = [r for r in results if r.status == CheckStatus.WARN and "check failed" in r.detail]
    assert len(warn_rows) >= 1
