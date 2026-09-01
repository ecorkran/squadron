"""Tests for the curated context-forge MCP bridge tools.

Argument mapping and gating are tested with the transport patched out — these assert what
squadron *sends*, which is exactly the surface that CF schema drift breaks. The live contract
test (``test_cf_contract_live.py``) checks the other half: that what we send still matches
what CF accepts. No test here needs network or node.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from mcp import StdioServerParameters

from squadron import tools
from squadron.config.manager import set_config
from squadron.pipeline.models import StepConfig
from squadron.pipeline.steps.utils import validate_allowed_tools
from squadron.tools import cf_tools
from squadron.tools.models import ToolResult

CF_TOOL_NAMES = [
    cf_tools.CF_SET_PHASE_NAME,
    cf_tools.CF_SET_SLICE_NAME,
    cf_tools.CF_BUILD_CONTEXT_NAME,
    cf_tools.CF_PROMPT_GET_NAME,
    cf_tools.CF_WORKFLOW_STATUS_NAME,
]


@pytest.fixture
def patched_transport(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Replace ``call_mcp_tool`` where ``cf_tools`` looks it up."""
    mock = AsyncMock(return_value=ToolResult(content="ok"))
    monkeypatch.setattr(cf_tools, "call_mcp_tool", mock)
    return mock


def _sent(mock: AsyncMock) -> tuple[str, dict[str, object]]:
    """Return the (mcp tool name, arguments) of the single recorded transport call."""
    mock.assert_awaited_once()
    call = mock.await_args
    assert call is not None
    _server, tool, arguments, _timeout = call.args
    return tool, arguments


async def _invoke(name: str, args: dict[str, object], cwd: Path) -> ToolResult:
    executor = tools.materialize([name], cwd)[name]
    return await executor(args)


def test_all_five_registered() -> None:
    registered = set(tools.list_tools())
    assert set(CF_TOOL_NAMES) <= registered


def test_schemas_expose_no_project_identity() -> None:
    """The model must never be able to point these tools at another project."""
    for name in CF_TOOL_NAMES:
        descriptor = tools.lookup(name)
        assert descriptor is not None
        rendered = repr(descriptor.parameters)
        assert "projectId" not in rendered
        assert "projectPath" not in rendered


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,args,expected_tool,expected_arguments",
    [
        (
            cf_tools.CF_SET_PHASE_NAME,
            {"phase": "Phase 5: Task Breakdown"},
            cf_tools.CF_MCP_PROJECT_UPDATE,
            {cf_tools.CF_ARG_PHASE: "Phase 5: Task Breakdown"},
        ),
        (
            cf_tools.CF_SET_SLICE_NAME,
            {"slice": "264-slice.context-forge-mcp-tool-bridge"},
            cf_tools.CF_MCP_PROJECT_UPDATE,
            {cf_tools.CF_ARG_SLICE: "264-slice.context-forge-mcp-tool-bridge"},
        ),
        (
            cf_tools.CF_PROMPT_GET_NAME,
            {"template_name": "P5"},
            cf_tools.CF_MCP_PROMPT_GET,
            {cf_tools.CF_ARG_TEMPLATE_NAME: "P5"},
        ),
        (
            cf_tools.CF_WORKFLOW_STATUS_NAME,
            {},
            cf_tools.CF_MCP_WORKFLOW_STATUS,
            {},
        ),
        (
            cf_tools.CF_BUILD_CONTEXT_NAME,
            {},
            cf_tools.CF_MCP_CONTEXT_BUILD,
            {},
        ),
        (
            cf_tools.CF_BUILD_CONTEXT_NAME,
            {"phase": "Phase 6", "slice": "264-slice.x", "instruction": "focus on tests"},
            cf_tools.CF_MCP_CONTEXT_BUILD,
            {
                cf_tools.CF_ARG_PHASE: "Phase 6",
                cf_tools.CF_ARG_SLICE: "264-slice.x",
                cf_tools.CF_ARG_INSTRUCTION: "focus on tests",
            },
        ),
        (
            cf_tools.CF_BUILD_CONTEXT_NAME,
            {"slice": "264-slice.x"},
            cf_tools.CF_MCP_CONTEXT_BUILD,
            {cf_tools.CF_ARG_SLICE: "264-slice.x"},
        ),
    ],
)
async def test_argument_mapping(
    patched_transport: AsyncMock,
    tmp_path: Path,
    name: str,
    args: dict[str, object],
    expected_tool: str,
    expected_arguments: dict[str, object],
) -> None:
    await _invoke(name, args, tmp_path)

    assert _sent(patched_transport) == (expected_tool, expected_arguments)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,args,field",
    [
        (cf_tools.CF_SET_PHASE_NAME, {}, "phase"),
        (cf_tools.CF_SET_PHASE_NAME, {"phase": "   "}, "phase"),
        (cf_tools.CF_SET_SLICE_NAME, {}, "slice"),
        (cf_tools.CF_PROMPT_GET_NAME, {}, "template_name"),
    ],
)
async def test_missing_required_arg_fails_before_spawn(
    patched_transport: AsyncMock,
    tmp_path: Path,
    name: str,
    args: dict[str, object],
    field: str,
) -> None:
    result = await _invoke(name, args, tmp_path)

    assert result.is_error is True
    assert field in result.content
    patched_transport.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "transport_result",
    [
        ToolResult(content="status: Phase 6"),
        ToolResult(content="Error: CF said no", is_error=True),
    ],
)
async def test_transport_result_passes_through_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    transport_result: ToolResult,
) -> None:
    monkeypatch.setattr(cf_tools, "call_mcp_tool", AsyncMock(return_value=transport_result))

    result = await _invoke(cf_tools.CF_WORKFLOW_STATUS_NAME, {}, tmp_path)

    assert result == transport_result


