"""Tests for ReviewTemplate dataclass, YAML loader, and template registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.review.models import TemplateValidationError
from squadron.review.templates import (
    InputDef,
    ReviewTemplate,
    clear_registry,
    get_template,
    list_templates,
    load_template,
    register_template,
)

# -- Fixtures ---------------------------------------------------------------

VALID_YAML = """\
name: test-template
description: A test template
system_prompt: You are a reviewer.
allowed_tools: [Read, Glob]
permission_mode: bypassPermissions
setting_sources: null
inputs:
  required:
    - name: input
      description: File to review
  optional:
    - name: cwd
      description: Working directory
      default: "."
prompt_template: |
  Review the file at {input} in directory {cwd}.
"""

BOTH_PROMPT_YAML = """\
name: bad
description: Both prompt fields
system_prompt: x
allowed_tools: []
permission_mode: bypassPermissions
prompt_template: "hello {input}"
prompt_builder: some.module.func
inputs:
  required: []
"""

NEITHER_PROMPT_YAML = """\
name: bad
description: Neither prompt field
system_prompt: x
allowed_tools: []
permission_mode: bypassPermissions
inputs:
  required: []
"""

BUILDER_YAML = """\
name: builder-test
description: Uses prompt_builder
system_prompt: You review code.
allowed_tools: [Read]
permission_mode: bypassPermissions
inputs:
  required: []
prompt_builder: squadron.review.tests_helpers.sample_builder
"""


# -- Helper for prompt_builder tests ----------------------------------------
# We need a real importable function. Create a mini module in-memory.


def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "template.yaml"
    p.write_text(content)
    return p


# -- Tests -------------------------------------------------------------------


class TestLoadTemplate:
    """Test load_template with valid and invalid YAML."""

    def test_valid_inline_yaml(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, VALID_YAML)
        t = load_template(path)

        assert t.name == "test-template"
        assert t.description == "A test template"
        assert t.system_prompt.strip() == "You are a reviewer."
        assert t.allowed_tools == ["Read", "Glob"]
        assert t.permission_mode == "bypassPermissions"
        assert t.setting_sources is None
        assert len(t.required_inputs) == 1
        assert t.required_inputs[0].name == "input"
        assert len(t.optional_inputs) == 1
        assert t.optional_inputs[0].default == "."
        assert t.prompt_template is not None
        assert t.prompt_builder is None
        assert t.model is None  # no model in YAML → None

    def test_profile_field_parsed_from_yaml(self, tmp_path: Path) -> None:
        yaml_with_profile = VALID_YAML.replace(
            "permission_mode: bypassPermissions",
            "permission_mode: bypassPermissions\nprofile: openrouter",
        )
        path = _write_yaml(tmp_path, yaml_with_profile)
        t = load_template(path)
        assert t.profile == "openrouter"

    def test_profile_field_defaults_to_none(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, VALID_YAML)
        t = load_template(path)
        assert t.profile is None

    def test_review_template_has_profile_attribute(self) -> None:
        t = ReviewTemplate(
            name="t",
            description="d",
            system_prompt="s",
            allowed_tools=[],
            permission_mode="bypassPermissions",
            setting_sources=None,
            required_inputs=[],
            optional_inputs=[],
            prompt_template="hello",
            profile="sdk",
        )
        assert t.profile == "sdk"

    def test_model_field_parsed_from_yaml(self, tmp_path: Path) -> None:
        yaml_with_model = VALID_YAML.replace(
            "permission_mode: bypassPermissions",
            "permission_mode: bypassPermissions\nmodel: opus",
        )
        path = _write_yaml(tmp_path, yaml_with_model)
        t = load_template(path)
        assert t.model == "opus"

    def test_build_prompt_with_template(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, VALID_YAML)
        t = load_template(path)
        prompt = t.build_prompt({"input": "file.md", "cwd": "/project"})
        assert "file.md" in prompt
        assert "/project" in prompt

    def test_both_prompt_fields_raises(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, BOTH_PROMPT_YAML)
        with pytest.raises(TemplateValidationError, match="both"):
            load_template(path)

    def test_neither_prompt_field_raises(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, NEITHER_PROMPT_YAML)
        with pytest.raises(TemplateValidationError, match="must specify"):
            load_template(path)

    def test_prompt_builder_resolution(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test prompt_builder dotted-path resolution with a real function."""
        import types

        # Create a temporary module with a sample builder
        mod = types.ModuleType("squadron.review.tests_helpers")
        mod.sample_builder = lambda inputs: f"reviewing {inputs.get('cwd', '.')}"  # type: ignore[attr-defined]
        import sys

        monkeypatch.setitem(sys.modules, "squadron.review.tests_helpers", mod)

        path = _write_yaml(tmp_path, BUILDER_YAML)
        t = load_template(path)
        assert t.prompt_builder is not None
        assert callable(t.prompt_builder)
        result = t.build_prompt({"cwd": "/test"})
        assert result == "reviewing /test"

    def test_unresolvable_builder_raises(self, tmp_path: Path) -> None:
        yaml_content = """\
name: bad-builder
description: Unresolvable builder
system_prompt: x
allowed_tools: []
permission_mode: bypassPermissions
inputs:
  required: []
prompt_builder: nonexistent.module.func
"""
        path = _write_yaml(tmp_path, yaml_content)
        with pytest.raises(TemplateValidationError, match="Cannot import"):
            load_template(path)


