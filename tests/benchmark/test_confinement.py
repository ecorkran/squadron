"""Claude Code confinement settings for benchmark producers."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from squadron.benchmark.confinement import (
    CLAUDE_SETTINGS_KEY,
    SymlinkLoopError,
    confinement_settings,
    toolchain_paths,
    write_confinement,
)
from squadron.config.keys import CONFIG_KEYS


def test_the_settings_deny_the_real_home_but_allow_the_sandbox_and_tools(tmp_path: Path) -> None:
    real, tree, home, tool = (tmp_path / name for name in ("real", "tree", "home", "tool"))

    settings = json.loads(confinement_settings(real_home=real, tree=tree, home=home, readable=[tool]))

    sandbox = settings["sandbox"]
    assert sandbox["enabled"] is True
    assert sandbox["failIfUnavailable"] is True
    assert sandbox["allowUnsandboxedCommands"] is False
    assert sandbox["filesystem"]["denyRead"] == [str(real)]
    assert sandbox["filesystem"]["allowRead"] == [str(tree), str(home), str(tool)]
    assert sandbox["filesystem"]["allowWrite"] == [str(home)]
    assert settings["permissions"] == {
        "blockReadsOutsideWorkingDirectories": True,
        "blockWritesOutsideWorkingDirectories": True,
    }


def test_toolchain_paths_list_every_link_and_install_root_under_the_real_home(
    tmp_path: Path,
) -> None:
    # fnm's shape: a per-shell folder links to an alias, which links to the install.
    root = tmp_path.resolve()
    real = root / "real"
    install = real / "fnm" / "v22" / "installation"
    (install / "bin").mkdir(parents=True)
    (install / "bin" / "node").write_text("")
    (real / "fnm" / "aliases").mkdir()
    (real / "fnm" / "aliases" / "default").symlink_to(install)
    (real / "shells").mkdir()
    (real / "shells" / "123").symlink_to(real / "fnm" / "aliases" / "default")
    outside = root / "system" / "git"
    outside.parent.mkdir()
    outside.write_text("")
    bin_dir = root / "home" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "node").symlink_to(real / "shells" / "123" / "bin" / "node")
    (bin_dir / "git").symlink_to(outside)

    paths = toolchain_paths(sorted(bin_dir.iterdir()), real)

    assert paths == [real / "shells" / "123", real / "fnm" / "aliases" / "default", install]


def test_a_symlink_loop_is_refused(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    (root / "a").symlink_to(root / "b")
    (root / "b").symlink_to(root / "a")

    with pytest.raises(SymlinkLoopError):
        toolchain_paths([root / "a"], root)


def test_writing_keeps_the_seeded_config_and_names_a_declared_key(tmp_path: Path) -> None:
    config = tmp_path / ".config" / "squadron" / "config.toml"
    config.parent.mkdir(parents=True)
    config.write_text('"pipeline.auto_memory" = false\n')

    write_confinement(tmp_path, '{"sandbox":{}}')

    with config.open("rb") as handle:
        stored = tomllib.load(handle)
    assert stored == {"pipeline.auto_memory": False, CLAUDE_SETTINGS_KEY: '{"sandbox":{}}'}
    assert CLAUDE_SETTINGS_KEY in CONFIG_KEYS
