"""Tests for core Pydantic models and enums."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from squadron.core.models import (
    AgentConfig,
    AgentInfo,
    AgentState,
    Message,
    MessageType,
    ShutdownReport,
    TopologyConfig,
    TopologyType,
)

# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


def test_agent_state_values() -> None:
    assert AgentState.idle == "idle"
    assert AgentState.processing == "processing"
    assert AgentState.restarting == "restarting"
    assert AgentState.failed == "failed"
    assert AgentState.terminated == "terminated"
    assert len(AgentState) == 5


def test_message_type_values() -> None:
    assert MessageType.chat == "chat"
    assert MessageType.system == "system"
    assert MessageType.command == "command"
    assert len(MessageType) == 3


def test_topology_type_values() -> None:
    assert TopologyType.broadcast == "broadcast"
    assert TopologyType.filtered == "filtered"
    assert TopologyType.hierarchical == "hierarchical"
    assert TopologyType.custom == "custom"
    assert len(TopologyType) == 4


# ---------------------------------------------------------------------------
# AgentConfig model tests
# ---------------------------------------------------------------------------


def test_agent_config_minimal_required_fields() -> None:
    cfg = AgentConfig(name="test-bot", agent_type="sdk", provider="sdk")
    assert cfg.name == "test-bot"
    assert cfg.agent_type == "sdk"
    assert cfg.provider == "sdk"


def test_agent_config_optional_fields_default_none() -> None:
    cfg = AgentConfig(name="a", agent_type="sdk", provider="sdk")
    assert cfg.model is None
    assert cfg.instructions is None
    assert cfg.api_key is None
    assert cfg.auth_token is None
    assert cfg.base_url is None
    assert cfg.cwd is None
    assert cfg.setting_sources is None
    assert cfg.allowed_tools is None
    assert cfg.permission_mode is None


def test_agent_config_credentials_default_empty_dict() -> None:
    cfg = AgentConfig(name="a", agent_type="sdk", provider="sdk")
    assert cfg.credentials == {}


def test_agent_config_sdk_specific_fields() -> None:
    cfg = AgentConfig(
        name="reviewer",
        agent_type="sdk",
        provider="sdk",
        cwd="/project",
        setting_sources=["project"],
        allowed_tools=["Read", "Grep", "Glob"],
        permission_mode="bypassPermissions",
    )
    assert cfg.cwd == "/project"
    assert cfg.setting_sources == ["project"]
    assert cfg.allowed_tools == ["Read", "Grep", "Glob"]
    assert cfg.permission_mode == "bypassPermissions"


def test_agent_config_api_specific_fields() -> None:
    cfg = AgentConfig(
        name="chat-bot",
        agent_type="api",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        api_key="sk-test",
        auth_token="bearer-test",
        base_url="https://api.anthropic.com",
    )
    assert cfg.model == "claude-sonnet-4-20250514"
    assert cfg.api_key == "sk-test"
    assert cfg.auth_token == "bearer-test"
    assert cfg.base_url == "https://api.anthropic.com"


def test_agent_config_json_round_trip() -> None:
    cfg = AgentConfig(
        name="test",
        agent_type="sdk",
        provider="sdk",
        cwd="/project",
        credentials={"token": "abc"},
    )
    data = cfg.model_dump_json()
    restored = AgentConfig.model_validate_json(data)
    assert restored.name == cfg.name
    assert restored.agent_type == cfg.agent_type
    assert restored.cwd == cfg.cwd
    assert restored.credentials == cfg.credentials


def test_agent_config_rejects_missing_required() -> None:
    with pytest.raises(ValidationError):
        AgentConfig(name="a")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Message model tests
# ---------------------------------------------------------------------------


def test_message_creation_with_required_fields() -> None:
    msg = Message(sender="human", recipients=["all"], content="hello")
    assert msg.sender == "human"
    assert msg.recipients == ["all"]
    assert msg.content == "hello"


def test_message_id_auto_generated() -> None:
    m1 = Message(sender="s", recipients=["r"], content="c")
    m2 = Message(sender="s", recipients=["r"], content="c")
    assert len(m1.id) == 36
    assert m1.id != m2.id


def test_message_timestamp_auto_generated() -> None:
    before = datetime.now(UTC)
    msg = Message(sender="s", recipients=["r"], content="c")
    after = datetime.now(UTC)
    assert before <= msg.timestamp <= after


def test_message_default_message_type() -> None:
    msg = Message(sender="s", recipients=["r"], content="c")
    assert msg.message_type == MessageType.chat


def test_message_default_metadata() -> None:
    msg = Message(sender="s", recipients=["r"], content="c")
    assert msg.metadata == {}


def test_message_rejects_invalid_message_type() -> None:
    with pytest.raises(ValidationError):
        Message(
            sender="s",
            recipients=["r"],
            content="c",
            message_type="invalid",  # type: ignore[arg-type]
        )


def test_message_json_round_trip() -> None:
    msg = Message(sender="human", recipients=["agent1", "agent2"], content="hi")
    data = msg.model_dump_json()
    restored = Message.model_validate_json(data)
    assert restored.id == msg.id
    assert restored.recipients == msg.recipients
    assert restored.message_type == msg.message_type


# ---------------------------------------------------------------------------
# TopologyConfig model tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# AgentInfo model tests
# ---------------------------------------------------------------------------


def test_agent_info_construction() -> None:
    info = AgentInfo(name="bot1", agent_type="sdk", provider="sdk", state=AgentState.idle)
    assert info.name == "bot1"
    assert info.agent_type == "sdk"
    assert info.provider == "sdk"
    assert info.state == AgentState.idle


def test_agent_info_validates_state_as_enum() -> None:
    info = AgentInfo(name="bot2", agent_type="api", provider="anthropic", state=AgentState.processing)
    assert isinstance(info.state, AgentState)
    assert info.state == AgentState.processing


def test_agent_info_rejects_invalid_state() -> None:
    with pytest.raises(ValidationError):
        AgentInfo(
            name="bot3",
            agent_type="sdk",
            provider="sdk",
            state="not_a_state",  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# ShutdownReport model tests
# ---------------------------------------------------------------------------


def test_shutdown_report_empty_defaults() -> None:
    report = ShutdownReport()
    assert report.succeeded == []
    assert report.failed == {}


def test_shutdown_report_with_populated_fields() -> None:
    report = ShutdownReport(
        succeeded=["agent1", "agent2"],
        failed={"agent3": "timeout", "agent4": "connection refused"},
    )
    assert report.succeeded == ["agent1", "agent2"]
    assert report.failed == {"agent3": "timeout", "agent4": "connection refused"}


# ---------------------------------------------------------------------------
# TopologyConfig model tests
# ---------------------------------------------------------------------------


def test_topology_config_defaults() -> None:
    tc = TopologyConfig()
    assert tc.topology_type == TopologyType.broadcast
    assert tc.config == {}


def test_topology_config_with_values() -> None:
    tc = TopologyConfig(topology_type=TopologyType.hierarchical, config={"root": "agent1"})
    assert tc.topology_type == TopologyType.hierarchical
    assert tc.config == {"root": "agent1"}


def test_topology_config_json_round_trip() -> None:
    tc = TopologyConfig(topology_type=TopologyType.filtered, config={"filter": "tag"})
    data = tc.model_dump_json()
    restored = TopologyConfig.model_validate_json(data)
    assert restored.topology_type == tc.topology_type
    assert restored.config == tc.config
