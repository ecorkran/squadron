"""Tests for the config CLI subcommand."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


class TestConfigSet:
    """Test config set command."""

    def test_set_user_config(
        self,
        cli_runner: CliRunner,
        patch_config_paths: dict[str, Path],
    ) -> None:
        result = cli_runner.invoke(app, ["config", "set", "cwd", "/my/path"])
        assert result.exit_code == 0
        assert "Set cwd = /my/path" in result.output
        assert "(user config)" in result.output

    def test_set_project_config(
        self,
        cli_runner: CliRunner,
        patch_config_paths: dict[str, Path],
    ) -> None:
        result = cli_runner.invoke(app, ["config", "set", "cwd", "/proj/path", "--project"])
        assert result.exit_code == 0
        assert "(project config)" in result.output

    def test_unknown_key_error(
        self,
        cli_runner: CliRunner,
        patch_config_paths: dict[str, Path],
    ) -> None:
        result = cli_runner.invoke(app, ["config", "set", "fake_key", "val"])
        assert result.exit_code == 1
        assert "Unknown config key" in result.output


class TestConfigGet:
    """Test config get command."""

    def test_get_default_value(
        self,
        cli_runner: CliRunner,
        patch_config_paths: dict[str, Path],
    ) -> None:
        result = cli_runner.invoke(app, ["config", "get", "cwd"])
        assert result.exit_code == 0
        assert "cwd = ." in result.output
        assert "(default)" in result.output

    def test_get_after_set(
        self,
        cli_runner: CliRunner,
        patch_config_paths: dict[str, Path],
    ) -> None:
        cli_runner.invoke(app, ["config", "set", "verbosity", "2"])
        result = cli_runner.invoke(app, ["config", "get", "verbosity"])
        assert result.exit_code == 0
        assert "verbosity = 2" in result.output
        assert "(user)" in result.output

    def test_unknown_key_error(
        self,
        cli_runner: CliRunner,
        patch_config_paths: dict[str, Path],
    ) -> None:
        result = cli_runner.invoke(app, ["config", "get", "nonexistent"])
        assert result.exit_code == 1
        assert "Unknown config key" in result.output


class TestConfigList:
    """Test config list command."""

    def test_lists_all_keys(
        self,
        cli_runner: CliRunner,
        patch_config_paths: dict[str, Path],
    ) -> None:
        result = cli_runner.invoke(app, ["config", "list"])
        assert result.exit_code == 0
        assert "cwd" in result.output
        assert "verbosity" in result.output
        assert "default_rules" in result.output

    def test_shows_sources(
        self,
        cli_runner: CliRunner,
        patch_config_paths: dict[str, Path],
    ) -> None:
        cli_runner.invoke(app, ["config", "set", "verbosity", "1"])
        result = cli_runner.invoke(app, ["config", "list"])
        assert "(user)" in result.output
        assert "(default)" in result.output


class TestConfigPath:
    """Test config path command."""

    def test_shows_both_paths(
        self,
        cli_runner: CliRunner,
        patch_config_paths: dict[str, Path],
    ) -> None:
        result = cli_runner.invoke(app, ["config", "path"])
        assert result.exit_code == 0
        assert "User:" in result.output
        assert "Project:" in result.output

    def test_shows_existence_status(
        self,
        cli_runner: CliRunner,
        patch_config_paths: dict[str, Path],
    ) -> None:
        # Before any set, files don't exist
        result = cli_runner.invoke(app, ["config", "path"])
        assert "not found" in result.output

        # After set, user file exists
        cli_runner.invoke(app, ["config", "set", "cwd", "/test"])
        result = cli_runner.invoke(app, ["config", "path"])
        assert "exists" in result.output
