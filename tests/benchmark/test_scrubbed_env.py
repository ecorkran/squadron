"""ScrubbedEnvironment at map level (the real-process test is added in Task 26)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from squadron.benchmark.scrubbed_env import (
    BENCHMARK_GIT_USER_EMAIL,
    SQUADRON_CONFIG_SEED,
    SYSTEM_PATH_DIRS,
    CredentialGrant,
    MissingCredentialError,
    MissingHarnessToolError,
    ScrubbedEnvironment,
)
from squadron.providers.base import ProfileName


@pytest.fixture
def tools_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "tools"
    directory.mkdir()
    for name in ("git", "uv"):
        tool = directory / name
        tool.write_text("#!/bin/sh\n")
        tool.chmod(0o755)
    return directory


@pytest.fixture
def real_home(tmp_path: Path) -> Path:
    home = tmp_path / "realhome"
    config = home / ".config" / "squadron"
    (config / "metrology").mkdir(parents=True)
    (config / "runs").mkdir()
    (config / "config.toml").write_text("a = 1\n")
    (config / "models.toml").write_text("b = 2\n")
    (config / "metrology" / "rec.json").write_text("{}")
    return home


@pytest.fixture
def harness_env(real_home: Path, tools_dir: Path) -> dict[str, str]:
    return {
        "HOME": str(real_home),
        "PATH": str(tools_dir),
        "LANG": "en_US.UTF-8",
        "GH_TOKEN": "t",
        "GITHUB_TOKEN": "t",
        "SSH_AUTH_SOCK": "/sock",
        "CLAUDE_CONFIG_DIR": "/c",
        "CODEX_HOME": "/x",
        "VIRTUAL_ENV": "/v",
        "NEW_VAR": "n",
    }


def make_env(
    tmp_path: Path, harness_env: dict[str, str], grant: CredentialGrant
) -> ScrubbedEnvironment:
    root = tmp_path / "root"
    root.mkdir(exist_ok=True)
    return ScrubbedEnvironment(root, "sb1", grant, harness_env)


def test_variables_exclude_harness_secrets(tmp_path: Path, harness_env: dict[str, str]) -> None:
    env = make_env(tmp_path, harness_env, CredentialGrant.none())
    env.prepare()
    variables = env.variables(())
    for name in (
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "SSH_AUTH_SOCK",
        "CLAUDE_CONFIG_DIR",
        "CODEX_HOME",
        "VIRTUAL_ENV",
        "NEW_VAR",
    ):
        assert name not in variables
    assert variables["LANG"] == "en_US.UTF-8"
    assert variables["HOME"] == str(env.home)
    assert variables["TZ"] == "UTC"
    assert variables["GIT_CONFIG_NOSYSTEM"] == "1"


def test_seed_copies_only_existing_seed_files(tmp_path: Path, harness_env: dict[str, str]) -> None:
    env = make_env(tmp_path, harness_env, CredentialGrant.none())
    env.prepare()
    config = env.home / ".config" / "squadron"
    assert sorted(path.name for path in config.iterdir()) == [
        "config.toml",
        "models.toml",
    ]
    assert set(path.name for path in config.iterdir()) <= set(SQUADRON_CONFIG_SEED)
    assert BENCHMARK_GIT_USER_EMAIL in (env.home / ".gitconfig").read_text()


def test_path_order_and_tool_links(tmp_path: Path, harness_env: dict[str, str]) -> None:
    env = make_env(tmp_path, harness_env, CredentialGrant.none())
    env.prepare()
    entry = tmp_path / "venv" / "bin"
    path = env.variables((entry,))["PATH"].split(":")
    assert path == [str(entry), str(env.home / "bin"), *SYSTEM_PATH_DIRS]
    assert (env.home / "bin" / "git").is_symlink()
    assert (env.home / "bin" / "uv").is_symlink()


def test_none_grant_adds_no_credential_variable(tmp_path: Path, harness_env: dict[str, str]) -> None:
    harness_env["OPENAI_API_KEY"] = "k"
    env = make_env(tmp_path, harness_env, CredentialGrant.none())
    assert "OPENAI_API_KEY" not in env.variables(())


def test_grant_variable_valued_from_harness(tmp_path: Path, harness_env: dict[str, str]) -> None:
    harness_env["OPENAI_API_KEY"] = "k"
    grant = CredentialGrant.for_profiles([ProfileName.OPENAI])
    env = make_env(tmp_path, harness_env, grant)
    assert env.variables(())["OPENAI_API_KEY"] == "k"


def test_carried_file_is_symlink_to_source(
    tmp_path: Path, harness_env: dict[str, str], real_home: Path
) -> None:
    source = real_home / ".codex" / "auth.json"
    source.parent.mkdir(parents=True)
    source.write_text("{}")
    grant = CredentialGrant.for_profiles([ProfileName.OPENAI_OAUTH])
    env = make_env(tmp_path, harness_env, grant)
    env.prepare()
    carried = env.home / ".codex" / "auth.json"
    assert carried.is_symlink()
    assert os.readlink(carried) == str(source)
    assert env.carried_paths == [carried]


def test_missing_granted_variable_raises(tmp_path: Path, harness_env: dict[str, str]) -> None:
    grant = CredentialGrant.for_profiles([ProfileName.OPENAI])
    env = make_env(tmp_path, harness_env, grant)
    with pytest.raises(MissingCredentialError, match="OPENAI_API_KEY not set"):
        env.variables(())


def test_missing_uv_raises(tmp_path: Path, harness_env: dict[str, str]) -> None:
    (Path(harness_env["PATH"]) / "uv").unlink()
    env = make_env(tmp_path, harness_env, CredentialGrant.none())
    with pytest.raises(MissingHarnessToolError, match="uv not found"):
        env.prepare()
