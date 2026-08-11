"""Tests for plugin discovery (design D7)."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

import squadron.events as events_pkg
from squadron.events import get_event_action
from squadron.events.discovery import PluginLoadError, discover_plugins

_GOOD_PLUGIN = """\
from squadron.events import EventType, register_event_action
from squadron.events.contexts import EventContext
from squadron.pipeline.models import ActionResult


class _DiscoveredAction:
    name = "demo.discovered-check"
    events = frozenset({EventType.COMMIT})

    def validate(self, config):
        return []

    async def execute(self, context: EventContext) -> ActionResult:
        return ActionResult(success=True, action_type=self.name, outputs={})


register_event_action(_DiscoveredAction())
"""

_RAISING_PLUGIN = """\
raise RuntimeError("plugin is broken")
"""


@pytest.fixture(autouse=True)
def _clear_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(events_pkg, "_REGISTRY", {})


@pytest.fixture(autouse=True)
def _clear_sys_modules() -> Iterator[None]:
    """Discovered test plugin modules must not leak between tests."""
    yield
    for name in ("demo_good_plugin", "demo_raising_plugin"):
        sys.modules.pop(name, None)


def test_real_plugin_module_imports_and_registers(tmp_path: Path) -> None:
    (tmp_path / "demo_good_plugin.py").write_text(_GOOD_PLUGIN)

    discover_plugins(("demo_good_plugin",), manifest_source="events.yaml", cwd=str(tmp_path))

    assert get_event_action("demo.discovered-check").name == "demo.discovered-check"


def test_no_path_leak_on_success(tmp_path: Path) -> None:
    (tmp_path / "demo_good_plugin.py").write_text(_GOOD_PLUGIN)
    before = list(sys.path)

    discover_plugins(("demo_good_plugin",), manifest_source="events.yaml", cwd=str(tmp_path))

    assert sys.path == before


def test_raising_plugin_raises_plugin_load_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "demo_raising_plugin.py").write_text(_RAISING_PLUGIN)

    with caplog.at_level("ERROR"):
        with pytest.raises(PluginLoadError) as exc_info:
            discover_plugins(("demo_raising_plugin",), manifest_source="events.yaml", cwd=str(tmp_path))

    assert exc_info.value.module == "demo_raising_plugin"
    assert exc_info.value.manifest_source == "events.yaml"
    assert any("demo_raising_plugin" in rec.message for rec in caplog.records)


def test_sys_path_restored_after_raising_plugin(tmp_path: Path) -> None:
    (tmp_path / "demo_raising_plugin.py").write_text(_RAISING_PLUGIN)
    before = list(sys.path)

    with pytest.raises(PluginLoadError):
        discover_plugins(("demo_raising_plugin",), manifest_source="events.yaml", cwd=str(tmp_path))

    assert sys.path == before


def test_no_plugins_is_a_noop(tmp_path: Path) -> None:
    before = list(sys.path)
    discover_plugins((), manifest_source="events.yaml", cwd=str(tmp_path))
    assert sys.path == before
