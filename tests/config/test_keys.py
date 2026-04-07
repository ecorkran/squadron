"""Tests for config key registry (CONFIG_KEYS)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.config.keys import CONFIG_KEYS, get_default
from squadron.config.manager import get_config, set_config


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