class TestBuildPrompt:
    """Test ReviewTemplate.build_prompt edge cases."""

    def test_raises_when_neither_set(self) -> None:
        t = ReviewTemplate(
            name="empty",
            description="No prompt",
            system_prompt="x",
            allowed_tools=[],
            permission_mode="bypassPermissions",
            setting_sources=None,
            required_inputs=[],
            optional_inputs=[],
        )
        with pytest.raises(ValueError, match="neither"):
            t.build_prompt({})


class TestRegistry:
    """Test template registry operations."""

    @pytest.fixture(autouse=True)
    def _clean_registry(self) -> None:
        clear_registry()

    def test_register_and_get(self) -> None:
        t = ReviewTemplate(
            name="my-template",
            description="Test",
            system_prompt="x",
            allowed_tools=[],
            permission_mode="bypassPermissions",
            setting_sources=None,
            required_inputs=[],
            optional_inputs=[],
            prompt_template="hello",
        )
        register_template(t)
        assert get_template("my-template") is t

    def test_get_missing_returns_none(self) -> None:
        assert get_template("nonexistent") is None

    def test_list_templates(self) -> None:
        for name in ("a", "b", "c"):
            register_template(
                ReviewTemplate(
                    name=name,
                    description=f"Template {name}",
                    system_prompt="x",
                    allowed_tools=[],
                    permission_mode="bypassPermissions",
                    setting_sources=None,
                    required_inputs=[],
                    optional_inputs=[],
                    prompt_template="hello",
                )
            )
        templates = list_templates()
        assert len(templates) == 3
        names = {t.name for t in templates}
        assert names == {"a", "b", "c"}


class TestInputDef:
    """Test InputDef dataclass."""

    def test_with_default(self) -> None:
        i = InputDef(name="cwd", description="Working dir", default=".")
        assert i.default == "."

    def test_without_default(self) -> None:
        i = InputDef(name="input", description="File to review")
        assert i.default is None


# ---------------------------------------------------------------------------
# T8: Prompt hardening present in all three builtin templates
# ---------------------------------------------------------------------------


class TestBuiltinTemplateHardening:
    """Test that all three builtin templates have the CRITICAL consistency block."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        from squadron.review.templates import load_all_templates

        load_all_templates()

    def _get(self, name: str) -> ReviewTemplate:
        t = get_template(name)
        assert t is not None, f"Template '{name}' not found"
        return t

    def test_slice_template_has_consistency_instruction(self) -> None:
        t = self._get("slice")
        assert "CRITICAL" in t.system_prompt

    def test_tasks_template_has_consistency_instruction(self) -> None:
        t = self._get("tasks")
        assert "CRITICAL" in t.system_prompt

    def test_code_template_has_consistency_instruction(self) -> None:
        t = self._get("code")
        assert "CRITICAL" in t.system_prompt
