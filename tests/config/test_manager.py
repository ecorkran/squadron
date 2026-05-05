"""Tests for config manager — load, merge, persist."""

from __future__ import annotations

from pathlib import Path

import pytest
import tomli_w

from squadron.config.manager import (
    get_config,
    load_config,
    resolve_config_source,
    set_config,
)


class TestLoadConfig:
    """Test config loading and precedence merging."""

    def test_defaults_when_no_files(self, patch_config_paths: dict[str, Path]) -> None:
        config = load_config()
        assert config["cwd"] == "."
        assert config["verbosity"] == 0
        assert config["default_rules"] is None
        assert config["default_model"] is None

    def test_user_config_overrides_defaults(self, patch_config_paths: dict[str, Path]) -> None:
        user_file = patch_config_paths["user"]
        with open(user_file, "wb") as f:
            tomli_w.dump({"verbosity": 1, "cwd": "/home/user/project"}, f)

        config = load_config()
        assert config["verbosity"] == 1
        assert config["cwd"] == "/home/user/project"
        assert config["default_rules"] is None  # still default

    def test_project_config_overrides_user(self, patch_config_paths: dict[str, Path]) -> None:
        user_file = patch_config_paths["user"]
        project_file = patch_config_paths["project"]

        with open(user_file, "wb") as f:
            tomli_w.dump({"verbosity": 1, "cwd": "/user/path"}, f)
        with open(project_file, "wb") as f:
            tomli_w.dump({"cwd": "./project/path"}, f)

        config = load_config()
        assert config["cwd"] == "./project/path"  # project wins
        assert config["verbosity"] == 1  # user value (no project override)

    def test_precedence_chain(self, patch_config_paths: dict[str, Path]) -> None:
        user_file = patch_config_paths["user"]
        project_file = patch_config_paths["project"]

        with open(user_file, "wb") as f:
            tomli_w.dump(
                {"cwd": "/user", "verbosity": 1, "default_rules": "user.md"},
                f,
            )
        with open(project_file, "wb") as f:
            tomli_w.dump({"cwd": "/project", "default_rules": "project.md"}, f)

        config = load_config()
        assert config["cwd"] == "/project"
        assert config["verbosity"] == 1
        assert config["default_rules"] == "project.md"

    def test_unknown_keys_in_files_ignored(self, patch_config_paths: dict[str, Path]) -> None:
        user_file = patch_config_paths["user"]
        with open(user_file, "wb") as f:
            tomli_w.dump({"unknown_key": "value", "verbosity": 2}, f)

        config = load_config()
        assert "unknown_key" not in config
        assert config["verbosity"] == 2


class TestGetConfig:
    """Test single-key access."""

    def test_returns_single_value(self, patch_config_paths: dict[str, Path]) -> None:
        assert get_config("cwd") == "."

    def test_unknown_key_raises(self, patch_config_paths: dict[str, Path]) -> None:
        with pytest.raises(KeyError, match="Unknown config key"):
            get_config("nonexistent")


class TestSetConfig:
    """Test config persistence."""

    def test_creates_user_config(self, patch_config_paths: dict[str, Path]) -> None:
        set_config("cwd", "/new/path")
        assert get_config("cwd") == "/new/path"
        assert patch_config_paths["user"].exists()

    def test_creates_directories(self, tmp_path: Path) -> None:
        from unittest.mock import patch as mock_patch

        deep_path = tmp_path / "a" / "b" / "c" / "config.toml"
        with (
            mock_patch(
                "squadron.config.manager.user_config_path",
                return_value=deep_path,
            ),
            mock_patch(
                "squadron.config.manager.project_config_path",
                return_value=tmp_path / "proj" / ".squadron.toml",
            ),
        ):
            set_config("cwd", "/test")
            assert deep_path.exists()

    def test_project_flag_writes_project_config(self, patch_config_paths: dict[str, Path]) -> None:
        set_config("cwd", "/project/dir", project=True)
        assert patch_config_paths["project"].exists()
        assert get_config("cwd") == "/project/dir"

    def test_coerces_int_value(self, patch_config_paths: dict[str, Path]) -> None:
        set_config("verbosity", "2")
        assert get_config("verbosity") == 2

    def test_unknown_key_raises(self, patch_config_paths: dict[str, Path]) -> None:
        with pytest.raises(KeyError, match="Unknown config key"):
            set_config("bogus", "value")

    def test_preserves_existing_keys(self, patch_config_paths: dict[str, Path]) -> None:
        set_config("cwd", "/first")
        set_config("verbosity", "1")
        assert get_config("cwd") == "/first"
        assert get_config("verbosity") == 1

    def test_default_model_round_trip(self, patch_config_paths: dict[str, Path]) -> None:
        set_config("default_model", "opus")
        assert get_config("default_model") == "opus"


class TestResolveConfigSource:
    """Test source resolution."""

    def test_default_source(self, patch_config_paths: dict[str, Path]) -> None:
        assert resolve_config_source("cwd") == "default"

    def test_user_source(self, patch_config_paths: dict[str, Path]) -> None:
        set_config("cwd", "/user/path")
        assert resolve_config_source("cwd") == "user"

    def test_project_source(self, patch_config_paths: dict[str, Path]) -> None:
        set_config("cwd", "/proj/path", project=True)
        assert resolve_config_source("cwd") == "project"

    def test_project_overrides_user_source(self, patch_config_paths: dict[str, Path]) -> None:
        set_config("cwd", "/user")
        set_config("cwd", "/project", project=True)
        assert resolve_config_source("cwd") == "project"

    def test_unknown_key_raises(self, patch_config_paths: dict[str, Path]) -> None:
        with pytest.raises(KeyError, match="Unknown config key"):
            resolve_config_source("fake_key")
