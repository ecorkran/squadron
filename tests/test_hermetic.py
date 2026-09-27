"""The environment a test actually sees is the pinned one, not the host's."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests import _hermetic

_homes_seen: list[Path] = []


@pytest.mark.parametrize("run", [1, 2])
def test_home_is_fresh_per_test(run: int, tmp_path_factory: pytest.TempPathFactory) -> None:
    home = Path.home()
    assert home != _hermetic.REAL_HOME
    assert home.is_relative_to(tmp_path_factory.getbasetemp())
    assert list(home.iterdir()) == []
    assert home not in _homes_seen
    _homes_seen.append(home)


def test_git_sees_pinned_config() -> None:
    result = subprocess.run(
        ["git", "config", "init.defaultBranch"], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == _hermetic.PINNED_DEFAULT_BRANCH
    assert os.environ["GIT_CONFIG_NOSYSTEM"] == "1"


def test_timezone_and_width_are_pinned() -> None:
    assert os.environ["TZ"] == _hermetic.PINNED_TZ
    assert os.environ["COLUMNS"] == _hermetic.PINNED_COLUMNS


def test_host_state_vars_are_scrubbed() -> None:
    scrubbed = _hermetic.credential_env_vars() | set(_hermetic.SCRUBBED_ENV_VARS)
    leaked = [v for v in os.environ if v in scrubbed]
    leaked += [v for v in os.environ if v.startswith(_hermetic.SCRUBBED_ENV_PREFIXES)]
    assert leaked == []


def test_credential_list_covers_built_in_profiles() -> None:
    names = _hermetic.credential_env_vars()
    assert {"OPENAI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY"} <= names


@pytest.mark.host_cf  # asserts the opt-out itself restores the host's home
def test_host_cf_gets_real_home() -> None:
    assert Path.home() == _hermetic.REAL_HOME
