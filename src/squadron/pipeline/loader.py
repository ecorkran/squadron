"""Pipeline loader — load, discover, and validate pipeline definitions.

Loads pipeline YAML files from built-in, user, and project directories,
validates them via the Pydantic schema, and converts to PipelineDefinition.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from squadron.data import data_dir
from squadron.pipeline.models import PipelineDefinition, StepConfig, ValidationError
from squadron.pipeline.schema import PipelineSchema

_logger = logging.getLogger(__name__)

_BUILTIN_DIR = data_dir() / "pipelines"
_USER_DIR = Path.home() / ".config" / "squadron" / "pipelines"
_PROJECT_PIPELINES_REL = Path("project-documents/user/pipelines")


@dataclass
class PipelineInfo:
    """Metadata about a discovered pipeline."""

    name: str
    description: str
    source: str  # "built-in" | "user" | "project"
    path: Path


def _load_yaml(path: Path) -> PipelineDefinition:
    """Read a YAML file, validate via PipelineSchema, return PipelineDefinition.

    Raises FileNotFoundError if the file doesn't exist.
    Raises pydantic.ValidationError on structural validation failure.
    """
    with open(path) as f:
        raw = yaml.safe_load(f)

    schema = PipelineSchema.model_validate(raw)
    return schema.to_definition()


def load_pipeline(
    name_or_path: str,
    *,
    project_dir: Path | None = None,
    user_dir: Path | None = None,
) -> PipelineDefinition:
    """Load a pipeline by name or file path.

    If *name_or_path* is an existing file path, load directly.
    Otherwise treat as a pipeline name and search project → user → built-in
    directories for ``{name}.yaml``.

    Raises FileNotFoundError if the pipeline cannot be found.
    """
    candidate = Path(name_or_path)
    if candidate.is_file():
        return _load_yaml(candidate)

    # Normalise name to lowercase for case-insensitive lookup
    name_or_path = name_or_path.lower()

    # Search directories: project (highest priority) → user → built-in
    search_dirs = _search_dirs(project_dir=project_dir, user_dir=user_dir)
    for search_dir in search_dirs:
        yaml_path = search_dir / f"{name_or_path}.yaml"
        if yaml_path.is_file():
            return _load_yaml(yaml_path)

    raise FileNotFoundError(
        f"Pipeline '{name_or_path}' not found in any pipeline directory. "
        f"Searched: {[str(d) for d in search_dirs]}"
    )


def _search_dirs(
    *,
    project_dir: Path | None = None,
    user_dir: Path | None = None,
) -> list[Path]:
    """Return pipeline directories in search order (highest priority first)."""
    dirs: list[Path] = []

    proj = (
        project_dir
        if project_dir is not None
        else (Path.cwd() / _PROJECT_PIPELINES_REL)
    )
    dirs.append(proj)

    user = user_dir if user_dir is not None else _USER_DIR
    dirs.append(user)

    dirs.append(_BUILTIN_DIR)
    return dirs


def discover_pipelines(
    *,
    project_dir: Path | None = None,
    user_dir: Path | None = None,
) -> list[PipelineInfo]:
    """Discover all available pipelines from all sources.

    Scans built-in → user → project directories for ``*.yaml`` files.
    Later sources overwrite earlier ones by pipeline name (project wins).
    Returns a sorted list of PipelineInfo.
    """
    source_dirs: list[tuple[Path, str]] = [
        (_BUILTIN_DIR, "built-in"),
    ]

    user = user_dir if user_dir is not None else _USER_DIR
    source_dirs.append((user, "user"))

    proj = (
        project_dir
        if project_dir is not None
        else (Path.cwd() / _PROJECT_PIPELINES_REL)
    )
    source_dirs.append((proj, "project"))

    found: dict[str, PipelineInfo] = {}

    for directory, source in source_dirs:
        if not directory.is_dir():
            continue
        for yaml_path in sorted(directory.glob("*.yaml")):
            try:
                with open(yaml_path) as f:
                    raw = yaml.safe_load(f)
                schema = PipelineSchema.model_validate(raw)
                pipeline_name = schema.name.lower()
                found[pipeline_name] = PipelineInfo(
                    name=pipeline_name,
                    description=schema.description,
                    source=source,
                    path=yaml_path,
                )
            except Exception:
                _logger.warning("Skipping invalid pipeline file: %s", yaml_path)
                continue

    return sorted(found.values(), key=lambda p: p.name)


def validate_pipeline(
    definition: PipelineDefinition,
) -> list[ValidationError]:
    """Semantic validation of a pipeline definition.

    Checks beyond structural schema validation:
    - Step types are registered in the step type registry
    - Model aliases resolve
    - Review template names exist
    - Param placeholders in step configs reference declared params
    """
    # Trigger step type registration by importing step modules
    import squadron.pipeline.steps.collection as _collection  # noqa: F401
    import squadron.pipeline.steps.compact as _compact  # noqa: F401
    import squadron.pipeline.steps.devlog as _devlog  # noqa: F401
    import squadron.pipeline.steps.phase as _phase  # noqa: F401
    import squadron.pipeline.steps.review as _review  # noqa: F401
    import squadron.pipeline.steps.summary as _summary  # noqa: F401

    _ = (
        _collection,
        _compact,
        _devlog,
        _phase,
        _review,
        _summary,
    )  # satisfy unused-import checks

    from squadron.models.aliases import resolve_model_alias
    from squadron.pipeline.steps import get_step_type, list_step_types
    from squadron.review.templates import (
        get_template,
        list_templates,
        load_all_templates,
    )

    # Ensure review templates are loaded for template name validation
    if not list_templates():
        load_all_templates()

    errors: list[ValidationError] = []
    registered = list_step_types()
    declared_params = set(definition.params.keys())

    # Validate pipeline-level model alias
    if definition.model is not None:
        _validate_model_alias(definition.model, "model", errors, resolve_model_alias)

    for step in definition.steps:
        # Check step type is registered
        if step.step_type not in registered:
            errors.append(
                ValidationError(
                    field="step_type",
                    message=(
                        f"Unknown step type '{step.step_type}'. "
                        f"Registered: {registered}"
                    ),
                    action_type=step.step_type,
                )
            )
        else:
            # Delegate to step type's own validate()
            step_impl = get_step_type(step.step_type)
            errors.extend(step_impl.validate(step))

        # Validate step-level model alias
        model_val = step.config.get("model")
        if isinstance(model_val, str):
            _validate_model_alias(
                model_val,
                f"steps[{step.name}].model",
                errors,
                resolve_model_alias,
            )

        # Validate review template references
        _validate_review_template(step, errors, get_template)

        # Validate param placeholders
        _validate_param_placeholders(step, declared_params, errors)

    return errors


def _validate_model_alias(
    alias: str,
    field: str,
    errors: list[ValidationError],
    resolver: object,
) -> None:
    """Check that a model alias resolves. Skip placeholders."""
    if "{" in alias:
        return  # Contains param placeholder — skip at validation time
    from squadron.models.aliases import resolve_model_alias

    _model_id, profile = resolve_model_alias(alias)
    if profile is None:
        errors.append(
            ValidationError(
                field=field,
                message=f"Model alias '{alias}' did not resolve to a known alias",
                action_type="pipeline",
            )
        )


def _validate_review_template(
    step: StepConfig,
    errors: list[ValidationError],
    get_template_fn: object,
) -> None:
    """Check review template references in step config."""
    from squadron.review.templates import get_template

    review_val = step.config.get("review")
    template_name: str | None = None

    if isinstance(review_val, str):
        template_name = review_val
    elif isinstance(review_val, dict):
        review_dict = cast(dict[str, Any], review_val)
        tpl: object = review_dict.get("template")
        if isinstance(tpl, str):
            template_name = tpl

    if template_name is None:
        return
    if "{" in template_name:
        return  # Contains param placeholder — skip

    if get_template(template_name) is None:
        errors.append(
            ValidationError(
                field=f"steps[{step.name}].review.template",
                message=f"Review template '{template_name}' not found",
                action_type=step.step_type,
            )
        )


def _validate_param_placeholders(
    step: StepConfig,
    declared_params: set[str],
    errors: list[ValidationError],
) -> None:
    """Check that {param_name} placeholders in config reference declared params."""
    import re

    # Match {name} or {name.attr} style placeholders
    placeholder_re = re.compile(r"\{([\w.]+)\}")

    for key, value in step.config.items():
        if not isinstance(value, str):
            continue
        for match in placeholder_re.finditer(value):
            ref = match.group(1)
            # Dotted references like {slice.index} are loop variables
            # from the `each` step type — not pipeline params
            if "." in ref:
                continue
            if ref not in declared_params:
                errors.append(
                    ValidationError(
                        field=f"steps[{step.name}].{key}",
                        message=(
                            f"Param placeholder '{{{ref}}}' "
                            f"references undeclared param '{ref}'"
                        ),
                        action_type=step.step_type,
                    )
                )
