"""ReviewTemplate dataclass, YAML loader, and template registry."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

from squadron.review.models import TemplateValidationError


@dataclass
class InputDef:
    """Definition of a template input (CLI argument)."""

    name: str
    description: str
    default: str | None = None


@dataclass
class ReviewTemplate:
    """Runtime representation of a review workflow template. Loaded from YAML."""

    name: str
    description: str
    system_prompt: str
    allowed_tools: list[str]
    permission_mode: str
    setting_sources: list[str] | None
    required_inputs: list[InputDef]
    optional_inputs: list[InputDef]
    hooks: dict[str, object] | None = None
    model: str | None = None
    profile: str | None = None

    # Prompt construction — exactly one of these is set (validated at load time)
    prompt_template: str | None = None
    prompt_builder: Callable[[dict[str, str]], str] | None = None

    def build_prompt(self, inputs: dict[str, str]) -> str:
        """Construct the review prompt from user-supplied inputs."""
        if self.prompt_builder is not None:
            return self.prompt_builder(inputs)
        if self.prompt_template is not None:
            return self.prompt_template.format(**inputs)
        raise ValueError(
            f"Template '{self.name}' has neither prompt_template nor prompt_builder"
        )


# ---------------------------------------------------------------------------
# YAML Loader
# ---------------------------------------------------------------------------


def _resolve_builder(dotted_path: str) -> Callable[[dict[str, str]], str]:
    """Resolve a dotted Python path to a callable."""
    parts = dotted_path.rsplit(".", 1)
    if len(parts) != 2:
        raise TemplateValidationError(
            f"prompt_builder must be a dotted path (module.function), "
            f"got: {dotted_path}"
        )
    module_path, func_name = parts
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise TemplateValidationError(
            f"Cannot import module '{module_path}' for prompt_builder"
        ) from exc

    func = getattr(module, func_name, None)
    if func is None:
        raise TemplateValidationError(
            f"Module '{module_path}' has no attribute '{func_name}'"
        )
    if not callable(func):
        raise TemplateValidationError(f"'{dotted_path}' is not callable")
    return func  # type: ignore[return-value]


def load_template(path: Path) -> ReviewTemplate:
    """Load a ReviewTemplate from a YAML file."""
    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise TemplateValidationError(f"Template file is not a YAML mapping: {path}")

    data = cast(dict[str, object], raw)

    # Validate mutually exclusive prompt fields
    has_template = "prompt_template" in data
    has_builder = "prompt_builder" in data
    if has_template and has_builder:
        raise TemplateValidationError(
            f"Template '{path}' specifies both prompt_template and prompt_builder"
        )
    if not has_template and not has_builder:
        raise TemplateValidationError(
            f"Template '{path}' must specify prompt_template or prompt_builder"
        )

    # Resolve prompt_builder to callable if specified
    builder = None
    if has_builder:
        builder = _resolve_builder(str(data["prompt_builder"]))

    # Parse input definitions
    inputs_raw = data.get("inputs", {})
    inputs_data = cast(
        dict[str, object], inputs_raw if isinstance(inputs_raw, dict) else {}
    )
    req_list: list[object] = list(inputs_data.get("required") or [])  # type: ignore[arg-type]
    opt_list: list[object] = list(inputs_data.get("optional") or [])  # type: ignore[arg-type]
    required = [InputDef(**i) for i in req_list]  # type: ignore[arg-type]
    optional = [InputDef(**i) for i in opt_list]  # type: ignore[arg-type]

    setting_src = data.get("setting_sources")
    hooks_raw = data.get("hooks")

    return ReviewTemplate(
        name=str(data["name"]),
        description=str(data["description"]),
        system_prompt=str(data["system_prompt"]),
        allowed_tools=list(data["allowed_tools"]),  # type: ignore[arg-type]
        permission_mode=str(data["permission_mode"]),
        setting_sources=list(setting_src) if setting_src else None,  # type: ignore[arg-type]
        required_inputs=required,
        optional_inputs=optional,
        hooks=dict(hooks_raw) if isinstance(hooks_raw, dict) else None,  # type: ignore[arg-type]
        model=str(data["model"]) if "model" in data else None,
        profile=str(data["profile"]) if "profile" in data else None,
        prompt_template=(
            str(data["prompt_template"]) if "prompt_template" in data else None
        ),
        prompt_builder=builder,
    )


# ---------------------------------------------------------------------------
# Template Registry
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, ReviewTemplate] = {}


def register_template(template: ReviewTemplate) -> None:
    """Register a template by name."""
    _TEMPLATES[template.name] = template


def get_template(name: str) -> ReviewTemplate | None:
    """Look up a template by name. Returns None if not found."""
    return _TEMPLATES.get(name)


def list_templates() -> list[ReviewTemplate]:
    """Return all registered templates."""
    return list(_TEMPLATES.values())


def clear_registry() -> None:
    """Remove all registered templates. Useful for testing."""
    _TEMPLATES.clear()


_USER_TEMPLATES_DIR = Path.home() / ".config" / "squadron" / "templates"


def load_all_templates(
    user_dir: Path | None = None,
) -> None:
    """Load built-in and user templates.

    Built-in templates are loaded first, then user templates from
    ~/.config/squadron/templates/. User templates with the same name
    override built-in ones.
    """
    # Built-in templates
    builtin_dir = Path(__file__).parent / "builtin"
    if builtin_dir.is_dir():
        for yaml_file in sorted(builtin_dir.glob("*.yaml")):
            template = load_template(yaml_file)
            register_template(template)

    # User templates (override built-in by name)
    user_templates_dir = user_dir or _USER_TEMPLATES_DIR
    if user_templates_dir.is_dir():
        for yaml_file in sorted(user_templates_dir.glob("*.yaml")):
            template = load_template(yaml_file)
            register_template(template)


# Backward-compatible alias
load_builtin_templates = load_all_templates
