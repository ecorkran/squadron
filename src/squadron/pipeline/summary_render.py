"""Shared helpers for rendering summary/compaction template instructions.

Loads a compaction template by name, gathers Context Forge project params
(best-effort), and renders placeholders.  Used by the ``_summary-instructions``
CLI command and potentially other summary-producing entry points.
"""

from __future__ import annotations

import os
from pathlib import Path

from squadron.integrations.context_forge import (
    ContextForgeClient,
    ContextForgeError,
    ContextForgeNotAvailable,
)
from squadron.pipeline.actions.compact import load_compaction_template
from squadron.pipeline.compact_render import render_with_params


def resolve_template_instructions(
    template_name: str,
    *,
    cwd: str = ".",
) -> str:
    """Load a compaction template, gather CF params, and render placeholders.

    Args:
        template_name: Name of the compaction template (e.g. ``"minimal"``).
        cwd: Working directory for CF param resolution.

    Returns:
        Rendered instruction text with placeholders substituted.

    Raises:
        FileNotFoundError: If no template with the given name exists.
    """
    template = load_compaction_template(template_name)
    params = gather_cf_params(cwd)
    return render_with_params(template.instructions, params)


def resolve_template_suffix(
    template_name: str,
    *,
    cwd: str = ".",
) -> str:
    """Return the rendered suffix for a compaction template, or empty string.

    The suffix is appended verbatim to the clipboard content after the summary,
    bypassing LLM generation.  Returns ``""`` if the template has no suffix.

    Raises:
        FileNotFoundError: If no template with the given name exists.
    """
    template = load_compaction_template(template_name)
    params = gather_cf_params(cwd)
    return render_with_params(template.suffix, params) if template.suffix else ""


def gather_cf_params(cwd: str) -> dict[str, object]:
    """Return available render params from Context Forge (best-effort).

    Keys: ``project``, ``slice``, ``phase``.  Returns ``{}`` on any failure
    so that the lenient renderer leaves placeholders intact.
    """
    resolved_cwd = Path(cwd).resolve()
    project_name = resolved_cwd.name

    original_cwd = os.getcwd()
    try:
        try:
            os.chdir(resolved_cwd)
        except (FileNotFoundError, OSError):
            return {}
        try:
            info = ContextForgeClient().get_project()
        except (
            ContextForgeError,
            ContextForgeNotAvailable,
            FileNotFoundError,
            OSError,
        ):
            return {}
    finally:
        try:
            os.chdir(original_cwd)
        except OSError:
            pass

    # Only include non-empty values so that LenientDict leaves placeholders
    # intact for params CF doesn't know about.
    params: dict[str, object] = {"project": project_name}
    if info.slice:
        params["slice"] = info.slice
    if info.phase:
        params["phase"] = info.phase
    return params
