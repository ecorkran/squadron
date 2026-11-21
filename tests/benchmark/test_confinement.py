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
    denied_read_roots,
    toolchain_paths,
    under_confinement,
    write_confinement,
)
from squadron.benchmark.leak_rules import LeakRules, build_leak_rules
from squadron.config.keys import CONFIG_KEYS
from squadron.providers.base import ProfileName


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


def test_the_denied_roots_are_read_back_from_the_settings_the_home_was_given(tmp_path: Path) -> None:
    real, home = tmp_path / "real", tmp_path / "home"
    write_confinement(
        home, confinement_settings(real_home=real, tree=home / "t", home=home, readable=[])
    )

    assert denied_read_roots(home) == (real,)


def test_a_home_with_no_confinement_has_no_denied_roots(tmp_path: Path) -> None:
    assert denied_read_roots(tmp_path) == ()


def _rules(base: Path) -> LeakRules:
    return build_leak_rules(
        tree=base / "tree",
        home=base / "home",
        output_dir=base / "out",
        real_home=base / "real",
        repo_root=base / "real" / "checkout",
        install_location=base / "site",
        uv_cache=base / "uvcache",
        distribution_name="squadron-ai",
        host_owner="owner",
        host_repo="repo",
    )


def test_only_a_confined_profile_gets_the_denied_roots(tmp_path: Path) -> None:
    real, home = tmp_path / "real", tmp_path / "home"
    write_confinement(
        home, confinement_settings(real_home=real, tree=home / "t", home=home, readable=[])
    )
    rules = _rules(tmp_path)

    assert under_confinement(rules, ProfileName.SDK, home).confined_roots == (real,)
    # Codex ignores the settings key, so its producer ran free and is judged as before.
    assert under_confinement(rules, ProfileName.OPENAI_OAUTH, home) == rules
