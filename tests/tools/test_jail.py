"""Tests for the path jail rule in isolation.

Tasks 4.2 and 5.2 exercise the jail end-to-end through the file tools. This module pins the
rule itself, so a jail regression names the jail rather than surfacing as two confusing
tool-test failures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.tools.builtin import _resolve_in_jail


@pytest.mark.parametrize(
    "path",
    [
        "file.txt",
        "sub/nested/file.txt",
        "sub/../file.txt",
        "./file.txt",
    ],
)
def test_relative_paths_inside_the_jail_are_accepted(tmp_path: Path, path: str) -> None:
    assert _resolve_in_jail(tmp_path, path) == (tmp_path / path).resolve(strict=False)


def test_absolute_path_inside_the_jail_is_accepted(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "file.txt"

    assert _resolve_in_jail(tmp_path, str(target)) == target.resolve(strict=False)


def test_jail_root_itself_is_accepted(tmp_path: Path) -> None:
    assert _resolve_in_jail(tmp_path, ".") == tmp_path


@pytest.mark.parametrize("path", ["../escape", "../../../escape", "sub/../../escape"])
def test_upward_traversal_is_rejected(tmp_path: Path, path: str) -> None:
    jail = tmp_path / "jail"
    jail.mkdir()

    assert _resolve_in_jail(jail, path) is None


def test_absolute_path_outside_the_jail_is_rejected(tmp_path: Path) -> None:
    jail = tmp_path / "jail"
    jail.mkdir()
    outside = tmp_path / "outside" / "file.txt"

    assert _resolve_in_jail(jail, str(outside)) is None


def test_symlink_pointing_outside_the_jail_is_rejected(tmp_path: Path) -> None:
    jail = tmp_path / "jail"
    jail.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    (jail / "link").symlink_to(outside)

    assert _resolve_in_jail(jail, "link/secret.txt") is None


def test_path_whose_parent_resolves_outside_the_jail_is_rejected(tmp_path: Path) -> None:
    """write_file relies on this before creating parent directories."""
    jail = tmp_path / "jail"
    jail.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (jail / "link").symlink_to(outside)

    candidate = _resolve_in_jail(jail, "link/new.txt")

    assert candidate is None


def test_sibling_directory_sharing_a_string_prefix_is_rejected(tmp_path: Path) -> None:
    """Regression test for the 'do not use startswith' rule.

    ``/tmp/.../jail_evil`` starts with ``/tmp/.../jail`` as a string but is not inside it.
    Prefix comparison accepts it; ``is_relative_to`` correctly rejects it.
    """
    jail = tmp_path / "jail"
    jail.mkdir()
    evil = tmp_path / "jail_evil"
    evil.mkdir()
    (evil / "file.txt").write_text("nope")

    assert str(evil).startswith(str(jail))  # the trap the rule avoids
    assert _resolve_in_jail(jail, str(evil / "file.txt")) is None
