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
from typing import cast

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


def _leaves(exc: BaseException) -> list[BaseException]:
    """Flatten *exc* into its leaf exceptions, unwrapping nested exception groups.

    The mcp SDK runs its transport inside anyio task groups, so a failure raised in-band
    (a protocol error, a broken pipe) reaches the caller wrapped in a ``BaseExceptionGroup``
    rather than as itself. Classification has to see through that wrapper.
    """
    if isinstance(exc, BaseExceptionGroup):
        # BaseExceptionGroup is generic and the SDK gives it no parameter, so the member
        # access is Unknown to strict pyright; the runtime contract is exact.
        inners = cast(
            "tuple[BaseException, ...]",
            exc.exceptions,  # pyright: ignore[reportUnknownMemberType]
        )
        return [leaf for inner in inners for leaf in _leaves(inner)]
    return [exc]


def _classify_failure(server: StdioServerParameters, tool: str, exc: BaseException) -> ToolResult:
    """Map a raised failure onto the error result and WARNING its failure-mode row requires.

    Errors are values (261 contract), so every branch returns rather than re-raises. The
    order matters: spawn failure is checked before protocol error because a server that never
    started also produces a closed-stream protocol error downstream, and the launch problem is
    the one an operator has to fix.
    """
    leaves = _leaves(exc)

    # TimeoutError is an OSError subclass, so it must be split off before the spawn check or a
    # grouped timeout would be reported as an unlaunchable server — wrong cause, wrong fix.
    # The ungrouped case is handled by the caller's own `except TimeoutError`.
    timeouts = [leaf for leaf in leaves if isinstance(leaf, TimeoutError)]
    if timeouts:
        _logger.warning("mcp_bridge: tool '%s' timed out", tool)
        return ToolResult(
            content=f"Error: MCP tool '{tool}' timed out and was cancelled.", is_error=True
        )

    spawn_errors = [leaf for leaf in leaves if isinstance(leaf, OSError)]
    if spawn_errors:
        # Spawn failure: the launch command is missing, not executable, or its cwd is bad.
        command = _describe(server)
        cause = spawn_errors[0]
        _logger.warning("mcp_bridge: could not launch MCP server '%s': %s", command, cause)
        return ToolResult(
            content=(
                f"Error: could not launch the MCP server '{command}': {cause}. "
                f"The bridge is unavailable."
            ),
            is_error=True,
        )

    protocol_errors = [leaf for leaf in leaves if isinstance(leaf, McpError)]
    if protocol_errors:
        cause = protocol_errors[0]
        _logger.warning("mcp_bridge: protocol error calling tool '%s': %s", tool, cause)
        return ToolResult(content=f"Error: MCP protocol error calling '{tool}': {cause}", is_error=True)

    # Anything else is unclassified: a transport teardown race or an SDK failure we have no
    # specific handling for. It must still reach the model as a value rather than end the run,
    # and it is logged with a traceback so the cause is never lost. The leaf is reported rather
    # than the group, whose own message names nothing actionable.
    cause = leaves[0] if leaves else exc
    _logger.exception("mcp_bridge: unexpected failure calling tool '%s'", tool, exc_info=exc)
    return ToolResult(
        content=f"Error: unexpected failure calling MCP tool '{tool}': {cause}", is_error=True
    )


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
    except Exception as exc:  # noqa: BLE001
        # Single classifying handler at the process boundary for the model loop. It is one
        # `except` rather than a chain because the SDK's internal anyio task groups re-raise
        # in-band failures wrapped in a BaseExceptionGroup: a bare `except McpError` never
        # matches a real protocol error, and the group's own message ("unhandled errors in a
        # TaskGroup") names nothing the model or an operator could act on. Classification
        # therefore runs over the flattened leaves.
        return _classify_failure(server, tool, exc)
