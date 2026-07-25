"""Recommendation core: direction classification and current-threshold read.

Surface-agnostic (no Typer imports) — matches 320/321's pattern. Pure
functions over agreement evidence; nothing here writes to the store, a
template file, or config.
"""

from __future__ import annotations

import logging

from squadron.metrology.calibration_models import RecommendationDirection
from squadron.pipeline.actions.judge import JudgeThresholds, resolve_thresholds

_logger = logging.getLogger(__name__)


def classify_direction(
    match_rate: float,
    n: int,
    floor: int,
    *,
    versioned: bool,
    graduate_rate: float,
    tighten_rate: float,
) -> RecommendationDirection:
    """Classify a calibration cell's advisory direction.

    The floor gates loosening (``GRADUATE``) only. ``TIGHTEN`` is checked
    before the floor test, so a below-floor cell with a low match rate
    reaches ``TIGHTEN`` rather than stopping at ``INSUFFICIENT_EVIDENCE`` —
    a weak judge is worth flagging on thin evidence, while trusting one is
    not. Precedence (literal top-to-bottom; any other ordering makes
    ``TIGHTEN`` unreachable below the floor):

    1. unversioned config -> ``INSUFFICIENT_EVIDENCE`` (never graduate on
       un-keyable evidence, regardless of n or match rate).
    2. ``match_rate <= tighten_rate`` -> ``TIGHTEN`` (not floor-gated).
    3. ``n < floor`` -> ``INSUFFICIENT_EVIDENCE`` (the floor gates only what's
       left: graduating or holding).
    4. ``n >= floor and match_rate >= graduate_rate`` -> ``GRADUATE``.
    5. otherwise -> ``HOLD``.
    """
    if not versioned:
        return RecommendationDirection.INSUFFICIENT_EVIDENCE
    if match_rate <= tighten_rate:
        return RecommendationDirection.TIGHTEN
    if n < floor:
        return RecommendationDirection.INSUFFICIENT_EVIDENCE
    if n >= floor and match_rate >= graduate_rate:
        return RecommendationDirection.GRADUATE
    return RecommendationDirection.HOLD


def read_current_thresholds(template_name: str) -> JudgeThresholds | None:
    """Read the currently configured template-level thresholds.

    Step-level override is not knowable outside a specific step context, so
    this reads the *template's* configured floor via
    ``resolve_thresholds(template.judge, None)`` — what a recommendation is
    a delta from. Returns ``None`` if the template is not registered, or if
    its ``judge:`` block is malformed (e.g. a non-numeric ``pass_floor``);
    never fabricates a threshold.

    ``resolve_thresholds`` itself has no fallback for a malformed value — a
    non-numeric floor raises ``ValueError``/``TypeError`` from its bare
    ``float()`` conversion. That is correct for 300's enforcement path,
    which is not this function's concern; here the malformed block is
    caught and degraded to the same "unresolvable target" signal as an
    unregistered template, so a recommendation report can still render.
    """
    # Imported lazily: the review.templates package pulls in the review
    # subsystem, which the metrology core otherwise does not need.
    from squadron.review.templates import get_template

    template = get_template(template_name)
    if template is None:
        _logger.warning(
            "Cannot read current thresholds: template '%s' is not registered",
            template_name,
        )
        return None
    try:
        return resolve_thresholds(template.judge, None)
    except (ValueError, TypeError):
        _logger.warning(
            "Cannot read current thresholds: template '%s' has a malformed "
            "judge block (non-numeric pass_floor/concerns_floor)",
            template_name,
        )
        return None
