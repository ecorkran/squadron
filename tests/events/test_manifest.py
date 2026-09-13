"""Tests for the event binding manifest loader (design D6)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from squadron.events import EventType, bootstrap_event_actions, get_event_action
from squadron.events.contexts import EventContext
from squadron.events.manifest import (
    DEFAULT_BINDINGS,
    ManifestError,
    load_manifest,
    resolve_bindings,
)
from squadron.events.protocol import EventAction
from squadron.pipeline.models import ActionResult, ValidationError

_PROJECT_MANIFEST_YAML = """\
plugins:
  - tools.squadron_rules
bindings:
  commit:
    - action: demo.rule-check
      params:
        ruleset: strict
"""

_USER_MANIFEST_YAML = """\
plugins:
  - user_tools.checks
bindings:
  post-action:
    - action: demo.post-check
"""


def test_no_manifest_returns_defaults_only(tmp_path: Path) -> None:
    manifest = load_manifest(
        project_path=tmp_path / "missing-project.yaml",
        user_path=tmp_path / "missing-user.yaml",
    )
    assert manifest.plugins == ()
    assert manifest.bindings == DEFAULT_BINDINGS
    assert manifest.manifest_path is None


def test_project_file_wins_over_user_file(tmp_path: Path) -> None:
    project_path = tmp_path / "project-events.yaml"
    user_path = tmp_path / "user-events.yaml"
    project_path.write_text(_PROJECT_MANIFEST_YAML)
    user_path.write_text(_USER_MANIFEST_YAML)

    manifest = load_manifest(project_path=project_path, user_path=user_path)

    assert manifest.manifest_path == project_path
    assert manifest.plugins == ("tools.squadron_rules",)
    action_names = [b.action for b in manifest.bindings]
    assert "demo.rule-check" in action_names
    assert "demo.post-check" not in action_names


def test_user_file_used_when_project_absent(tmp_path: Path) -> None:
    project_path = tmp_path / "missing-project.yaml"
    user_path = tmp_path / "user-events.yaml"
    user_path.write_text(_USER_MANIFEST_YAML)

    manifest = load_manifest(project_path=project_path, user_path=user_path)

    assert manifest.manifest_path == user_path
    assert manifest.plugins == ("user_tools.checks",)
    action_names = [b.action for b in manifest.bindings]
    assert "demo.post-check" in action_names


def test_disable_removes_a_default_binding(tmp_path: Path) -> None:
    project_path = tmp_path / "project-events.yaml"
    project_path.write_text("disable:\n  - squadron.frontmatter-gate\n")

    manifest = load_manifest(project_path=project_path, user_path=tmp_path / "missing-user.yaml")

    action_names = [b.action for b in manifest.bindings]
    assert "squadron.frontmatter-gate" not in action_names
    assert "squadron.dispatch-artifact" in action_names
    assert "squadron.revision-stamp" in action_names


def test_unknown_event_key_errors_naming_file(tmp_path: Path) -> None:
    project_path = tmp_path / "project-events.yaml"
    project_path.write_text("bindings:\n  bogus-event:\n    - action: demo.rule-check\n")

    with pytest.raises(ManifestError, match=str(project_path)):
        load_manifest(project_path=project_path, user_path=tmp_path / "missing-user.yaml")


class _StubAction:
    """Minimal EventAction satisfying the protocol resolve_bindings checks.

    resolve_bindings reads only ``events``, but it is typed against the
    EventAction protocol, so a SimpleNamespace does not type-check as one.
    """

    def __init__(self, name: str, events: frozenset[EventType]) -> None:
        self.name = name
        self.events = events

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        return []

    async def execute(self, context: EventContext) -> ActionResult:
        raise NotImplementedError("stub: resolve_bindings never executes an action")


def _fake_get_action(
    events_by_name: dict[str, frozenset[EventType]],
) -> Callable[[str], EventAction]:
    def get_action(name: str) -> EventAction:
        return _StubAction(name, events_by_name[name])

    return get_action


def _builtin_events() -> dict[str, frozenset[EventType]]:
    """Every built-in binding's action, mapped to the events it supports.

    Derived from DEFAULT_BINDINGS and the live registry rather than spelled
    out, so adding a built-in does not silently strand these fixtures with a
    KeyError that has nothing to do with what they test.
    """
    bootstrap_event_actions()
    return {binding.action: get_event_action(binding.action).events for binding in DEFAULT_BINDINGS}


def test_unknown_action_name_errors_naming_both(tmp_path: Path) -> None:
    project_path = tmp_path / "project-events.yaml"
    project_path.write_text(_PROJECT_MANIFEST_YAML)

    manifest = load_manifest(project_path=project_path, user_path=tmp_path / "missing-user.yaml")
    registered = [b.action for b in DEFAULT_BINDINGS]
    get_action = _fake_get_action(_builtin_events())

    with pytest.raises(ManifestError) as exc_info:
        resolve_bindings(manifest, registered, get_action)

    message = str(exc_info.value)
    assert "demo.rule-check" in message
    assert all(name in message for name in registered)


def test_incompatible_event_binding_errors(tmp_path: Path) -> None:
    project_path = tmp_path / "project-events.yaml"
    project_path.write_text("bindings:\n  post-action:\n    - action: squadron.frontmatter-gate\n")

    manifest = load_manifest(project_path=project_path, user_path=tmp_path / "missing-user.yaml")
    registered = [b.action for b in DEFAULT_BINDINGS]
    get_action = _fake_get_action(_builtin_events())

    with pytest.raises(ManifestError, match="does not support event 'post-action'"):
        resolve_bindings(manifest, registered, get_action)


def test_compatible_event_binding_passes(tmp_path: Path) -> None:
    project_path = tmp_path / "project-events.yaml"
    project_path.write_text("bindings:\n  commit:\n    - action: demo.rule-check\n")
    manifest = load_manifest(project_path=project_path, user_path=tmp_path / "missing-user.yaml")
    registered = [*[b.action for b in DEFAULT_BINDINGS], "demo.rule-check"]
    get_action = _fake_get_action(
        {**_builtin_events(), "demo.rule-check": frozenset({EventType.COMMIT})}
    )

    resolve_bindings(manifest, registered, get_action)  # must not raise


def test_bindings_preserve_file_order_after_defaults(tmp_path: Path) -> None:
    project_path = tmp_path / "project-events.yaml"
    project_path.write_text(
        "bindings:\n  commit:\n    - action: demo.first-check\n    - action: demo.second-check\n"
    )

    manifest = load_manifest(project_path=project_path, user_path=tmp_path / "missing-user.yaml")

    action_names = [b.action for b in manifest.bindings]
    default_names = [b.action for b in DEFAULT_BINDINGS]
    assert action_names[: len(default_names)] == default_names
    assert action_names[len(default_names) :] == ["demo.first-check", "demo.second-check"]


def test_default_bindings_order_is_909_before_911() -> None:
    post_action_names = [b.action for b in DEFAULT_BINDINGS if b.event is EventType.POST_ACTION]
    assert post_action_names == ["squadron.dispatch-artifact", "squadron.revision-stamp"]
