"""Minimal stdio MCP server used as a real peer for bridge tests.

Run as ``python tests/tools/fake_mcp_server.py [--pid-file PATH]``. It exists only to give
:mod:`squadron.tools.mcp_bridge` a genuine subprocess to talk to, so the round-trip and
failure-mode tests exercise the transport rather than a mock. The low-level ``Server`` API is
used instead of ``FastMCP`` because these tools must return hand-built ``CallToolResult``
values (``isError``, zero content blocks, non-text blocks) that the high-level API hides.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Any

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

# A 1x1 transparent PNG, the smallest realistic non-text block payload.
_TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

_TOOLS = [
    types.Tool(
        name="echo",
        description="Return the supplied text.",
        inputSchema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    ),
    types.Tool(
        name="fail",
        description="Return a result flagged isError.",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="sleep",
        description="Sleep before responding.",
        inputSchema={
            "type": "object",
            "properties": {"seconds": {"type": "number"}},
            "required": ["seconds"],
        },
    ),
    types.Tool(
        name="empty",
        description="Return a result with zero content blocks.",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="nontext",
        description="Return a result containing a non-text block.",
        inputSchema={"type": "object", "properties": {}},
    ),
]

server: Server[Any, Any] = Server("fake-mcp-server")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return _TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
    if name == "echo":
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=str(arguments["text"]))]
        )
    if name == "fail":
        return types.CallToolResult(
            content=[types.TextContent(type="text", text="fake server refused the call")],
            isError=True,
        )
    if name == "sleep":
        await asyncio.sleep(float(arguments["seconds"]))
        return types.CallToolResult(content=[types.TextContent(type="text", text="awake")])
    if name == "empty":
        return types.CallToolResult(content=[])
    if name == "nontext":
        return types.CallToolResult(
            content=[
                types.TextContent(type="text", text="see attachment"),
                types.ImageContent(type="image", data=_TINY_PNG_B64, mimeType="image/png"),
            ]
        )
    raise ValueError(f"fake server has no tool '{name}'")


async def serve() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid-file")
    args = parser.parse_args()
    if args.pid_file:
        # Written before the event loop starts so the timeout test can read the PID and
        # assert this process is reaped when the client tears the session down.
        Path(args.pid_file).write_text(str(os.getpid()))
    asyncio.run(serve())


if __name__ == "__main__":
    main()
