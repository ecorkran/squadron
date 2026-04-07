"""[hidden] PreCompact hook subcommand for interactive Claude Code.

Invoked by the ``PreCompact`` entry in ``.claude/settings.json``. Reads
squadron config to pick either a compaction template (``compact.template``)
or a literal instruction string (``compact.instructions``), gathers project
params from Context Forge (best-effort), renders placeholders, and emits
the Claude Code PreCompact hook JSON payload on stdout.

Contract: this command must never break the user's ``/compact`` — it always
exits 0, even if every resolution step fails. On failure, it emits a valid
payload with an empty ``additionalContext`` string.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import typer

from squadron.config.manager import get_config
from squadron.integrations.context_forge import (
    ContextForgeClient,
    ContextForgeError,
    ContextForgeNotAvailable,
)
from squadron.pipeline.actions.compact import load_compaction_template
from squadron.pipeline.compact_render import render_with_params


def _resolve_instructions(cwd: str) -> str:
    """Return the raw (pre-render) instructions for this hook invocation.

    Precedence:
    1. ``compact.instructions`` config value (literal) if non-empty.
    2. Template named by ``compact.template`` config value (default "minimal").
    3. Empty string if the template cannot be loaded.

    The hook must never raise — a missing or corrupt template just yields
    an empty string and lets the caller emit an empty ``additionalContext``.
    """
    literal = get_config("compact.instructions", cwd=cwd)
    if isinstance(literal, str) and literal.strip():
        return literal

    template_value = get_config("compact.template", cwd=cwd)
    template_name = (
        template_value
        if isinstance(template_value, str) and template_value
        else "minimal"
    )

    try:
        template = load_compaction_template(template_name)
    except (FileNotFoundError, ValueError):
        return ""
    return template.instructions


def _gather_params(cwd: str) -> dict[str, object]:
    """Return available render params from Context Forge (best-effort).

    Keys: ``slice``, ``phase``, ``project``. CF unavailability is silently
    absorbed — callers should treat a ``{}`` return as "no params, let the
    lenient renderer leave placeholders intact".
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

    return {
        "slice": info.slice or "",
        "phase": info.phase or "",
        "project": project_name,
    }


def precompact_hook(
    cwd: str = typer.Option(".", "--cwd", hidden=True),
) -> None:
    """[hidden] Emit PreCompact hook output. Invoked by Claude Code."""
    # Tight catch-all: the hook's contract is "never break the user's
    # /compact". A bare Exception catch is justified here (and nowhere else
    # in squadron) because any failure inside the render pipeline must
    # degrade to an empty additionalContext, not a non-zero exit.
    try:
        instructions = _resolve_instructions(cwd)
        params = _gather_params(cwd)
        rendered = render_with_params(instructions, params)
    except Exception:  # noqa: BLE001 - see comment above
        rendered = ""

    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreCompact",
            "additionalContext": rendered,
        }
    }
    print(json.dumps(payload))
