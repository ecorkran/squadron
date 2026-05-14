"""Integration tests for `sq doctor` Typer command via CliRunner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.providers.base import ProfileName, ProviderType
from squadron.providers.profiles import ProviderProfile

runner = CliRunner()

_ALL_PROVIDER_ENVS = ["OPENAI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY"]

# Only API-key-based profiles so fresh-system simulation has no valid credentials.
_API_KEY_ONLY_PROFILES = {
    ProfileName.OPENAI: ProviderProfile(
        name=ProfileName.OPENAI,
        provider=ProviderType.OPENAI,
        api_key_env="OPENAI_API_KEY",
        description="OpenAI (API key)",
    ),
    ProfileName.OPENROUTER: ProviderProfile(
        name=ProfileName.OPENROUTER,
        provider=ProviderType.OPENAI,
        api_key_env="OPENROUTER_API_KEY",
        description="OpenRouter (API key)",
    ),
    ProfileName.GEMINI: ProviderProfile(
        name=ProfileName.GEMINI,
        provider=ProviderType.OPENAI,
        api_key_env="GEMINI_API_KEY",
        description="Gemini (API key)",
    ),
}


def test_doctor_fresh_system_exits_1(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No credentials + no tools → exit 1, MISSING shown."""
    for key in _ALL_PROVIDER_ENVS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)
    nonexistent = tmp_path / "providers.toml"
    nonexistent2 = tmp_path / "models.toml"
    with (
        patch(
            "squadron.cli.commands.doctor_checks.get_all_profiles", return_value=_API_KEY_ONLY_PROFILES
        ),
        patch("squadron.cli.commands.doctor_checks.providers_toml_path", return_value=nonexistent),
        patch("squadron.cli.commands.doctor_checks.models_toml_path", return_value=nonexistent2),
    ):
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "at least one provider OK" in result.output
    assert "✗" in result.output


def test_doctor_minimum_viable_exits_0(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """OPENAI_API_KEY set → exit 0, openai OK."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    nonexistent = tmp_path / "providers.toml"
    nonexistent2 = tmp_path / "models.toml"
    with (
        patch("squadron.cli.commands.doctor_checks.providers_toml_path", return_value=nonexistent),
        patch("squadron.cli.commands.doctor_checks.models_toml_path", return_value=nonexistent2),
    ):
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "openai" in result.output


def test_doctor_broken_providers_toml_exits_1(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Malformed providers.toml → exit 1, 'malformed' in output."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    bad_toml = tmp_path / "providers.toml"
    bad_toml.write_text('not = toml = "')
    nonexistent2 = tmp_path / "models.toml"
    with (
        patch("squadron.cli.commands.doctor_checks.providers_toml_path", return_value=bad_toml),
        patch("squadron.cli.commands.doctor_checks.models_toml_path", return_value=nonexistent2),
    ):
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "malformed" in result.output


def test_doctor_json_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """--json flag → valid JSON with required top-level keys."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    nonexistent = tmp_path / "providers.toml"
    nonexistent2 = tmp_path / "models.toml"
    with (
        patch("squadron.cli.commands.doctor_checks.providers_toml_path", return_value=nonexistent),
        patch("squadron.cli.commands.doctor_checks.models_toml_path", return_value=nonexistent2),
    ):
        result = runner.invoke(app, ["doctor", "--json"])
    data = json.loads(result.output)
    assert "squadron_version" in data
    assert "exit_code" in data
    assert "summary" in data
    assert "checks" in data
    summary = data["summary"]
    assert summary["ok"] + summary["missing"] + summary["warn"] == len(data["checks"])


def test_doctor_verbose_shows_more_rows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """-v output has >= line count of default output."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    nonexistent = tmp_path / "providers.toml"
    nonexistent2 = tmp_path / "models.toml"
    with (
        patch("squadron.cli.commands.doctor_checks.providers_toml_path", return_value=nonexistent),
        patch("squadron.cli.commands.doctor_checks.models_toml_path", return_value=nonexistent2),
    ):
        default_result = runner.invoke(app, ["doctor"])
        verbose_result = runner.invoke(app, ["doctor", "-v"])

    default_lines = default_result.output.count("\n")
    verbose_lines = verbose_result.output.count("\n")
    assert verbose_lines >= default_lines


def test_doctor_help() -> None:
    """--help includes the docstring text."""
    result = runner.invoke(app, ["doctor", "--help"])
    assert result.exit_code == 0
    assert "Inspect" in result.output
