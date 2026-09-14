"""Killing an ``asyncio`` subprocess's whole process group.

Shared by every caller that spawns a subprocess with ``start_new_session=True``
and needs to reap it on a timeout — ``bash_tool.py`` (the ``bash`` tool) and
``frontmatter_gate.py`` (the ``cf validate frontmatter`` gate, slice 919 Part 3,
#98). Split out rather than duplicated so a fix to the kill/reap logic cannot
drift between the two copies (CLAUDE.md's DRY rule). Deliberately dependency-free
— it must be importable by both ``events`` and ``tools`` without pulling in
either package's own registration side effects.
"""

from __future__ import annotations

import asyncio
import os
import signal


async def kill_process_group(proc: asyncio.subprocess.Process) -> None:
    """Kill *proc*'s whole process group and reap it, so no zombie or orphan is left."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except ProcessLookupError:
        # The process exited on its own between the timeout firing and this kill. Nothing to
        # signal; the wait below still reaps it.
        pass
    await proc.wait()
