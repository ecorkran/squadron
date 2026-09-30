"""Core Pydantic models for the squadron framework."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentState(StrEnum):
    """Lifecycle states for a managed agent."""

    idle = "idle"
    processing = "processing"
    restarting = "restarting"
    failed = "failed"
    terminated = "terminated"


class MessageType(StrEnum):
    """Classification of messages routed through the message bus."""

    chat = "chat"
    system = "system"
    command = "command"


class TopologyType(StrEnum):
    """Communication topology strategy for agent routing."""

    broadcast = "broadcast"
    filtered = "filtered"
    hierarchical = "hierarchical"
    custom = "custom"


class Effort(StrEnum):
    """How hard a model reasons before answering (slice 931 D1).

    The intersection of OpenAI-style ``reasoning_effort`` and the Claude SDK's ``effort``,
    plus ``none``, which disables reasoning — the most useful setting for a tool-heavy
    loop. Unset (``None`` on AgentConfig) sends nothing and the backend default applies.
    """

    none = "none"
    low = "low"
    medium = "medium"
    high = "high"
    xhigh = "xhigh"


class AgentConfig(BaseModel):
    """Configuration for creating an agent instance."""

    name: str
    agent_type: str  # "sdk" or "api"
    provider: str  # "sdk", "anthropic", "openai", etc.
    model: str | None = None  # None for SDK agents (uses Claude Code default)
    instructions: str | None = None  # system prompt, optional
    # SDK agents: use the CLI's own default system prompt. Distinct from
    # instructions=None/"" — both of those send an *empty* system prompt,
    # stripping the tool-use discipline the CLI normally supplies. The flag
    # composes with instructions rather than discarding them (#85):
    #
    #   use_default_system_prompt  instructions   system_prompt sent
    #   False                      None           (none)
    #   False                      str            str
    #   True                       None / ""      preset
    #   True                       str            preset + append=str
    #
    # Set this when a run should behave like an interactive session.
    use_default_system_prompt: bool = False
    api_key: str | None = None
    auth_token: str | None = None
    base_url: str | None = None
    cwd: str | None = None  # SDK and API agents: working directory
    # SDK agents only: source directory for conventions (CLAUDE.md) when it differs from
    # `cwd` (e.g. a scratch worktree holding reviewed code vs. the trusted checkout holding
    # project conventions). None means "same as cwd" — today's behavior for every existing
    # caller (slice 382, design D1).
    convention_root: str | None = None
    setting_sources: list[str] | None = None  # SDK agents: e.g. ["project"]
    # SDK agents: True only on pipeline paths (pipeline.auto_memory)
    auto_memory: bool = False
    # SDK and API agents: tool whitelist. Note the vocabularies differ — SDK names
    # (e.g. "Read") vs. squadron registry names — see slice-262 decision D1.
    allowed_tools: list[str] | None = None
    # Why allowed_tools was emptied by the slice 266 capability gate, or None if it was
    # not. Carried so the agent can stamp it into telemetry: an empty allowed_tools is
    # otherwise indistinguishable from a run that simply declared no tools.
    tools_suppressed_reason: str | None = None
    # Per-request output budget; None sends no budget (slice 924 D4).
    max_output_tokens: int | None = None
    # Reasoning effort from the alias; None sends none and the backend default applies
    # (slice 931 D1). Providers that cannot apply it say so (D4).
    effort: Effort | None = None
    # API agents: path patterns withheld from the tool jail, relative to cwd. Opaque to
    # every layer below the caller that sets it — the agent threads them to tool binding
    # without knowing why any pattern is present (slice 918, design D5). Empty means plain
    # jail behavior, which is what every caller that does not set it gets.
    tool_exclude_patterns: list[str] = Field(default_factory=list)
    permission_mode: str | None = None  # SDK agents: permission handling
    credentials: dict[str, Any] = Field(default_factory=dict)


class SystemPromptMode(StrEnum):
    """Which system prompt an agent ran with — the four rows of the table above."""

    PRESET = "preset"
    PRESET_APPEND = "preset+append"
    CUSTOM = "custom"
    EMPTY = "empty"


def describe_system_prompt(config: AgentConfig) -> SystemPromptMode:
    """Derive the recorded mode from the same two fields the provider sends from."""
    if config.use_default_system_prompt:
        return SystemPromptMode.PRESET_APPEND if config.instructions else SystemPromptMode.PRESET
    return SystemPromptMode.CUSTOM if config.instructions else SystemPromptMode.EMPTY


SETTING_SOURCES_NON_SDK = "n/a (non-SDK)"
SETTING_SOURCES_NONE = "none"
# Only `sq serve` agents can still reach the SDK with None (slice 932 D10).
SETTING_SOURCES_CLI_DEFAULT = "cli default"


def describe_setting_sources(setting_sources: Sequence[str] | None, *, is_sdk: bool) -> str:
    """Render the settings sources an agent ran with, for artifacts and metadata."""
    if not is_sdk:
        return SETTING_SOURCES_NON_SDK
    if setting_sources is None:
        return SETTING_SOURCES_CLI_DEFAULT
    if not setting_sources:
        return SETTING_SOURCES_NONE
    return ", ".join(setting_sources)


def describe_run_settings(config: AgentConfig, *, is_sdk: bool) -> dict[str, object]:
    """Step-metadata keys for the prompt and settings a one-shot agent ran with."""
    return {
        "system_prompt_mode": describe_system_prompt(config).value,
        "setting_sources": describe_setting_sources(config.setting_sources, is_sdk=is_sdk),
        "auto_memory": config.auto_memory,
    }


class Message(BaseModel):
    """A message routed between agents via the message bus."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    sender: str
    recipients: list[str]
    content: str
    message_type: MessageType = MessageType.chat
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentInfo(BaseModel):
    """Read model for agent enumeration — lightweight summary."""

    name: str
    agent_type: str
    provider: str
    state: AgentState


class ShutdownReport(BaseModel):
    """Result of a bulk shutdown operation."""

    succeeded: list[str] = Field(default_factory=list)
    failed: dict[str, str] = Field(default_factory=dict)  # name → error message


# SDK providers tag duplicate messages with this metadata value.
# Consumers should skip messages where metadata["sdk_type"] == SDK_RESULT_TYPE.
SDK_RESULT_TYPE = "result"

# The CLI message type behind most "rate limit" sightings. Its own schema
# description reads "Rate limit event emitted when rate limit info changes"
# — it is a *status* event feeding the usage indicator, fired on any change,
# and the CLI's own SDK adapter ignores it
# (``[sdkMessageAdapter] Ignoring rate_limit_event message``). Only a
# ``rejected`` status means requests are actually being blocked; an
# informational one is a usage-meter notice, not response prose — consumers
# should skip messages where metadata["sdk_type"] == RATE_LIMIT_EVENT_TYPE
# the same way they skip SDK_RESULT_TYPE.
RATE_LIMIT_EVENT_TYPE = "rate_limit_event"

# The two sdk_type values a tool-use turn produces: the model's tool call and
# the tool's own result, written by providers/sdk/translation.py and read by
# every downstream consumer that needs to tell them apart (#108 — these were
# previously scattered string literals).
TOOL_USE_TYPE = "tool_use"
TOOL_RESULT_TYPE = "tool_result"


class TopologyConfig(BaseModel):
    """Configuration for the agent communication topology."""

    topology_type: TopologyType = TopologyType.broadcast
    config: dict[str, Any] = Field(default_factory=dict)
