"""Generic single-call MCP stdio transport.

One public coroutine spawns a stdio MCP server, initializes a session, calls one tool, maps
the result onto :class:`~squadron.tools.models.ToolResult`, and tears the session down. It
knows nothing about any particular server — callers build the
:class:`~mcp.StdioServerParameters` and choose the timeout — so bridging a second MCP server
later reuses this module unchanged.

Errors are values (slice-261 contract): every failure path returns a ``ToolResult`` with
``is_error=True`` and logs at WARNING. Nothing raises to the caller.
"""

from __future__ import annotations

import asyncio
import logging

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError
from mcp.types import CallToolResult, TextContent

from squadron.tools.models import ToolResult

_logger = logging.getLogger(__name__)


def _describe(server: StdioServerParameters) -> str:
    """Render the launch command for log and error messages."""
    return " ".join([server.command, *server.args])


def _map_result(tool: str, result: CallToolResult) -> ToolResult:
    """Map a ``CallToolResult`` onto a ``ToolResult`` per the slice-264 mapping rules.

    Text blocks are joined with newlines. Non-text blocks are noted by type rather than
    dropped, so the model is never told less than the server said. A result carrying no text
    at all becomes an explicit error: an empty success would be a silent no-op.
    """
    texts = [block.text for block in result.content if isinstance(block, TextContent)]
    other_types = sorted({block.type for block in result.content if not isinstance(block, TextContent)})

    if other_types:
        noted = ", ".join(other_types)
        texts.append(f"[non-text content omitted: {noted}]")

    if not texts:
        _logger.warning("mcp_bridge: tool '%s' returned no content blocks", tool)
        return ToolResult(
            content=(f"Error: MCP tool '{tool}' returned a result with no content blocks."),
            is_error=True,
        )

    content = "\n".join(texts)
    if result.isError:
        _logger.warning("mcp_bridge: tool '%s' reported an error: %s", tool, content)
        return ToolResult(content=content, is_error=True)
    return ToolResult(content=content)


async def call_mcp_tool(
    server: StdioServerParameters,
    tool: str,
    arguments: dict[str, object],
    timeout_s: int,
) -> ToolResult:
    """Spawn *server*, call *tool* once with *arguments*, and return the mapped result.

    The whole span — spawn, initialize, and call — is bounded by *timeout_s*. On timeout the
    async-context exit kills the server's process group, so grandchildren (e.g. the node
    process ``npx`` forks) are reaped rather than orphaned.

    Never raises: transport, protocol, and timeout failures all come back as
    ``ToolResult(is_error=True)``.
    """
    try:
        async with asyncio.timeout(timeout_s):
            async with stdio_client(server) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(tool, arguments)
        return _map_result(tool, result)
    except TimeoutError:
        _logger.warning("mcp_bridge: tool '%s' timed out after %ss", tool, timeout_s)
        return ToolResult(
            content=f"Error: MCP tool '{tool}' timed out after {timeout_s}s and was cancelled.",
            is_error=True,
        )
    except (FileNotFoundError, PermissionError, NotADirectoryError, OSError) as exc:
        # Spawn failure: the launch command is missing, not executable, or its cwd is bad.
        command = _describe(server)
        _logger.warning("mcp_bridge: could not launch MCP server '%s': %s", command, exc)
        return ToolResult(
            content=(
                f"Error: could not launch the MCP server '{command}': {exc}. The bridge is unavailable."
            ),
            is_error=True,
        )
    except McpError as exc:
        _logger.warning("mcp_bridge: protocol error calling tool '%s': %s", tool, exc)
        return ToolResult(content=f"Error: MCP protocol error calling '{tool}': {exc}", is_error=True)
    except Exception as exc:  # noqa: BLE001
        # Process boundary for the model loop: a transport teardown race or an unexpected SDK
        # failure must reach the model as an error result, never as an exception that ends the
        # run. Logged with a traceback so the cause is never lost.
        _logger.exception("mcp_bridge: unexpected failure calling tool '%s'", tool)
        return ToolResult(
            content=f"Error: unexpected failure calling MCP tool '{tool}': {exc}", is_error=True
        )
