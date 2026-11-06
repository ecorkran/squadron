"""Benchmark config keys: registered default and override."""

from __future__ import annotations

from pathlib import Path

from squadron.config.keys import BENCHMARK_AUTH_PROBE_TIMEOUT_KEY, CONFIG_KEYS
from squadron.config.manager import get_positive_int_config, set_config


def test_auth_probe_timeout_default(patch_config_paths: dict[str, Path]) -> None:
    key = CONFIG_KEYS[BENCHMARK_AUTH_PROBE_TIMEOUT_KEY]
    assert key.type_ is int
    assert get_positive_int_config(BENCHMARK_AUTH_PROBE_TIMEOUT_KEY) == 120


def test_auth_probe_timeout_override(patch_config_paths: dict[str, Path]) -> None:
    set_config(BENCHMARK_AUTH_PROBE_TIMEOUT_KEY, "45")
    assert get_positive_int_config(BENCHMARK_AUTH_PROBE_TIMEOUT_KEY) == 45
