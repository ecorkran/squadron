"""Benchmark config keys: registered default and override."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.config.keys import (
    BENCHMARK_AUTH_PROBE_TIMEOUT_KEY,
    BENCHMARK_INSTALL_TIMEOUT_KEY,
    BENCHMARK_PLANNED_SAMPLES_KEY,
    BENCHMARK_QUALIFICATION_REPEATS_KEY,
    BENCHMARK_SUITE_TIMEOUT_KEY,
    BENCHMARK_TARGET_PASS_RATE_DIFFERENCE_KEY,
    CONFIG_KEYS,
)
from squadron.config.manager import (
    get_open_unit_interval_config,
    get_positive_int_config,
    set_config,
)


def test_auth_probe_timeout_default(patch_config_paths: dict[str, Path]) -> None:
    key = CONFIG_KEYS[BENCHMARK_AUTH_PROBE_TIMEOUT_KEY]
    assert key.type_ is int
    assert get_positive_int_config(BENCHMARK_AUTH_PROBE_TIMEOUT_KEY) == 120


def test_auth_probe_timeout_override(patch_config_paths: dict[str, Path]) -> None:
    set_config(BENCHMARK_AUTH_PROBE_TIMEOUT_KEY, "45")
    assert get_positive_int_config(BENCHMARK_AUTH_PROBE_TIMEOUT_KEY) == 45


def test_install_timeout_default_and_override(patch_config_paths: dict[str, Path]) -> None:
    assert CONFIG_KEYS[BENCHMARK_INSTALL_TIMEOUT_KEY].type_ is int
    assert get_positive_int_config(BENCHMARK_INSTALL_TIMEOUT_KEY) == 900
    set_config(BENCHMARK_INSTALL_TIMEOUT_KEY, "30")
    assert get_positive_int_config(BENCHMARK_INSTALL_TIMEOUT_KEY) == 30


def test_suite_timeout_default_and_override(patch_config_paths: dict[str, Path]) -> None:
    assert CONFIG_KEYS[BENCHMARK_SUITE_TIMEOUT_KEY].type_ is int
    assert get_positive_int_config(BENCHMARK_SUITE_TIMEOUT_KEY) == 1800
    set_config(BENCHMARK_SUITE_TIMEOUT_KEY, "30")
    assert get_positive_int_config(BENCHMARK_SUITE_TIMEOUT_KEY) == 30


@pytest.mark.parametrize(
    ("key", "default"),
    [
        (BENCHMARK_QUALIFICATION_REPEATS_KEY, 3),
        (BENCHMARK_PLANNED_SAMPLES_KEY, 3),
    ],
)
def test_positive_int_keys_default_and_override(
    patch_config_paths: dict[str, Path], key: str, default: int
) -> None:
    assert CONFIG_KEYS[key].type_ is int
    assert get_positive_int_config(key) == default
    set_config(key, "5")
    assert get_positive_int_config(key) == 5


@pytest.mark.parametrize("key", [BENCHMARK_QUALIFICATION_REPEATS_KEY, BENCHMARK_PLANNED_SAMPLES_KEY])
def test_zero_count_is_rejected(patch_config_paths: dict[str, Path], key: str) -> None:
    set_config(key, "0")
    with pytest.raises(ValueError, match=key):
        get_positive_int_config(key)


def test_target_difference_default_and_override(patch_config_paths: dict[str, Path]) -> None:
    key = BENCHMARK_TARGET_PASS_RATE_DIFFERENCE_KEY
    assert CONFIG_KEYS[key].type_ is float
    assert get_open_unit_interval_config(key) == pytest.approx(0.20)
    set_config(key, "0.35")
    assert get_open_unit_interval_config(key) == pytest.approx(0.35)


@pytest.mark.parametrize("value", ["0", "-0.1", "1", "1.5"])
def test_target_difference_out_of_range_is_rejected(
    patch_config_paths: dict[str, Path], value: str
) -> None:
    key = BENCHMARK_TARGET_PASS_RATE_DIFFERENCE_KEY
    set_config(key, value)
    with pytest.raises(ValueError, match=key):
        get_open_unit_interval_config(key)
