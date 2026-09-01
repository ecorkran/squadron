"""Curated context-forge tools, bridged over MCP.

Five squadron-semantic tools let a tool-capable model drive the workflow itself: read state,
set the phase or slice, rebuild its own context, and fetch a prompt template. Each maps onto
one context-forge MCP call through the generic transport in
:mod:`squadron.tools.mcp_bridge`; the dependency runs one way only — this module imports the
bridge, never the reverse.

The mapping table below is the single place context-forge MCP vocabulary
(``developmentPhase``, ``fileSlice``, ``instruction``, ``templateName``) appears in squadron.
``tests/tools/test_cf_contract_live.py`` defends it against CF schema drift.

Registration is unconditional (design D4): whether the server is launchable on this machine
does not change which tool names a pipeline may declare. Unavailability surfaces at execution
as an explicit error result the model can react to.
"""

from __future__ import annotations

import logging
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from mcp import StdioServerParameters
from mcp.client.stdio import get_default_environment

from squadron.config.manager import get_config, get_typed_config
from squadron.tools.mcp_bridge import call_mcp_tool
from squadron.tools.models import ToolDescriptor, ToolExecutor, ToolFactory, ToolResult
from squadron.tools.registry import register

# Canonical squadron tool names.
CF_SET_PHASE_NAME = "cf_set_phase"
CF_SET_SLICE_NAME = "cf_set_slice"
CF_BUILD_CONTEXT_NAME = "cf_build_context"
CF_PROMPT_GET_NAME = "cf_prompt_get"
CF_WORKFLOW_STATUS_NAME = "cf_workflow_status"

# Context-forge MCP tool names.
CF_MCP_PROJECT_UPDATE = "project_update"
CF_MCP_CONTEXT_BUILD = "context_build"
CF_MCP_PROMPT_GET = "prompt_get"
CF_MCP_WORKFLOW_STATUS = "workflow_status"

# Context-forge MCP argument names. These four strings appear nowhere else in squadron.
CF_ARG_PHASE = "developmentPhase"
CF_ARG_SLICE = "fileSlice"
CF_ARG_INSTRUCTION = "instruction"
CF_ARG_TEMPLATE_NAME = "templateName"

# Config keys read at execute time (never captured at import, so a changed setting takes
# effect on the very next call).
CF_MCP_COMMAND_KEY = "cf.mcp_command"
CF_MCP_TIMEOUT_KEY = "cf.mcp_timeout_s"

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CfToolSpec:
    """One squadron tool's mapping onto a context-forge MCP call.

    Attributes:
        name: Squadron tool name, as the model calls it.
        description: What the tool does, in workflow terms — the model's only documentation.
        mcp_tool: Context-forge MCP tool this call maps to.
        arg_map: Squadron parameter name -> context-forge argument name.
        required: Squadron parameter names that must be present and non-blank. Parameters
            outside this set are optional and are forwarded only when supplied.
        param_descriptions: Squadron parameter name -> JSON Schema description.
    """

    name: str
    description: str
    mcp_tool: str
    arg_map: dict[str, str] = field(default_factory=lambda: {})
    required: tuple[str, ...] = ()
    param_descriptions: dict[str, str] = field(default_factory=lambda: {})


CF_TOOL_SPECS: tuple[CfToolSpec, ...] = (
    CfToolSpec(
        name=CF_SET_PHASE_NAME,
        description=(
            "Set the project's current development phase in context-forge. Use this to "
            "advance the workflow after finishing a phase's work."
        ),
        mcp_tool=CF_MCP_PROJECT_UPDATE,
        arg_map={"phase": CF_ARG_PHASE},
        required=("phase",),
        param_descriptions={"phase": "The development phase to set, e.g. 'Phase 5: Task Breakdown'."},
    ),
    CfToolSpec(
        name=CF_SET_SLICE_NAME,
        description=(
            "Set the project's active slice in context-forge. Use this to move work onto a "
            "different slice."
        ),
        mcp_tool=CF_MCP_PROJECT_UPDATE,
        arg_map={"slice": CF_ARG_SLICE},
        required=("slice",),
        param_descriptions={
            "slice": "The slice document name to make active, without the .md extension."
        },
    ),
    CfToolSpec(
        name=CF_BUILD_CONTEXT_NAME,
        description=(
            "Build the context-forge context prompt for the project. Any argument supplied "
            "is an ephemeral override applied to this build only — it does not change stored "
            "project state. Omit all arguments to build context for the current state."
        ),
        mcp_tool=CF_MCP_CONTEXT_BUILD,
        arg_map={
            "phase": CF_ARG_PHASE,
            "slice": CF_ARG_SLICE,
            "instruction": CF_ARG_INSTRUCTION,
        },
        param_descriptions={
            "phase": "Optional ephemeral phase override for this build only.",
            "slice": "Optional ephemeral slice override for this build only.",
            "instruction": "Optional extra instruction text to include in the built context.",
        },
    ),
    CfToolSpec(
        name=CF_PROMPT_GET_NAME,
        description=(
            "Fetch a context-forge prompt template by name, for example a phase prompt template."
        ),
        mcp_tool=CF_MCP_PROMPT_GET,
        arg_map={"template_name": CF_ARG_TEMPLATE_NAME},
        required=("template_name",),
        param_descriptions={"template_name": "Name of the prompt template to fetch."},
    ),
    CfToolSpec(
        name=CF_WORKFLOW_STATUS_NAME,
        description=(
            "Report the project's current workflow state from context-forge — phase, active "
            "slice, and task progress. Read this before changing phase or slice."
        ),
        mcp_tool=CF_MCP_WORKFLOW_STATUS,
    ),
)