@pytest.mark.asyncio
async def test_executor_reads_command_and_cwd_from_config(
    patched_transport: AsyncMock,
    patch_config_paths: dict[str, Path],
    tmp_path: Path,
) -> None:
    """The launch command is shlex-split and the server is bound to the factory's cwd."""
    set_config(cf_tools.CF_MCP_COMMAND_KEY, "node /opt/cf/index.js --stdio")
    set_config(cf_tools.CF_MCP_TIMEOUT_KEY, "17")

    await _invoke(cf_tools.CF_WORKFLOW_STATUS_NAME, {}, tmp_path)

    call = patched_transport.await_args
    assert call is not None
    server, _tool, _arguments, timeout = call.args
    assert isinstance(server, StdioServerParameters)
    assert server.command == "node"
    assert server.args == ["/opt/cf/index.js", "--stdio"]
    assert server.cwd == str(tmp_path.resolve())
    assert timeout == 17


@pytest.mark.asyncio
async def test_blank_command_is_an_error_result_not_a_raise(
    patched_transport: AsyncMock,
    patch_config_paths: dict[str, Path],
    tmp_path: Path,
) -> None:
    set_config(cf_tools.CF_MCP_COMMAND_KEY, "   ")

    result = await _invoke(cf_tools.CF_WORKFLOW_STATUS_NAME, {}, tmp_path)

    assert result.is_error is True
    assert "misconfigured" in result.content
    patched_transport.assert_not_awaited()


def _step(allowed: list[Any]) -> StepConfig:
    return StepConfig(step_type="dispatch", name="s", config={"allowed_tools": allowed})


def test_pipeline_validation_accepts_cf_tools_and_still_rejects_unknown() -> None:
    """263's validation is registry-driven, so cf_* names became valid YAML on registration."""
    assert validate_allowed_tools(_step([cf_tools.CF_WORKFLOW_STATUS_NAME]), "dispatch") == []

    errors = validate_allowed_tools(_step(["cf_bogus"]), "dispatch")
    assert len(errors) == 1
    assert "cf_bogus" in errors[0].message
