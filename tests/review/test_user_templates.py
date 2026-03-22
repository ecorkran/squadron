"""Tests for user template loading from ~/.config/squadron/templates/."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.review.templates import (
    clear_registry,
    get_template,
    list_templates,
    load_all_templates,
)

USER_TEMPLATE_YAML = """\
name: arch
description: "Custom architectural review"
model: gpt-4o
profile: openai
system_prompt: |
  You are a custom reviewer.
allowed_tools: [Read]
permission_mode: bypassPermissions
inputs:
  required:
    - name: input
      description: "Document to review"
  optional: []
prompt_template: |
  Review: {input}
"""

CUSTOM_TEMPLATE_YAML = """\
name: security
description: "Security review"
model: opus
system_prompt: |
  You are a security reviewer.
allowed_tools: [Read, Glob]
permission_mode: bypassPermissions
inputs:
  required:
    - name: input
      description: "Code to review"
  optional: []
prompt_template: |
  Security review: {input}
"""


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    clear_registry()


class TestUserTemplateOverride:
    """Test user templates override built-in by name."""

    def test_user_template_overrides_builtin(self, tmp_path: Path) -> None:
        user_dir = tmp_path / "templates"
        user_dir.mkdir()
        (user_dir / "arch.yaml").write_text(USER_TEMPLATE_YAML)

        load_all_templates(user_dir=user_dir)

        t = get_template("arch")
        assert t is not None
        assert t.description == "Custom architectural review"
        assert t.model == "gpt-4o"
        assert t.profile == "openai"


class TestUserTemplateAddNew:
    """Test user templates can add new review types."""

    def test_user_template_adds_new_type(self, tmp_path: Path) -> None:
        user_dir = tmp_path / "templates"
        user_dir.mkdir()
        (user_dir / "security.yaml").write_text(CUSTOM_TEMPLATE_YAML)

        load_all_templates(user_dir=user_dir)

        t = get_template("security")
        assert t is not None
        assert t.name == "security"
        assert t.description == "Security review"

        # Built-in templates should also be loaded
        templates = list_templates()
        names = {t.name for t in templates}
        assert "security" in names
        # Built-in 'slice' should also be present (renamed from arch)
        assert "slice" in names


class TestMissingUserDirectory:
    """Test graceful handling of missing user template directory."""

    def test_missing_directory_no_error(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nonexistent"
        # Should not raise
        load_all_templates(user_dir=nonexistent)
        # Built-in templates still loaded
        templates = list_templates()
        assert len(templates) > 0


class TestReviewListShowsBoth:
    """Test that list_templates shows both built-in and user."""

    def test_list_includes_user_and_builtin(self, tmp_path: Path) -> None:
        user_dir = tmp_path / "templates"
        user_dir.mkdir()
        (user_dir / "security.yaml").write_text(CUSTOM_TEMPLATE_YAML)

        load_all_templates(user_dir=user_dir)

        templates = list_templates()
        names = {t.name for t in templates}
        # 'security' is user-defined, 'slice'/'tasks'/'code' are built-in
        assert "security" in names
        assert "slice" in names
