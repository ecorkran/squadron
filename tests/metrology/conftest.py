"""Shared fixtures for metrology tests.

Provides isolated tmp_path git repos (with / without a remote), a
project-config writer for ``.squadron.toml``, and user-config isolation so
that a developer's real ``~/.config/squadron/config.toml`` can never leak a
recorded ``metrology.project_id`` into a test that asserts its absence.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
import tomli_w


def _git(*args: str, cwd: Path) -> None:
    """Run a git command in ``cwd``, raising on failure (test setup only)."""
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git("init", cwd=path)
    # Local identity so commits (if any) don't depend on global git config.
    _git("config", "user.email", "test@example.com", cwd=path)
    _git("config", "user.name", "Test", cwd=path)


@pytest.fixture
def isolated_user_config(tmp_path: Path) -> Iterator[Path]:
    """Redirect the user-level config file to an empty temp file.

    Without this, ``get_config`` merges the real user config, which could
    supply a ``metrology.project_id`` and mask the no-identity path.
    """
    user_file = tmp_path / "user-config" / "config.toml"
    user_file.parent.mkdir(parents=True, exist_ok=True)
    with patch("squadron.config.manager.user_config_path", return_value=user_file):
        yield user_file


@pytest.fixture
def repo_with_remote(tmp_path: Path, isolated_user_config: Path) -> Path:
    """A git repo whose origin remote is a known URL."""
    repo = tmp_path / "repo-remote"
    _init_repo(repo)
    _git(
        "remote",
        "add",
        "origin",
        "https://github.com/manta/example-repo.git",
        cwd=repo,
    )
    return repo


@pytest.fixture
def repo_no_remote(tmp_path: Path, isolated_user_config: Path) -> Path:
    """A git repo with no origin remote."""
    repo = tmp_path / "repo-no-remote"
    _init_repo(repo)
    return repo


@pytest.fixture
def non_repo_dir(tmp_path: Path, isolated_user_config: Path) -> Path:
    """A plain directory that is not a git repository."""
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    return plain


@pytest.fixture
def write_project_config() -> Callable[[Path, dict[str, object]], Path]:
    """Return a writer that dumps keys into ``<cwd>/.squadron.toml``."""

    def _write(cwd: Path, values: dict[str, object]) -> Path:
        path = cwd / ".squadron.toml"
        existing: dict[str, object] = {}
        if path.is_file():
            import tomllib

            with open(path, "rb") as handle:
                existing = dict(tomllib.load(handle))
        existing.update(values)
        with open(path, "wb") as handle:
            tomli_w.dump(existing, handle)
        return path

    return _write
