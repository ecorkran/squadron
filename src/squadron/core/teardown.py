"""Best-effort teardown of SDK clients."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable


async def close_best_effort(
    close: Callable[[], Awaitable[object]], logger: logging.Logger, owner: str
) -> None:
    """Await ``close()``; log any failure at ERROR and never re-raise.

    Teardown boundary: callers close an SDK's subprocess/transport, whose
    failure modes are internal to the SDK and not enumerable. A cleanup
    failure must not mask the caller's result or block finishing teardown.
    """
    try:
        await close()
    except Exception:  # noqa: BLE001
        logger.exception("%s: ignoring error during cleanup", owner)
