"""Compact action — issues compaction instructions to ContextForge."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

from squadron.data import data_dir
from squadron.integrations.context_forge import ContextForgeClient, ContextForgeError
from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError

_USER_COMPACTION_DIR = Path.home() / ".config" / "squadron" / "compaction"


@dataclass
class CompactionTemplate:
    """Runtime representation of a compaction instruction template."""

    name: str
    description: str
    instructions: str


def load_compaction_template(
    template_name: str,
    *,
    user_dir: Path | None = None,
) -> CompactionTemplate:
    """Load a compaction template by name.

    Resolution order:
    1. User override directory (``~/.config/squadron/compaction/``)
    2. Built-in directory (``src/squadron/data/compaction/``)

    Raises:
        FileNotFoundError: If no template with the given name exists.
    """
    filename = f"{template_name}.yaml"
    user_templates = user_dir or _USER_COMPACTION_DIR

    # User override takes precedence
    user_path = user_templates / filename
    if user_path.is_file():
        return _parse_template(user_path)

    # Fall back to built-in
    builtin_path = data_dir() / "compaction" / filename
    if builtin_path.is_file():
        return _parse_template(builtin_path)

    raise FileNotFoundError(
        f"Compaction template '{template_name}' not found. "
        f"Searched: {user_templates}, {data_dir() / 'compaction'}"
    )


def _parse_template(path: Path) -> CompactionTemplate:
    """Parse a compaction template YAML file."""
    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Compaction template is not a YAML mapping: {path}")

    data = cast(dict[str, object], raw)
    return CompactionTemplate(
        name=str(data["name"]),
        description=str(data["description"]),
        instructions=str(data["instructions"]),
    )


def render_instructions(
    template: CompactionTemplate,
    *,
    keep: list[str] | None = None,
    summarize: bool = False,
) -> str:
    """Render compaction instructions with the given parameters."""
    if keep:
        keep_section = "Preserve the following artifacts in full:\n" + "\n".join(
            f"- {item}" for item in keep
        )
    else:
        keep_section = "No specific artifacts designated for preservation."

    if summarize:
        summarize_section = (
            "After compaction, generate a concise summary of the compacted content."
        )
    else:
        summarize_section = "No summary requested."

    return template.instructions.format(
        keep_section=keep_section,
        summarize_section=summarize_section,
    )


class CompactAction:
    """Pipeline action that issues compaction instructions to ContextForge."""

    @property
    def action_type(self) -> str:
        return ActionType.COMPACT

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        errors: list[ValidationError] = []

        keep = config.get("keep")
        if keep is not None and (
            not isinstance(keep, list)
            or not all(isinstance(item, str) for item in cast(list[object], keep))
        ):
            errors.append(
                ValidationError(
                    field="keep",
                    message="'keep' must be a list of strings",
                    action_type=self.action_type,
                )
            )

        summarize = config.get("summarize")
        if summarize is not None and not isinstance(summarize, bool):
            errors.append(
                ValidationError(
                    field="summarize",
                    message="'summarize' must be a boolean",
                    action_type=self.action_type,
                )
            )

        template = config.get("template")
        if template is not None and not isinstance(template, str):
            errors.append(
                ValidationError(
                    field="template",
                    message="'template' must be a string",
                    action_type=self.action_type,
                )
            )

        return errors

    async def execute(self, context: ActionContext) -> ActionResult:
        template_name = str(context.params.get("template", "default"))
        keep_raw = context.params.get("keep")
        keep: list[str] | None = (
            [str(item) for item in cast(list[object], keep_raw)]
            if isinstance(keep_raw, list)
            else None
        )
        summarize = bool(context.params.get("summarize", False))

        try:
            template = load_compaction_template(template_name)
        except FileNotFoundError as exc:
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=str(exc),
            )

        instructions = render_instructions(template, keep=keep, summarize=summarize)

        cf_client: ContextForgeClient = context.cf_client  # type: ignore[assignment]

        try:
            stdout = cf_client._run(  # pyright: ignore[reportPrivateUsage]
                ["compact", "--instructions", instructions]
            )

            summarize_stdout = ""
            if summarize:
                summarize_stdout = cf_client._run(  # pyright: ignore[reportPrivateUsage]
                    ["summarize"]
                )
        except ContextForgeError as exc:
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=str(exc),
            )

        outputs: dict[str, object] = {
            "stdout": stdout,
            "instructions": instructions,
        }
        if summarize:
            outputs["summarize_stdout"] = summarize_stdout

        return ActionResult(
            success=True,
            action_type=self.action_type,
            outputs=outputs,
        )


register_action(ActionType.COMPACT, CompactAction())
