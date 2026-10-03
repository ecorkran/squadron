"""Tests for the per-target skill-pack layout table (slice 928, D3, D6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.skills.models import PackEntry
from squadron.skills.pack_layouts import PACK_LAYOUTS
from squadron.skills.targets import CommandTarget

PREFIX_ENTRY = PackEntry(source="bundled", prefix="demo")
DISPATCH_ENTRY = PackEntry(source="bundled", dispatch_file="hello")


def test_pack_layouts_covers_every_target() -> None:
    assert set(PACK_LAYOUTS) == set(CommandTarget)


# ---------------------------------------------------------------------------
# Claude installed_path
# ---------------------------------------------------------------------------


def test_claude_prefix_missing_dir_is_not_installed(tmp_path: Path) -> None:
    assert PACK_LAYOUTS[CommandTarget.CLAUDE].installed_path(PREFIX_ENTRY, tmp_path) is None


def test_claude_prefix_empty_dir_is_not_installed(tmp_path: Path) -> None:
    (tmp_path / "demo").mkdir()
    assert PACK_LAYOUTS[CommandTarget.CLAUDE].installed_path(PREFIX_ENTRY, tmp_path) is None


def test_claude_prefix_non_empty_dir_is_installed(tmp_path: Path) -> None:
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "a.md").write_text("x")
    path = PACK_LAYOUTS[CommandTarget.CLAUDE].installed_path(PREFIX_ENTRY, tmp_path)
    assert path == tmp_path / "demo"


@pytest.mark.parametrize("present", [False, True])
def test_claude_dispatch_file(tmp_path: Path, present: bool) -> None:
    if present:
        (tmp_path / "sq").mkdir()
        (tmp_path / "sq" / "hello.md").write_text("x")
    path = PACK_LAYOUTS[CommandTarget.CLAUDE].installed_path(DISPATCH_ENTRY, tmp_path)
    assert path == (tmp_path / "sq" / "hello.md" if present else None)
