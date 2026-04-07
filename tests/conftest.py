"""Shared pytest fixtures for the squadron test suite."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.config import Settings


@pytest.fixture
def user_config_dir(tmp_path: Path) -> Path:
    """Temporary directory standing in for ``~/.config/squadron/``."""
    config_dir = tmp_path / "user_config" / ".config" / "squadron"
    config_dir.mkdir(parents=True)
    return config_dir


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Temporary directory standing in for a project root."""
    proj = tmp_path / "project"
    proj.mkdir()
    return proj


@pytest.fixture
def patch_config_paths(user_config_dir: Path, project_dir: Path):
    """Redirect both user and project config paths to temp files.

    Applies across ``squadron.config.manager`` and every CLI command module
    that imports the path helpers directly.
    """
    user_file = user_config_dir / "config.toml"
    project_file = project_dir / ".squadron.toml"

    targets = [
        "squadron.config.manager.user_config_path",
        "squadron.cli.commands.config.user_config_path",
    ]
    project_targets = [
        "squadron.config.manager.project_config_path",
        "squadron.cli.commands.config.project_config_path",
    ]

    patches = [patch(t, return_value=user_file) for t in targets]
    patches += [patch(t, return_value=project_file) for t in project_targets]

    for p in patches:
        p.start()
    yield {"user": user_file, "project": project_file}
    for p in patches:
        p.stop()


@pytest.fixture
def test_settings() -> Settings:
    """Settings instance with test defaults, ignoring any .env file on disk."""
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        anthropic_api_key="test-api-key",
        log_level="DEBUG",
        log_format="text",
    )
