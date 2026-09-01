"""Shared fixtures for tool tests."""

from __future__ import annotations

import sys
from pathlib import Path

from mcp import StdioServerParameters

FAKE_SERVER_PATH = Path(__file__).parent / "fake_mcp_server.py"


def fake_server_params(*, pid_file: Path | None = None) -> StdioServerParameters:
    """Build launch parameters for the fake stdio MCP server.

    ``sys.executable`` is used rather than ``"python"`` so the tests do not depend on any
    particular interpreter being on PATH.
    """
    args = [str(FAKE_SERVER_PATH)]
    if pid_file is not None:
        args += ["--pid-file", str(pid_file)]
    return StdioServerParameters(command=sys.executable, args=args)
