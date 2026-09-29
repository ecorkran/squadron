"""Tests for the SDK settings policy helper (slice 932 D10/D11)."""

from __future__ import annotations

from squadron.providers.sdk.settings import AUTO_MEMORY_DISABLE_ENV, sdk_settings_options


def test_auto_memory_off_sets_disable_var() -> None:
    opts = sdk_settings_options(["project"], auto_memory=False)
    assert opts["env"] == {AUTO_MEMORY_DISABLE_ENV: "1"}


def test_auto_memory_on_leaves_env_without_disable_var() -> None:
    opts = sdk_settings_options(["project"], auto_memory=True)
    assert opts["env"] == {}


def test_base_env_keys_survive_and_input_is_not_mutated() -> None:
    base = {"FOO": "bar"}
    opts = sdk_settings_options([], auto_memory=False, base_env=base)
    assert opts["env"] == {"FOO": "bar", AUTO_MEMORY_DISABLE_ENV: "1"}
    assert base == {"FOO": "bar"}


def test_setting_sources_returned_as_a_new_list() -> None:
    sources = ("project",)
    opts = sdk_settings_options(sources, auto_memory=True)
    assert opts["setting_sources"] == ["project"]
    assert isinstance(opts["setting_sources"], list)
