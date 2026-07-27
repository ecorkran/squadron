"""ClaudeSDKProvider implementation. Creates and manages SDK-based agents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from claude_agent_sdk import ClaudeAgentOptions

from squadron.core.models import AgentConfig
from squadron.logging import get_logger
from squadron.providers.base import ProviderCapabilities, ProviderType

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
        kwargs: dict[str, object] = {}

        # The preset form is the only way to get the CLI's default system
        # prompt: the SDK emits no --system-prompt flag for it, so the CLI
        # falls back to its own. A str (including "") or None both send
        # --system-prompt "", which is an *empty* prompt, not the default.
        if config.use_default_system_prompt:
            kwargs["system_prompt"] = {"type": "preset", "preset": "claude_code"}
        elif config.instructions is not None:
            kwargs["system_prompt"] = config.instructions
        if config.model is not None:
            kwargs["model"] = config.model
        if config.allowed_tools is not None:
            kwargs["allowed_tools"] = config.allowed_tools
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
