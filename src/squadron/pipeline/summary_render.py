"""Shared helpers for rendering summary/compaction template instructions.

Loads a compaction template by name, gathers Context Forge project params
(best-effort), and renders placeholders.  Used by the ``_summary-instructions``
CLI command and potentially other summary-producing entry points.
"""

from __future__ import annotations

import logging
from pathlib import Path

from squadron.integrations.context_forge import (
    ContextForgeClient,
    ContextForgeError,
    ContextForgeNotAvailable,
)
from squadron.pipeline.compact_render import render_with_params
from squadron.pipeline.compaction_templates import load_compaction_template, render_instructions

_logger = logging.getLogger(__name__)


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
    # This entry point has no --keep/--summarize CLI flags, so keep/summarize
    # are always their defaults (empty/False) — routed through
    # render_instructions() so keep_section/summarize_section resolve to ""
    # instead of leaking as literal placeholder text (issue #21).
    return render_instructions(template, pipeline_params=params)


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

    try:
        info = ContextForgeClient(cwd=resolved_cwd).get_project()
    except (ContextForgeError, ContextForgeNotAvailable, OSError) as exc:
        # Best-effort by contract: the lenient renderer keeps placeholders.
        _logger.warning("Context Forge params unavailable for %s: %s", resolved_cwd, exc)
        return {}

    # Only include non-empty values so that LenientDict leaves placeholders
    # intact for params CF doesn't know about.
    params: dict[str, object] = {"project": project_name}
    if info.slice:
        params["slice"] = info.slice
    if info.phase:
        params["phase"] = info.phase
    return params
