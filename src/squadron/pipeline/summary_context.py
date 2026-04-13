"""Assemble prior pipeline step results into a context block for non-SDK summary models.

This module is a pure-function module with no I/O, no provider calls, and no side
effects. ``assemble_dispatch_context`` is safe to call from any async context and
trivially testable without mocking providers or sessions.

The assembled context block is prepended to the instructions sent to non-SDK summary
models (which have no session history). The SDK path in ``_execute_summary`` is
unaffected.
"""

from __future__ import annotations

from squadron.pipeline.actions import ActionType
from squadron.pipeline.models import ActionResult

__all__ = ["assemble_dispatch_context"]

_HEADER = "--- Pipeline Context (for summarization) ---"
_FOOTER = "--- End Pipeline Context ---"

# Action types that carry no summarizable content.
_SKIP_TYPES: frozenset[str] = frozenset(
    {
        ActionType.CHECKPOINT,
        ActionType.COMMIT,
    }
)


def assemble_dispatch_context(
    prior_outputs: dict[str, ActionResult],
) -> str:
    """Assemble prior pipeline step results into a context block.

    Iterates ``prior_outputs`` in insertion order (which matches execution order).
    Steps whose ``action_type`` is in ``_SKIP_TYPES``, or whose extracted content is
    empty, are silently omitted.

    Returns an empty string when no prior steps produced meaningful content, so the
    caller can unconditionally check and prepend without special-casing.

    Args:
        prior_outputs: Accumulated step results from the current pipeline run, keyed
            by step name in execution order.

    Returns:
        A delimited plain-text context block, or ``""`` if no content was extracted.
    """
    sections: list[str] = []

    for step_name, result in prior_outputs.items():
        if result.action_type in _SKIP_TYPES:
            continue

        content = _extract_content(result)
        if not content:
            continue

        header = f"## Step: {step_name} ({result.action_type})"
        sections.append(f"{header}\n{content}")

    if not sections:
        return ""

    body = "\n\n".join(sections)
    return f"{_HEADER}\n\n{body}\n\n{_FOOTER}"


def _extract_content(result: ActionResult) -> str:
    """Extract summarizable content from an ActionResult.

    Returns a failure note when ``result.success`` is False.
    Returns ``""`` for action types with no summarizable output key.
    """
    if not result.success:
        return f"[Step failed: {result.error}]"

    match result.action_type:
        case ActionType.DISPATCH:
            return str(result.outputs.get("response", ""))
        case ActionType.REVIEW:
            return _format_review(result)
        case ActionType.CF_OP:
            # Only include build_context operations; other cf-op operations
            # (set_phase, set_slice, etc.) produce no summarizable output.
            if result.outputs.get("operation") == "build_context":
                return str(result.outputs.get("stdout", ""))
            return ""
        case ActionType.SUMMARY:
            # Covers both summary and compact steps: the compact step expands to a
            # summary action, so both appear with action_type "summary".
            return str(result.outputs.get("summary", ""))
        case _:
            return ""


def _format_review(result: ActionResult) -> str:
    """Format review verdict and findings into human-readable text.

    Args:
        result: An ActionResult with ``action_type == ActionType.REVIEW``.

    Returns:
        A newline-joined string with verdict and findings, or ``""`` if neither
        is present.
    """
    parts: list[str] = []
    if result.verdict:
        parts.append(f"Verdict: {result.verdict}")
    if result.findings:
        parts.append("Findings:")
        for finding in result.findings:
            parts.append(f"- {finding}")
    return "\n".join(parts)
