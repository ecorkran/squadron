"""Core Pydantic models for the squadron framework."""

from __future__ import annotations

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


class AgentConfig(BaseModel):
    """Configuration for creating an agent instance."""

    name: str
    agent_type: str  # "sdk" or "api"
    provider: str  # "sdk", "anthropic", "openai", etc.
    model: str | None = None  # None for SDK agents (uses Claude Code default)
    instructions: str | None = None  # system prompt, optional
    api_key: str | None = None
    auth_token: str | None = None
    base_url: str | None = None
    cwd: str | None = None  # SDK agents: working directory
    setting_sources: list[str] | None = None  # SDK agents: e.g. ["project"]
    allowed_tools: list[str] | None = None  # SDK agents: tool whitelist
    permission_mode: str | None = None  # SDK agents: permission handling
    credentials: dict[str, Any] = Field(default_factory=dict)


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


class TopologyConfig(BaseModel):
    """Configuration for the agent communication topology."""

    topology_type: TopologyType = TopologyType.broadcast
    config: dict[str, Any] = Field(default_factory=dict)
