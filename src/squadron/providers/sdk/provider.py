"""ClaudeSDKProvider implementation. Creates and manages SDK-based agents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from claude_agent_sdk import ClaudeAgentOptions, PermissionResultDeny, ToolPermissionContext

from squadron.core.models import AgentConfig, Effort
from squadron.logging import get_logger
from squadron.providers.base import ProviderCapabilities, ProviderType
from squadron.providers.sdk.settings import SDK_MAX_BUFFER_BYTES, sdk_settings_options
from squadron.providers.sdk.tool_names import translate_tool_names

if TYPE_CHECKING:
    from squadron.providers.sdk.agent import ClaudeSDKAgent

_log = get_logger("squadron.providers.sdk.provider")

# Default permission mode for programmatic agents — interactive mode hangs.
_DEFAULT_PERMISSION_MODE = "acceptEdits"
# Asks `can_use_tool` about every tool call; used for a step that declared no tools (#299).
_TOOL_LESS_PERMISSION_MODE = "default"


async def deny_every_tool(
    tool_name: str, tool_input: dict[str, object], context: ToolPermissionContext
) -> PermissionResultDeny:
    """``can_use_tool`` callback for a step that declared ``allowed_tools: []`` (#299).

    With an empty tool list the model has nothing to call, so reaching here means the
    isolation leaked. Deny the call so nothing runs unchecked, and say so at ERROR.
    """
    _log.error("tool-less SDK step was offered tool %r; denied (isolation leak)", tool_name)
    return PermissionResultDeny(message="This step runs without tools.")


def sdk_effort_options(effort: Effort | None) -> dict[str, object]:
    """``ClaudeAgentOptions`` entries for ``effort`` (slice 931 D1).

    ``none`` has no SDK effort level; it disables thinking instead. Every other level is
    one the SDK accepts as-is. Unset sends neither, so the backend default applies.
    """
    if effort is None:
        return {}
    if effort is Effort.none:
        return {"thinking": {"type": "disabled"}}
    return {"effort": effort.value}


class ClaudeSDKProvider:
    """Creates SDK-based agents backed by claude-agent-sdk."""

    @property
    def provider_type(self) -> str:
        return ProviderType.SDK

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            can_read_files=True,
            supports_system_prompt=True,
            supports_streaming=True,
            applies_effort=True,
            honors_empty_tools=True,
        )

    async def create_agent(self, config: AgentConfig) -> ClaudeSDKAgent:
        """Build ``ClaudeAgentOptions`` from *config* and return agent."""
        kwargs: dict[str, object] = {}
        # Slice 924 B2: the SDK agent sends no per-request budget, so say so rather
        # than drop it silently. Warned here because the agent never sees the config.
        if config.max_output_tokens is not None:
            _log.warning(
                "SDK agent cannot apply max_output_tokens=%d; the backend default applies",
                config.max_output_tokens,
            )

        # The preset form is the only way to get the CLI's default system
        # prompt: the SDK emits no --system-prompt flag for it, so the CLI
        # falls back to its own. A str (including "") or None both send
        # --system-prompt "", which is an *empty* prompt, not the default.
        # ``append`` carries the caller's instructions *alongside* the preset
        # rather than replacing it (#85): a review template sent as the entire
        # system prompt discards the CLI's tool-use discipline, which is the
        # whole reason the preset is used here.
        if config.use_default_system_prompt:
            preset: dict[str, str] = {"type": "preset", "preset": "claude_code"}
            if config.instructions:
                preset["append"] = config.instructions
            kwargs["system_prompt"] = preset
        elif config.instructions is not None:
            kwargs["system_prompt"] = config.instructions
        if config.model is not None:
            kwargs["model"] = config.model
        if config.allowed_tools is not None:
            # Canonical -> Claude vocabulary happens here and only here; see tool_names.
            translated = translate_tool_names(config.allowed_tools)
            # Both are set deliberately: they answer different questions. `tools`
            # is what exists at all, `allowed_tools` what is pre-approved. Setting
            # only the latter left the CLI's full default set reachable, so a
            # review declaring three read-only tools could still run Bash
            # (issue #69). An allowlist is used rather than `disallowed_tools`
            # because a denylist must be re-audited every time the CLI's defaults
            # grow, and drifts silently when nobody does.
            kwargs["tools"] = translated
            kwargs["allowed_tools"] = translated
        if config.cwd is not None:
            kwargs["cwd"] = config.cwd
        # Auto-memory is an explicit per-path choice (slice 932 D11), always
        # applied; setting_sources only when given (sq serve callers may pass None).
        settings = sdk_settings_options(
            config.setting_sources or [],
            auto_memory=config.auto_memory,
            base_env=kwargs.get("env"),  # type: ignore[arg-type]
        )
        kwargs["env"] = settings["env"]
        if config.setting_sources is not None:
            kwargs["setting_sources"] = settings["setting_sources"]

        # A tool-less step is not auto-approved (#299): the default mode asks
        # `can_use_tool` about every call, and that callback denies them all.
        tool_less = config.allowed_tools == []
        if tool_less:
            kwargs["can_use_tool"] = deny_every_tool
        default_mode = _TOOL_LESS_PERMISSION_MODE if tool_less else _DEFAULT_PERMISSION_MODE
        kwargs["permission_mode"] = (
            config.permission_mode if config.permission_mode is not None else default_mode
        )

        hooks = config.credentials.get("hooks")
        if hooks is not None:
            kwargs["hooks"] = hooks

        kwargs.update(sdk_effort_options(config.effort))
        kwargs["max_buffer_size"] = SDK_MAX_BUFFER_BYTES

        options = ClaudeAgentOptions(**kwargs)  # type: ignore[arg-type]
        mode = config.credentials.get("mode", "query")

        # Deferred import to avoid circular / stub-state issues at module load.
        from squadron.providers.sdk.agent import ClaudeSDKAgent

        _log.debug("Creating SDK agent %r (mode=%s)", config.name, mode)
        agent_kwargs: dict[str, object] = {}
        retries = config.credentials.get("max_rate_limit_retries")
        if retries is not None:
            agent_kwargs["max_rate_limit_retries"] = int(retries)  # pyright: ignore[reportArgumentType]
        cap_s = config.credentials.get("rate_limit_cap_s")
        if cap_s is not None:
            agent_kwargs["rate_limit_cap_s"] = float(cap_s)  # pyright: ignore[reportArgumentType]
        # Canonical names (pre-translation), so tool telemetry (issue #110) is stamped in
        # the same vocabulary the OpenAI agent uses — callers never see Claude's names.
        if config.allowed_tools is not None:
            agent_kwargs["tools_given"] = list(config.allowed_tools)
        return ClaudeSDKAgent(name=config.name, options=options, mode=mode, **agent_kwargs)  # pyright: ignore[reportArgumentType]

    async def validate_credentials(self) -> bool:
        """Return ``True`` if ``claude_agent_sdk`` is importable."""
        try:
            __import__("claude_agent_sdk")
        except ImportError:
            return False
        return True
