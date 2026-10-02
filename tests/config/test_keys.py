"""Tests for config key registry (CONFIG_KEYS)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.config.keys import CONFIG_KEYS, get_default
from squadron.config.manager import get_config, get_typed_config, set_config


class TestCompactConfigKeys:
    """Tests for the compact.* config keys used by the PreCompact hook."""

    def test_compact_template_registered(self) -> None:
        key = CONFIG_KEYS["compact.template"]
        assert key.name == "compact.template"
        assert key.type_ is str
        assert key.default == "minimal"

    def test_compact_instructions_registered(self) -> None:
        key = CONFIG_KEYS["compact.instructions"]
        assert key.name == "compact.instructions"
        assert key.type_ is str
        assert key.default is None

    def test_get_default_compact_template(self) -> None:
        assert get_default("compact.template") == "minimal"

    def test_get_default_compact_instructions(self) -> None:
        assert get_default("compact.instructions") is None

    @pytest.mark.parametrize(
        "key,value",
        [
            ("compact.template", "lean"),
            ("compact.instructions", "Keep slice {slice} only."),
        ],
    )
    def test_set_and_get_roundtrip(
        self,
        patch_config_paths: dict[str, Path],
        key: str,
        value: str,
    ) -> None:
        set_config(key, value)
        assert get_config(key) == value


class TestAgentLoopLimitConfigKeys:
    """Tests for the agent.* config keys used by the agentic loop guards."""

    def test_max_tool_iterations_registered(self) -> None:
        key = CONFIG_KEYS["agent.max_tool_iterations"]
        assert key.name == "agent.max_tool_iterations"
        assert key.type_ is int
        assert key.default == 20

    def test_max_history_chars_registered(self) -> None:
        key = CONFIG_KEYS["agent.max_history_chars"]
        assert key.name == "agent.max_history_chars"
        assert key.type_ is int
        assert key.default == 1_000_000

    def test_get_default_max_tool_iterations(self) -> None:
        assert get_default("agent.max_tool_iterations") == 20

    def test_get_default_max_history_chars(self) -> None:
        assert get_default("agent.max_history_chars") == 1_000_000

    @pytest.mark.parametrize(
        "key,default",
        [
            ("agent.max_tool_iterations", 20),
            ("agent.max_history_chars", 1_000_000),
        ],
    )
    def test_get_typed_config_returns_default_with_no_override(
        self,
        patch_config_paths: dict[str, Path],
        key: str,
        default: int,
    ) -> None:
        assert get_typed_config(key, int) == default

    @pytest.mark.parametrize(
        "key",
        ["agent.max_tool_iterations", "agent.max_history_chars"],
    )
    def test_set_and_get_typed_roundtrip(
        self,
        patch_config_paths: dict[str, Path],
        key: str,
    ) -> None:
        set_config(key, "5")
        assert get_typed_config(key, int) == 5


class TestCfMcpBridgeConfigKeys:
    """Tests for the cf.* config keys used by the context-forge MCP bridge."""

    def test_cf_mcp_command_registered(self) -> None:
        key = CONFIG_KEYS["cf.mcp_command"]
        assert key.name == "cf.mcp_command"
        assert key.type_ is str
        assert key.default == "npx -y @context-forge/mcp"

    def test_cf_mcp_timeout_registered(self) -> None:
        key = CONFIG_KEYS["cf.mcp_timeout_s"]
        assert key.name == "cf.mcp_timeout_s"
        assert key.type_ is int
        assert key.default == 60

    def test_cf_mcp_command_default(self, patch_config_paths: dict[str, Path]) -> None:
        assert get_default("cf.mcp_command") == "npx -y @context-forge/mcp"
        assert get_config("cf.mcp_command") == "npx -y @context-forge/mcp"

    def test_cf_mcp_timeout_default(self, patch_config_paths: dict[str, Path]) -> None:
        assert get_default("cf.mcp_timeout_s") == 60
        value = get_typed_config("cf.mcp_timeout_s", int)
        assert value == 60
        assert isinstance(value, int)

    def test_cf_mcp_command_override_roundtrip(self, patch_config_paths: dict[str, Path]) -> None:
        set_config("cf.mcp_command", "node /path/to/index.js")
        assert get_config("cf.mcp_command") == "node /path/to/index.js"


class TestCodexTimeoutConfigKeys:
    """Tests for the codex.* timeout keys (slice 129, D7)."""

    @pytest.mark.parametrize(
        ("key_name", "default"),
        [
            ("codex.turn_timeout_s", 1800),
            ("codex.login_timeout_s", 300),
            ("codex.account_timeout_s", 30),
        ],
    )
    def test_registered_typed_and_readable(
        self,
        key_name: str,
        default: int,
        patch_config_paths: dict[str, Path],
    ) -> None:
        key = CONFIG_KEYS[key_name]
        assert key.name == key_name
        assert key.type_ is int
        assert key.default == default
        assert key.description
        value = get_typed_config(key_name, int)
        assert value == default
        assert isinstance(value, int)


class TestPipelineConfigKeys:
    """Keys added by slice 932 for pipeline SDK sessions."""

    def test_background_idle_timeout_registered(self) -> None:
        key = CONFIG_KEYS["pipeline.background_idle_timeout_s"]
        assert key.type_ is int
        assert key.default == 1800

    def test_background_idle_timeout_coerces_on_set(self, patch_config_paths: dict[str, Path]) -> None:
        set_config("pipeline.background_idle_timeout_s", "60")
        assert get_typed_config("pipeline.background_idle_timeout_s", int) == 60

    def test_auto_memory_registered_as_bool_defaulting_on(self) -> None:
        key = CONFIG_KEYS["pipeline.auto_memory"]
        assert key.type_ is bool
        assert key.default is True

    def test_user_settings_registered_as_bool_defaulting_off(self) -> None:
        key = CONFIG_KEYS["pipeline.user_settings"]
        assert key.type_ is bool
        assert key.default is False
