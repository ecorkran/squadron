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
        assert key.default == 400_000

    def test_get_default_max_tool_iterations(self) -> None:
        assert get_default("agent.max_tool_iterations") == 20

    def test_get_default_max_history_chars(self) -> None:
        assert get_default("agent.max_history_chars") == 400_000

    @pytest.mark.parametrize(
        "key,default",
        [
            ("agent.max_tool_iterations", 20),
            ("agent.max_history_chars", 400_000),
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