def _build_parameters(spec: CfToolSpec) -> dict[str, object]:
    """Render *spec* as a JSON Schema object for the model.

    Only squadron parameter names appear; ``projectId``/``projectPath`` are deliberately
    absent, so a model cannot target a project other than the bound working directory.
    """
    properties: dict[str, object] = {
        param: {"type": "string", "description": spec.param_descriptions[param]}
        for param in spec.arg_map
    }
    parameters: dict[str, object] = {"type": "object", "properties": properties}
    if spec.required:
        parameters["required"] = list(spec.required)
    return parameters


def _missing_required(spec: CfToolSpec, args: dict[str, object]) -> str | None:
    """Return the name of the first missing or blank required argument, or None."""
    for param in spec.required:
        value = args.get(param)
        if not isinstance(value, str) or not value.strip():
            return param
    return None


def _map_arguments(spec: CfToolSpec, args: dict[str, object]) -> dict[str, object]:
    """Translate supplied squadron arguments into context-forge argument names.

    Absent optional parameters are omitted entirely rather than sent as ``None``, so an
    unspecified override never reads as an explicit blank to context-forge.
    """
    return {cf_name: args[param] for param, cf_name in spec.arg_map.items() if param in args}


def _server_params(cwd: Path) -> StdioServerParameters:
    """Build launch parameters for the context-forge MCP server bound to *cwd*.

    Context-forge resolves the active project from its working directory, which is why no
    project identity is ever sent as an argument.
    """
    command_line = get_config(CF_MCP_COMMAND_KEY, cwd=str(cwd))
    if not isinstance(command_line, str) or not command_line.strip():
        raise ValueError(f"{CF_MCP_COMMAND_KEY} must be a non-empty string, got {command_line!r}")
    command, *args = shlex.split(command_line)
    return StdioServerParameters(
        command=command,
        args=args,
        cwd=str(cwd),
        env=get_default_environment(),
    )


def _make_factory(spec: CfToolSpec) -> ToolFactory:
    """Return the ToolFactory for *spec*.

    One shared builder rather than five near-identical closures: the only thing that differs
    between these tools is their mapping-table entry.
    """

    def factory(cwd: Path) -> ToolExecutor:
        async def execute(args: dict[str, object]) -> ToolResult:
            missing = _missing_required(spec, args)
            if missing is not None:
                # Fails before any spawn: nothing has been launched, so no log is warranted —
                # the result text names the field for the model to correct.
                return ToolResult(
                    content=f"Error: missing required argument '{missing}' for {spec.name}.",
                    is_error=True,
                )

            try:
                timeout_s = int(get_typed_config(CF_MCP_TIMEOUT_KEY, int, cwd=str(cwd)))
                server = _server_params(cwd)
            except ValueError as exc:
                # Misconfiguration, not a model error: the bridge cannot be launched at all.
                # Surfaced as a value per the 261 contract, and logged because an operator has
                # to fix it.
                _logger.warning("%s: misconfigured MCP bridge: %s", spec.name, exc)
                return ToolResult(
                    content=f"Error: the context-forge bridge is misconfigured: {exc}",
                    is_error=True,
                )

            return await call_mcp_tool(server, spec.mcp_tool, _map_arguments(spec, args), timeout_s)

        return execute

    return factory


CF_DESCRIPTORS: tuple[ToolDescriptor, ...] = tuple(
    ToolDescriptor(
        name=spec.name,
        description=spec.description,
        parameters=_build_parameters(spec),
        factory=_make_factory(spec),
    )
    for spec in CF_TOOL_SPECS
)

for _descriptor in CF_DESCRIPTORS:
    register(_descriptor)
