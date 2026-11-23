"""Per-reviewer review call options from a recipe's ``reviewer_options`` (slice 437, D2, D3).

Kept out of ``recipe_runner.py``, which is already over the file-size guideline.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from squadron.project_rules.render import RULES_SEPARATOR
from squadron.recipes.recipe import ReviewerOptions

NO_TOOLS_KEY = "no_tools"
RULES_CONTENT_KEY = "rules_content"


def reviewer_call_options(
    call_options: Mapping[str, Any], options: ReviewerOptions | None
) -> dict[str, Any]:
    """A copy of the step's review call options for one reviewer.

    With no *options* the copy is unchanged. A reviewer with ``tools: false`` sets
    ``no_tools`` (the existing no-tools review, D2); one with ``tools: true`` leaves the
    step's own ``no_tools`` as it was. A reviewer rules file is appended to the
    step's assembled rules after ``RULES_SEPARATOR``, or stands alone when the step has
    none (D3). A reviewer with no rules file keeps the step's rules.
    """
    merged = dict(call_options)
    if options is None:
        return merged
    if options.rules is not None and options.rules_content is None:
        raise ValueError(f"reviewer rules file {options.rules!r} was never read by load_recipe")
    if not options.tools:
        merged[NO_TOOLS_KEY] = True
    if options.rules_content is not None:
        step_rules = call_options.get(RULES_CONTENT_KEY)
        merged[RULES_CONTENT_KEY] = (
            options.rules_content
            if not step_rules
            else f"{step_rules}{RULES_SEPARATOR}{options.rules_content}"
        )
    return merged
