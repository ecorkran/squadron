"""ClaudeSDKProvider implementation. Creates and manages SDK-based agents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from claude_agent_sdk import ClaudeAgentOptions

from squadron.core.models import AgentConfig
from squadron.logging import get_logger
from squadron.providers.base import ProviderCapabilities, ProviderType
from squadron.providers.sdk.rate_limit import install_rate_limit_parser_shim
from squadron.providers.sdk.tool_names import translate_tool_names

if TYPE_CHECKING:
    from squadron.providers.sdk.agent import ClaudeSDKAgent

_log = get_logger("squadron.providers.sdk.provider")

# Default permission mode for programmatic agents — interactive mode hangs.
_DEFAULT_PERMISSION_MODE = "acceptEdits"


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
        )

    async def create_agent(self, config: AgentConfig) -> ClaudeSDKAgent:
        """Build ``ClaudeAgentOptions`` from *config* and return agent."""
        # Must precede any streaming: the pinned parser dies on the CLI's
        # rate-limit status event, and that kills the whole stream.
        install_rate_limit_parser_shim()

        kwargs: dict[str, object] = {}

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
        if config.setting_sources is not None:
            kwargs["setting_sources"] = config.setting_sources

        kwargs["permission_mode"] = (
            config.permission_mode if config.permission_mode is not None else _DEFAULT_PERMISSION_MODE
        )

        hooks = config.credentials.get("hooks")
        if hooks is not None:
            kwargs["hooks"] = hooks

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
        return ClaudeSDKAgent(name=config.name, options=options, mode=mode, **agent_kwargs)  # pyright: ignore[reportArgumentType]

    async def validate_credentials(self) -> bool:
        """Return ``True`` if ``claude_agent_sdk`` is importable."""
        try:
            __import__("claude_agent_sdk")
        except ImportError:
            return False
        return True
