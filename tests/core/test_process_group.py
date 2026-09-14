"""Tests for ``kill_process_group`` against a real spawned process.

Shared by ``bash_tool.py`` and ``frontmatter_gate.py`` (slice 919 Part 3, #98
code review F002/F003) — a dedicated test here, independent of either
caller, exercises the real kill/reap logic rather than a mock, so a
regression (wrong signal, wrong pgid, an un-awaited wait) cannot pass green
just because both callers patch it out in their own tests.
"""

from __future__ import annotations

import asyncio
import sys

from squadron.core.process_group import kill_process_group


async def test_kills_and_reaps_a_real_hung_process() -> None:
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "import time; time.sleep(30)",
        start_new_session=True,
    )

    await kill_process_group(proc)

    # returncode is set once the process has been reaped; None would mean the
    # wait never completed and a zombie was left behind.
    assert proc.returncode is not None


async def test_process_that_already_exited_is_still_reaped_without_error() -> None:
    """The ProcessLookupError swallow path: the process exits on its own
    between the timeout firing and the kill signal being sent."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "pass",
        start_new_session=True,
    )
    await proc.wait()  # let it exit naturally first

    await kill_process_group(proc)  # must not raise

    assert proc.returncode == 0
