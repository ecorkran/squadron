"""The bounded ``list_files`` walk (slice 266, T22).

SC10 asks for bounded **work**, not a bounded byte count. The pre-existing
``MAX_OUTPUT_BYTES`` cap already bounded the returned listing while ``sorted()``
materialized the entire tree first, so a test asserting only on output size passes against
the unbounded implementation and proves nothing.

Every test here instruments ``walk_tree`` as ``list_files`` sees it and asserts on
**entries actually pulled** from the walk. Patching ``Path.glob``/``rglob`` would count
nothing: the walk uses ``iterdir`` (issue #79), so those wrappers never run.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from squadron.tools import limits, materialize
from squadron.tools.builtin import LIST_FILES_NAME, file_tools


def _make_wide_tree(root: Path, count: int) -> None:
    for index in range(count):
        (root / f"file_{index:05d}.txt").write_text("x")


class _CountingWalk:
    """Wraps ``walk_tree``, counting how many entries ``list_files`` actually pulls."""

    def __init__(self) -> None:
        self.consumed = 0

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        real = file_tools.walk_tree

        def _wrapper(
            root: Path, *, recursive: bool = True, excluded: tuple[Path, ...] = ()
        ) -> Iterator[Path]:
            for entry in real(root, recursive=recursive, excluded=excluded):
                self.consumed += 1
                yield entry

        monkeypatch.setattr(file_tools, "walk_tree", _wrapper)


async def _list(jail: Path, args: dict[str, object]) -> str:
    executor = materialize([LIST_FILES_NAME], str(jail))[LIST_FILES_NAME]
    result = await executor(args)
    return result.content


@pytest.mark.asyncio
async def test_walk_stops_early_over_a_wide_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SC10: the walk stops consuming at the cap.

    This is the assertion that fails against the pre-T21 implementation, where ``sorted()``
    drained all 500 entries regardless of what was returned.
    """
    _make_wide_tree(tmp_path, 500)
    monkeypatch.setattr(limits, "MAX_LIST_ENTRIES", 50)

    counter = _CountingWalk()
    counter.install(monkeypatch)

    content = await _list(tmp_path, {"path": ".", "pattern": "*"})

    # The counter must have seen the walk at all, or the bound below is vacuous.
    assert counter.consumed >= 50
    # One past the cap: the loop pulls the entry that trips the break.
    assert counter.consumed <= 51, (
        f"walked {counter.consumed} entries with a cap of 50 — the walk is not bounded"
    )
    assert "the listing is partial" in content


@pytest.mark.asyncio
async def test_cap_marker_names_the_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A short listing must stay distinguishable from a truncated one."""
    _make_wide_tree(tmp_path, 100)
    monkeypatch.setattr(limits, "MAX_LIST_ENTRIES", 10)

    content = await _list(tmp_path, {"path": ".", "pattern": "*"})

    assert "stopped after 10 entries" in content
    assert len([line for line in content.splitlines() if line.endswith(".txt")]) == 10


@pytest.mark.asyncio
async def test_tree_under_the_cap_is_listed_whole_without_a_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bound must not label a complete listing as partial."""
    _make_wide_tree(tmp_path, 5)
    monkeypatch.setattr(limits, "MAX_LIST_ENTRIES", 100)

    content = await _list(tmp_path, {"path": ".", "pattern": "*"})

    assert "partial" not in content
    assert len(content.splitlines()) == 5


@pytest.mark.asyncio
async def test_recursive_walk_is_bounded_too(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The recursive walk descends only as far as the cap makes it pull."""
    for index in range(20):
        sub = tmp_path / f"dir_{index:03d}"
        sub.mkdir()
        _make_wide_tree(sub, 20)
    monkeypatch.setattr(limits, "MAX_LIST_ENTRIES", 30)

    counter = _CountingWalk()
    counter.install(monkeypatch)

    content = await _list(tmp_path, {"path": ".", "pattern": "*", "recursive": True})

    assert 30 <= counter.consumed <= 31, f"walked {counter.consumed} entries with a cap of 30"
    assert "the listing is partial" in content


@pytest.mark.asyncio
async def test_hitting_the_cap_is_observable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """An operator must be able to see that a listing was cut short."""
    _make_wide_tree(tmp_path, 50)
    monkeypatch.setattr(limits, "MAX_LIST_ENTRIES", 5)

    with caplog.at_level(logging.WARNING, logger="squadron.tools.builtin"):
        await _list(tmp_path, {"path": ".", "pattern": "*"})

    assert any("cap" in r.getMessage() for r in caplog.records)
