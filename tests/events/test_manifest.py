"""Tests for the event binding manifest loader (design D6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.events import EventType
from squadron.events.manifest import (
    DEFAULT_BINDINGS,
    ManifestError,
    load_manifest,
    resolve_bindings,
)

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


def test_unknown_action_name_errors_naming_both(tmp_path: Path) -> None:
    project_path = tmp_path / "project-events.yaml"
    project_path.write_text(_PROJECT_MANIFEST_YAML)

    manifest = load_manifest(project_path=project_path, user_path=tmp_path / "missing-user.yaml")
    registered = [b.action for b in DEFAULT_BINDINGS]

    with pytest.raises(ManifestError) as exc_info:
        resolve_bindings(manifest, registered_names=registered)

    message = str(exc_info.value)
    assert "demo.rule-check" in message
    assert all(name in message for name in registered)


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
