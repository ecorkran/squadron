"""Load tests: fix-context's blocking work must not starve the event loop (slice 423).

Required by ``.claude/rules/python.md``'s load-test tier: ``FixContextAction`` reads files,
runs git and (in fetch mode) calls the code host, all synchronous. It runs them in
``asyncio.to_thread``. A single-call unit test cannot tell that apart from running them on
the loop, so these tests block the issue loader for a fixed time and assert that a
concurrent ticker keeps ticking, and that concurrent runs overlap instead of queueing.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

from squadron.codehost.models import IssueSnapshot, RepositoryLocator
from squadron.codehost.protocol import CodeHost
from squadron.core.process_runner import SubprocessRunner
from squadron.pipeline.actions.fix_context import FixContextAction
from squadron.pipeline.fix_issue import IssueText, IssueTextLoader
from squadron.pipeline.fix_keys import CommitTo, IssueSource
from squadron.pipeline.models import ActionContext
from tests.pipeline.fix_fetch_helpers import add_github_remote, snapshot

# How long the fake loader blocks its thread, and the share of it the loop may be late by.
BLOCK_SECONDS = 0.6
TICK_SECONDS = 0.01
MAX_GAP_SECONDS = BLOCK_SECONDS / 3
# Concurrent runs must finish in about one block time; a serial queue would take the sum.
CONCURRENT_RUNS = 4
MAX_CONCURRENT_SECONDS = BLOCK_SECONDS * 2


class _BlockingLoader:
    """An issue loader that blocks its calling thread, as a slow disk or host would."""

    def load(self, issue_number: int, issue_file: str, io_dir: Path | None, cwd: str) -> IssueText:
        time.sleep(BLOCK_SECONDS)
        return IssueText("issue text", IssueSource.FILE, "0" * 64)


def _context(repo: Path) -> ActionContext:
    return ActionContext(
        pipeline_name="fix",
        run_id="run-001",
        params={"issue": "1", "issue-file": "issue.md", "commit-to": CommitTo.CURRENT.value},
        step_name="fix",
        step_index=0,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        cwd=str(repo),
    )


async def _ticker(stop: asyncio.Event) -> float:
    """The longest gap between ticks while ``stop`` is unset."""
    longest = 0.0
    last = time.perf_counter()
    while not stop.is_set():
        await asyncio.sleep(TICK_SECONDS)
        now = time.perf_counter()
        longest = max(longest, now - last)
        last = now
    return longest


async def test_blocking_load_does_not_starve_the_event_loop(temp_git_repo: Path) -> None:
    action = FixContextAction(_BlockingLoader())
    stop = asyncio.Event()
    ticker = asyncio.create_task(_ticker(stop))
    await asyncio.sleep(TICK_SECONDS * 3)  # let the ticker establish its rhythm

    result = await action.execute(_context(temp_git_repo))
    stop.set()
    longest_gap = await ticker

    assert result.success, result.error
    assert longest_gap < MAX_GAP_SECONDS, f"event loop stalled for {longest_gap:.3f}s"


async def test_concurrent_runs_overlap(temp_git_repo: Path) -> None:
    action = FixContextAction(_BlockingLoader())
    started = time.perf_counter()

    results = await asyncio.gather(
        *(action.execute(_context(temp_git_repo)) for _ in range(CONCURRENT_RUNS))
    )
    elapsed = time.perf_counter() - started

    assert all(result.success for result in results)
    assert elapsed < MAX_CONCURRENT_SECONDS, f"{CONCURRENT_RUNS} runs took {elapsed:.2f}s"


class _BlockingHost:
    """A code host whose ``get_issue`` blocks its thread, as a slow ``gh`` call would."""

    runner = SubprocessRunner()

    def serves_host(self, hostname: str) -> bool:
        return hostname == "github.com"

    def get_issue(self, locator: RepositoryLocator, number: int) -> IssueSnapshot:
        time.sleep(BLOCK_SECONDS)
        return snapshot()


async def test_a_blocking_host_fetch_does_not_starve_the_event_loop(temp_git_repo: Path) -> None:
    add_github_remote(temp_git_repo)
    host = cast(CodeHost, _BlockingHost())
    action = FixContextAction(IssueTextLoader(lambda: host))  # the real loader, a slow host
    context = _context(temp_git_repo)
    context.params["issue-file"] = ""
    stop = asyncio.Event()
    ticker = asyncio.create_task(_ticker(stop))
    await asyncio.sleep(TICK_SECONDS * 3)

    result = await action.execute(context)
    stop.set()
    longest_gap = await ticker

    assert result.success, result.error
    assert longest_gap < MAX_GAP_SECONDS, f"event loop stalled for {longest_gap:.3f}s"
