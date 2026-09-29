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


class TestBoolConfigCli:
    """`pipeline.auto_memory` round-trips through the CLI (slice 932)."""

    def test_get_default_renders_toml_spelling(
        self, cli_runner: CliRunner, patch_config_paths: dict[str, Path]
    ) -> None:
        result = cli_runner.invoke(app, ["config", "get", "pipeline.auto_memory"])
        assert result.exit_code == 0
        assert "pipeline.auto_memory = true  (default)" in result.output

    def test_set_then_get_round_trips_as_native_bool(
        self, cli_runner: CliRunner, patch_config_paths: dict[str, Path]
    ) -> None:
        set_result = cli_runner.invoke(app, ["config", "set", "pipeline.auto_memory", "false"])
        assert set_result.exit_code == 0
        assert '"pipeline.auto_memory" = false' in patch_config_paths["user"].read_text()

        get_result = cli_runner.invoke(app, ["config", "get", "pipeline.auto_memory"])
        assert "pipeline.auto_memory = false  (user)" in get_result.output

    def test_invalid_value_exits_with_error(
        self, cli_runner: CliRunner, patch_config_paths: dict[str, Path]
    ) -> None:
        result = cli_runner.invoke(app, ["config", "set", "pipeline.auto_memory", "maybe"])
        assert result.exit_code == 1
        assert "must be a boolean" in result.output
