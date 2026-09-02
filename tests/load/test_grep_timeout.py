"""Load tests for the grep tool's whole-walk timeout budget.

Required by ``.claude/rules/python.md``'s load-test tier: ``grep``'s regex matching runs
CPU-bound inside ``asyncio.to_thread`` specifically to bound catastrophic backtracking
(design D9), which puts it on the concurrency-layer path. The unit test in
``tests/tools/test_grep.py`` asserts correctness with the budget monkeypatched down; these
tests assert the bound actually holds under a realistic configuration — the real
``limits.GREP_TIMEOUT_S``, a realistically-sized tree, and concurrent callers — which a
single-call unit test cannot check.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from squadron.tools import builtin, limits, registry  # noqa: F401  # builtin registers on import
from squadron.tools.models import ToolExecutor

# A long non-matching run of 'a's. ``(a|a)*$`` has exponentially many ways to split it and the
# trailing anchor forces the engine to exhaust them, so this is the shape the budget exists for.
PATHOLOGICAL_PATTERN = r"(a|a)*$"
PATHOLOGICAL_SUBJECT = "a" * 4000 + "b"

# How many multiples of the real budget a bounded call is allowed to take. Generous enough to
# absorb thread-pool scheduling and CI jitter, tight enough that an unbounded search (which
# measured 72.8s against a 1.0s budget during Phase 4) fails the assertion loudly.
BUDGET_TOLERANCE = 3.0

FILE_COUNT = 60


@pytest.fixture
def realistic_tree(tmp_path: Path) -> Path:
    """Dozens of ordinary source-sized files plus one pathological-match candidate."""
    for index in range(FILE_COUNT):
        body = "\n".join(f"def function_{index}_{line}(): return {line}" for line in range(40))
        (tmp_path / f"module_{index:03d}.py").write_text(body)
    (tmp_path / "pathological.txt").write_text(PATHOLOGICAL_SUBJECT)
    return tmp_path


@pytest.fixture
def grep(realistic_tree: Path) -> ToolExecutor:
    return registry.materialize(["grep"], realistic_tree)["grep"]


async def test_walk_budget_holds_at_real_timeout(grep: ToolExecutor) -> None:
    """The budget covers the whole walk, not each file, at the real GREP_TIMEOUT_S."""
    budget = limits.GREP_TIMEOUT_S

    started = time.monotonic()
    result = await grep({"pattern": PATHOLOGICAL_PATTERN})
    elapsed = time.monotonic() - started

    assert result.is_error is True
    assert "exceeded" in result.content
    # The quantitative bound this test exists for: a per-file budget across 61 files would
    # allow ~61x this, and no budget at all would run for minutes.
    assert elapsed < budget * BUDGET_TOLERANCE, (
        f"walk took {elapsed:.2f}s against a {budget}s whole-walk budget"
    )


async def test_healthy_search_over_realistic_tree_is_fast(grep: ToolExecutor) -> None:
    """A well-behaved pattern over the same tree stays far inside the budget.

    Guards against the timeout plumbing itself becoming the bottleneck — the per-line
    ``time.monotonic()`` deadline check runs on every line of every file.
    """
    started = time.monotonic()
    result = await grep({"pattern": r"def function_7_", "glob": "*.py"})
    elapsed = time.monotonic() - started

    assert result.is_error is False
    assert result.content
    assert elapsed < limits.GREP_TIMEOUT_S, f"healthy search took {elapsed:.2f}s"


async def test_concurrent_grep_calls_do_not_starve_the_event_loop(
    realistic_tree: Path, grep: ToolExecutor
) -> None:
    """Several concurrent greps stay bounded and leave the event loop responsive.

    Each call runs its CPU-bound match inside ``asyncio.to_thread``. If that discipline were
    ever dropped, the pathological calls would block the loop and the probe coroutine below
    would stop ticking — a failure mode no single-call unit test can observe.
    """
    budget = limits.GREP_TIMEOUT_S
    probe_ticks = 0
    probing = True

    async def probe() -> None:
        """Tick as fast as the loop allows; a starved loop cannot advance this."""
        nonlocal probe_ticks
        while probing:
            probe_ticks += 1
            await asyncio.sleep(0.01)

    probe_task = asyncio.create_task(probe())
    calls = [
        grep({"pattern": PATHOLOGICAL_PATTERN}),
        grep({"pattern": PATHOLOGICAL_PATTERN}),
        grep({"pattern": r"def function_3_", "glob": "*.py"}),
        grep({"pattern": r"def function_9_", "glob": "*.py"}),
    ]

    started = time.monotonic()
    results = await asyncio.gather(*calls)
    elapsed = time.monotonic() - started
    probing = False
    await probe_task

    assert [r.is_error for r in results] == [True, True, False, False]
    # No caller waits materially longer than the budget for a thread to free up.
    assert elapsed < budget * BUDGET_TOLERANCE, (
        f"{len(calls)} concurrent greps took {elapsed:.2f}s against a {budget}s budget"
    )
    # The loop kept running throughout: at 10ms per tick, a responsive loop ticks many times
    # over a multi-second window, while a starved one would tick a handful of times at most.
    minimum_ticks = int(elapsed / 0.05)
    assert probe_ticks >= minimum_ticks, (
        f"event loop ticked {probe_ticks} times over {elapsed:.2f}s (expected >= {minimum_ticks})"
    )


# ---------------------------------------------------------------------------
# The budget covers traversal and reads, not only line matching
# ---------------------------------------------------------------------------
#
# Added after the slice 265 code review observed that the deadline was consulted only inside
# the per-line matching loop, leaving two unbounded paths the original load test never
# exercised: the directory walk itself, and read_text() on a single enormous file.


async def test_budget_holds_against_a_very_large_single_file(tmp_path: Path) -> None:
    """One huge file must not consume the budget inside an unbounded read.

    The read is capped at MAX_READ_BYTES, so a file far larger than that still returns
    promptly instead of pulling gigabytes into memory first.
    """
    big = tmp_path / "huge.txt"
    line = "some ordinary source line that will not match the pattern\n"
    # Comfortably larger than MAX_READ_BYTES (256 KB) without making the test slow to write.
    big.write_text(line * 40_000)
    grep_tool = registry.materialize(["grep"], tmp_path)["grep"]

    started = time.monotonic()
    result = await grep_tool({"pattern": r"zzz-no-such-token"})
    elapsed = time.monotonic() - started

    assert result.is_error is False
    assert elapsed < limits.GREP_TIMEOUT_S, (
        f"single large file took {elapsed:.2f}s against a {limits.GREP_TIMEOUT_S}s budget"
    )


async def test_budget_holds_while_walking_a_wide_tree(tmp_path: Path) -> None:
    """Traversal is inside the budget, not before it.

    A materialized-and-sorted candidate list would walk the entire tree before the first
    deadline check; lazy iteration plus a per-candidate check keeps the walk itself bounded.
    """
    for bucket in range(40):
        directory = tmp_path / f"pkg_{bucket:03d}"
        directory.mkdir()
        for index in range(25):
            (directory / f"mod_{index:03d}.py").write_text("value = 1\n" * 20)
    grep_tool = registry.materialize(["grep"], tmp_path)["grep"]

    started = time.monotonic()
    result = await grep_tool({"pattern": r"value = 1", "max_results": 5})
    elapsed = time.monotonic() - started

    assert result.is_error is False
    assert len(result.content.splitlines()) == 5
    # max_results stops the walk early — it must not traverse all 1000 files first.
    assert elapsed < limits.GREP_TIMEOUT_S, (
        f"wide-tree walk took {elapsed:.2f}s against a {limits.GREP_TIMEOUT_S}s budget"
    )
