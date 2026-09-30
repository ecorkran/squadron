"""Load tests for batched ``read_file`` calls (slice 931 D5, D6).

Required by ``.claude/rules/python.md``'s load-test tier and the slice design's event-loop
NFR: a batch reads several real files near the byte budget in one call, so its blocking
work must stay inside the call's single ``asyncio.to_thread`` rather than on the loop. A
unit test cannot see starvation; these read a realistic batch beside a ticker task and
assert the loop keeps getting scheduled, and that a batch costs exactly one worker hop.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from squadron.tools import builtin, limits, registry  # noqa: F401  # builtin registers on import
from squadron.tools.models import ToolExecutor

FILE_COUNT = 5
MAX_LOOP_GAP_S = 0.050


@pytest.fixture
def batch_tree(tmp_path: Path) -> list[str]:
    """Five files that together fill the batch budget, as real reads from disk."""
    size = limits.MAX_READ_BATCH_BYTES // FILE_COUNT - 64
    names = [f"module_{index}.py" for index in range(FILE_COUNT)]
    for index, name in enumerate(names):
        line = f"def function_{index}(): return {index}\n"
        (tmp_path / name).write_text((line * (size // len(line) + 1))[:size])
    return names


@pytest.fixture
def read_file(tmp_path: Path) -> ToolExecutor:
    return registry.materialize(["read_file"], tmp_path)["read_file"]


async def test_budget_sized_batch_does_not_starve_the_loop(
    read_file: ToolExecutor, batch_tree: list[str]
) -> None:
    gaps: list[float] = []
    done = asyncio.Event()

    async def _ticker() -> None:
        last = time.monotonic()
        while not done.is_set():
            await asyncio.sleep(0.001)
            now = time.monotonic()
            gaps.append(now - last)
            last = now

    ticker = asyncio.create_task(_ticker())
    result = await read_file({"paths": batch_tree})
    done.set()
    await ticker

    assert result.is_error is False
    assert result.content.count("==> module_") == FILE_COUNT
    assert "[not read:" not in result.content
    assert gaps, "ticker never ran"
    assert max(gaps) < MAX_LOOP_GAP_S


async def test_a_five_path_batch_takes_one_worker_thread_hop(
    read_file: ToolExecutor, batch_tree: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    real_to_thread = asyncio.to_thread

    async def _counting(func: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
        calls.append(getattr(func, "__name__", repr(func)))
        return await real_to_thread(func, *args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", _counting)

    await read_file({"paths": batch_tree})

    assert len(calls) == 1
