"""Tests for the generic MCP stdio transport helper.

These are real subprocess round-trips against ``fake_mcp_server.py`` — no mocks — so the
transport, the timeout guard, and the SDK's process-group teardown are all exercised for
real. Every failure-mode row from the slice design asserts its observable WARNING.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import pytest
from mcp import StdioServerParameters

from squadron.tools.mcp_bridge import call_mcp_tool
from tests.tools.conftest import fake_server_params

# Generous enough that a cold interpreter start never trips it, short enough to keep the
# suite quick.
ROUND_TRIP_TIMEOUT_S = 30


@pytest.mark.asyncio
async def test_echo_round_trip() -> None:
    result = await call_mcp_tool(
        fake_server_params(), "echo", {"text": "round trip"}, ROUND_TRIP_TIMEOUT_S
    )

    assert result.is_error is False
    assert result.content == "round trip"


@pytest.mark.asyncio
async def test_server_is_error_maps_to_error_result(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="squadron.tools.mcp_bridge"):
        result = await call_mcp_tool(fake_server_params(), "fail", {}, ROUND_TRIP_TIMEOUT_S)

    assert result.is_error is True
    assert "refused" in result.content
    assert any("reported an error" in record.getMessage() for record in caplog.records)


@pytest.mark.asyncio
async def test_empty_result_is_explicit_error(caplog: pytest.LogCaptureFixture) -> None:
    """Zero content blocks must never look like an empty success (slice-909 lesson)."""
    with caplog.at_level(logging.WARNING, logger="squadron.tools.mcp_bridge"):
        result = await call_mcp_tool(fake_server_params(), "empty", {}, ROUND_TRIP_TIMEOUT_S)

    assert result.is_error is True
    assert "no content blocks" in result.content
    assert any("no content blocks" in record.getMessage() for record in caplog.records)


@pytest.mark.asyncio
async def test_nontext_block_noted_by_type() -> None:
    """Non-text blocks are named, not dropped, so the model is told the whole truth."""
    result = await call_mcp_tool(fake_server_params(), "nontext", {}, ROUND_TRIP_TIMEOUT_S)

    assert result.is_error is False
    assert "see attachment" in result.content
    assert "image" in result.content


@pytest.mark.asyncio
async def test_unknown_tool_name(caplog: pytest.LogCaptureFixture) -> None:
    """The protocol-error row: a bad tool name returns an error result, never an exception.

    The mcp SDK converts the server-side handler exception into a ``CallToolResult`` with
    ``isError`` set, so this arrives through the isError mapping path rather than as an
    ``McpError``. Either way the observable signal required by the failure-mode table — a
    WARNING naming the tool — must be present.
    """
    with caplog.at_level(logging.WARNING, logger="squadron.tools.mcp_bridge"):
        result = await call_mcp_tool(fake_server_params(), "no_such_tool", {}, ROUND_TRIP_TIMEOUT_S)

    assert result.is_error is True
    assert any("no_such_tool" in record.getMessage() for record in caplog.records)


def _process_alive(pid: int) -> bool:
    """Return True if *pid* still names a live process."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # The process exists but belongs to another user — impossible for a child we spawned,
        # so treat it as alive rather than hiding a real leak.
        return True
    return True


@pytest.mark.asyncio
async def test_timeout_cancels_and_reaps_server(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A hung call times out, and the SDK's process-group teardown reaps the server."""
    pid_file = tmp_path / "server.pid"
    timeout_s = 2

    started = time.monotonic()
    with caplog.at_level(logging.WARNING, logger="squadron.tools.mcp_bridge"):
        result = await call_mcp_tool(
            fake_server_params(pid_file=pid_file),
            "sleep",
            {"seconds": 30},
            timeout_s,
        )
    elapsed = time.monotonic() - started

    assert result.is_error is True
    assert "timed out" in result.content
    assert any("timed out" in record.getMessage() for record in caplog.records)

    # The call returns near the deadline; teardown adds the SDK's SIGTERM-then-SIGKILL
    # escalation window, so the bound is the timeout plus that margin, not the 30s sleep.
    assert elapsed < timeout_s + 10

    pid = int(pid_file.read_text())
    assert not _process_alive(pid), f"fake MCP server pid {pid} survived timeout teardown"


@pytest.mark.asyncio
async def test_spawn_failure_is_error_result(caplog: pytest.LogCaptureFixture) -> None:
    bad = StdioServerParameters(command="definitely-not-a-command")

    with caplog.at_level(logging.WARNING, logger="squadron.tools.mcp_bridge"):
        result = await call_mcp_tool(bad, "echo", {"text": "x"}, ROUND_TRIP_TIMEOUT_S)

    assert result.is_error is True
    assert "definitely-not-a-command" in result.content
    assert "unavailable" in result.content
    assert any("could not launch" in record.getMessage() for record in caplog.records)
