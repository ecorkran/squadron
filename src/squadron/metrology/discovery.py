"""Judge-result discovery: enumerate persisted judge review files (322).

320 has no whole-project "enumerate all judge results" surface —
``capture.resolve_target`` only resolves one target given an already-known
slice index. Residual sampling (T14) needs to diff against everything
already sampled, so this module builds that enumeration as a pure surface:
it returns file paths only, never derives a ``JudgeConfigId`` (that is
``select_residual_offers``' job).
"""

from __future__ import annotations

import logging
from pathlib import Path

from squadron.metrology.capture import REVIEWS_SUBDIR
from squadron.metrology.errors import MetrologyTargetError
from squadron.metrology.identity import read_review_frontmatter

_logger = logging.getLogger(__name__)

#: Frontmatter key naming a persisted review's type, used to resolve the
#: template and check whether it is a judge template (has a `judge:` block).
_FM_REVIEW_TYPE = "reviewType"


def discover_judge_results(cwd: str) -> list[Path]:
    """Return all persisted judge review files under the project's reviews dir.

    Enumerates every review file (not just one index's candidates), keeping
    only those whose ``reviewType`` resolves to a registered judge template
    (``ReviewTemplate.is_judge``). Non-judge reviews (arch/tasks/code reviews
    with no judge template) are skipped without erroring. Malformed or
    unreadable frontmatter is skipped with a WARNING naming the path — one
    bad review file must not sink the whole discovery pass.
    """
    # Imported lazily: the review.templates package pulls in the review
    # subsystem, which the metrology core otherwise does not need.
    from squadron.review.templates import get_template

    reviews_dir = Path(cwd) / REVIEWS_SUBDIR
    if not reviews_dir.is_dir():
        return []

    results: list[Path] = []
    for candidate in sorted(reviews_dir.glob("*-review.*")):
        try:
            frontmatter = read_review_frontmatter(candidate)
        except MetrologyTargetError:
            _logger.warning("Skipping unreadable review file during discovery: %s", candidate)
            continue

        raw_type = frontmatter.get(_FM_REVIEW_TYPE)
        if not isinstance(raw_type, str) or not raw_type:
            _logger.warning("Skipping review file with no reviewType during discovery: %s", candidate)
            continue

        template = get_template(raw_type)
        if template is None or not template.is_judge:
            continue

        results.append(candidate)

    return results
