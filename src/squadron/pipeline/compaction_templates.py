"""Shared compaction/summary template helpers.

This module is the single owner of compaction template loading and rendering.
It was extracted from ``actions/compact.py`` (slice 166) so that all consumers
(``prompt_renderer``, ``summary_render``, ``summary.py``, ``summary_run``) can
import from here rather than from an action-specific module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

from squadron.data import data_dir
from squadron.pipeline.compact_render import LenientDict

_USER_COMPACTION_DIR = Path.home() / ".config" / "squadron" / "compaction"


@dataclass
class CompactionTemplate:
    """Runtime representation of a compaction instruction template."""

    name: str
    description: str
    instructions: str
    suffix: str = ""


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
        suffix=str(data["suffix"]) if "suffix" in data else "",
    )


def render_instructions(
    template: CompactionTemplate,
    *,
    keep: list[str] | None = None,
    summarize: bool = False,
    pipeline_params: dict[str, object] | None = None,
) -> str:
    """Render compaction instructions with the given parameters.

    Pipeline params (e.g. ``slice``, ``model``) are available as
    ``{param_name}`` placeholders in the template.  Unknown placeholders
    are left as-is rather than raising ``KeyError``.
    """
    if keep:
        keep_section = "Preserve the following artifacts in full:\n" + "\n".join(
            f"- {item}" for item in keep
        )
    else:
        keep_section = ""

    if summarize:
        summarize_section = (
            "After compaction, generate a concise summary of the compacted content."
        )
    else:
        summarize_section = ""

    format_vars = LenientDict(
        keep_section=keep_section,
        summarize_section=summarize_section,
    )
    if pipeline_params:
        for k, v in pipeline_params.items():
            format_vars[k] = str(v)

    return template.instructions.format_map(format_vars).strip()
