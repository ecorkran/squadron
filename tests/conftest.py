"""Shared pytest fixtures for the squadron test suite."""

from __future__ import annotations

import importlib
import logging
import os
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.config import Settings
from tests import _hermetic


@pytest.fixture(scope="session")
def hermetic_git_config(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The git config that stands in for the host's global config, written once."""
    return _hermetic.write_git_config(tmp_path_factory.mktemp("hermetic") / "gitconfig")


@pytest.fixture(autouse=True)
def hermetic_environment(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    hermetic_git_config: Path,
) -> None:
    """Give every test pinned machine state instead of the developer's (issue #47).

    A test that needs a different value sets it itself with ``monkeypatch``;
    autouse fixtures run first, so the test's value wins. ``host_cf`` tests get
    the real home back, because they run the real ``cf`` against its registry.
    """
    if request.node.get_closest_marker("host_cf"):
        home = _hermetic.REAL_HOME
    else:
        # A fresh directory beside tmp_path, not inside it: tests that list
        # tmp_path must not find a home directory there.
        home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))

    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(hermetic_git_config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("TZ", _hermetic.PINNED_TZ)
    time.tzset()
    monkeypatch.setenv("COLUMNS", _hermetic.PINNED_COLUMNS)

    for var in _hermetic.credential_env_vars() | set(_hermetic.SCRUBBED_ENV_VARS):
        monkeypatch.delenv(var, raising=False)
    for var in [v for v in os.environ if v.startswith(_hermetic.SCRUBBED_ENV_PREFIXES)]:
        monkeypatch.delenv(var)

    # CliRunner runs the root callback with cwd at the repo root; the checkout's
    # .env must not reach tests. The real loader is covered by its own test.
    # import_module, not a dotted string: ``squadron.cli.app`` as an attribute
    # is the Typer object the package re-exports, not the module.
    cli_app_module = importlib.import_module("squadron.cli.app")
    monkeypatch.setattr(cli_app_module, "_load_env_file", lambda: None)


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


@pytest.fixture(autouse=True)
def restore_agent_logger_state() -> Iterator[None]:
    """Undo the global logger mutation ``sq review -v`` performs.

    ``_configure_agent_logging`` raises the level on ``squadron.providers`` (and
    siblings) and attaches a stderr handler, process-wide and permanently. In a
    test run that leaks: any later test asserting on captured records from those
    loggers sees a level that an earlier CLI invocation set, and fails for a
    reason that has nothing to do with the code under test.
    """
    names = ("squadron.providers", "squadron.tools", "squadron.review")
    saved = [
        (logging.getLogger(n), logging.getLogger(n).level, list(logging.getLogger(n).handlers))
        for n in names
    ]
    try:
        yield
    finally:
        for logger, level, handlers in saved:
            logger.setLevel(level)
            logger.handlers[:] = handlers


def run_test_git(repo: Path, *args: str) -> str:
    """Run git in a test repo, failing the test on a non-zero exit; returns stdout."""
    completed = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return completed.stdout


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """A throwaway repo on ``main`` with one commit (slice 196).

    Branch and commit tests run against this, never the project checkout. Identity and
    the default branch come from the hermetic git config.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    run_test_git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("init\n")
    run_test_git(repo, "add", "README.md")
    run_test_git(repo, "commit", "-q", "-m", "init")
    return repo
