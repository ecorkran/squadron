"""Live contract test against the real context-forge MCP server (schema-drift defense).

The mapping table in :mod:`squadron.tools.cf_tools` is hand-authored against a CF release and
can silently drift when CF changes an argument name — the unit tests would stay green while
every real call started failing. This module spawns the actual server and asserts the names
squadron sends still exist in its schemas.

Skipped as a module when the configured server cannot be launched, so CI without node stays
green while any environment with context-forge present verifies the contract.
"""

from __future__ import annotations

import asyncio
import shlex

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client
from mcp.types import Tool

from squadron import tools
from squadron.config.manager import get_config, get_typed_config
from squadron.tools import cf_tools

# Launching a cold `npx -y` may fetch the package, so the availability probe and the
# assertions get a far more generous budget than a warm in-process call needs.
LAUNCH_TIMEOUT_S = 180


def _server_params() -> StdioServerParameters:
    command_line = str(get_config(cf_tools.CF_MCP_COMMAND_KEY))
    command, *args = shlex.split(command_line)
    return StdioServerParameters(command=command, args=args, cwd=".", env=get_default_environment())


async def _fetch_tools() -> list[Tool]:
    """Spawn the configured server and return its advertised tools."""
    async with asyncio.timeout(LAUNCH_TIMEOUT_S):
        async with stdio_client(_server_params()) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                return (await session.list_tools()).tools


def _probe() -> list[Tool] | None:
    """Return the server's tools, or None if it could not be launched."""
    try:
        return asyncio.run(_fetch_tools())
    except Exception as exc:  # noqa: BLE001
        # Availability probe at collection time: any launch failure (no node, no network,
        # misconfigured command) means "skip", never "fail". The reason names the command so a
        # skip is never mistaken for a passing contract.
        pytest.skip(
            f"context-forge MCP server not launchable via "
            f"'{get_config(cf_tools.CF_MCP_COMMAND_KEY)}': {exc}",
            allow_module_level=True,
        )


LIVE_TOOLS: list[Tool] = _probe() or []
LIVE_BY_NAME: dict[str, Tool] = {tool.name: tool for tool in LIVE_TOOLS}

# Every CF MCP tool and argument name squadron sends, read from the mapping table itself so
# this test cannot drift away from the code it defends.
EXPECTED_CALLS: list[tuple[str, tuple[str, ...]]] = [
    (spec.mcp_tool, tuple(spec.arg_map.values())) for spec in cf_tools.CF_TOOL_SPECS
]


@pytest.mark.parametrize("mcp_tool", sorted({call[0] for call in EXPECTED_CALLS}))
def test_curated_mcp_tool_exists(mcp_tool: str) -> None:
    assert mcp_tool in LIVE_BY_NAME, f"context-forge no longer advertises '{mcp_tool}'"


@pytest.mark.parametrize(
    "mcp_tool,argument",
    sorted({(tool, arg) for tool, args in EXPECTED_CALLS for arg in args}),
)
def test_sent_argument_exists_in_schema(mcp_tool: str, argument: str) -> None:
    schema = LIVE_BY_NAME[mcp_tool].inputSchema
    properties = schema.get("properties") or {}
    assert argument in properties, f"context-forge '{mcp_tool}' no longer accepts '{argument}'"


@pytest.mark.asyncio
async def test_live_workflow_status_round_trip() -> None:
    """The full path — descriptor, config, transport, mapping — against the real server."""
    executor = tools.materialize([cf_tools.CF_WORKFLOW_STATUS_NAME], ".")[
        cf_tools.CF_WORKFLOW_STATUS_NAME
    ]

    result = await executor({})

    assert result.is_error is False, result.content
    assert "squadron" in result.content
    # Sanity that the configured per-call budget is what the executor would have used.
    assert get_typed_config(cf_tools.CF_MCP_TIMEOUT_KEY, int) > 0
