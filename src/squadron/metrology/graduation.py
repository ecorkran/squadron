"""Graduated-config registry: version-scoped graduation records (322).

Surface-agnostic (no Typer imports) — matches 320/321's pattern. A
graduation is a statement about an instrument, not a name: matching is on
the full ``JudgeConfigId`` (including ``template_content_hash``), never the
looser ``(template_name, model)`` pair — see the slice design's
"Graduation is version-scoped" decision.
"""

from __future__ import annotations

import logging

from squadron.metrology.levels import ArtifactLevel
from squadron.metrology.models import GraduatedConfig, JudgeConfigId
from squadron.metrology.store import MetrologyStore

_logger = logging.getLogger(__name__)


def _identity_matches(
    graduated: GraduatedConfig, judge_config: JudgeConfigId, level: ArtifactLevel
) -> bool:
    """Exact match on the full ``JudgeConfigId`` and artifact level.

    Unlike the store's sample-filter matching (which treats an absent
    filter hash as a wildcard), graduation matching always compares
    ``template_content_hash`` — a differing hash with identical
    ``template_name``/``model`` must **not** match, or a graduation earned
    by one prompt would silently transfer to a rewritten one.
    """
    return (
        graduated.judge_config.template_name == judge_config.template_name
        and graduated.judge_config.model == judge_config.model
        and graduated.judge_config.template_content_hash == judge_config.template_content_hash
        and graduated.artifact_level == level
    )


def write_graduation(store: MetrologyStore, graduated: GraduatedConfig) -> str:
    """Persist a graduation, updating an existing exact-identity record in place.

    Idempotent: if a ``GraduatedConfig`` for this exact ``(JudgeConfigId,
    artifact_level)`` already exists, its evidence snapshot is updated
    in-place (one record, not two) — INFO logged rather than WARNING, since
    a re-graduation is a normal operator action, not a problem.
    """
    for record_id, existing in store.list_graduations():
        if _identity_matches(existing, graduated.judge_config, graduated.artifact_level):
            _logger.info(
                "Updating existing graduation for %s at level %s (record %s)",
                graduated.judge_config,
                graduated.artifact_level,
                record_id,
            )
            return store.write_graduation(graduated, record_id=record_id)
    return store.write_graduation(graduated)


def find_graduation(
    store: MetrologyStore, judge_config: JudgeConfigId, level: ArtifactLevel
) -> GraduatedConfig | None:
    """Return the graduation matching this exact ``JudgeConfigId`` and level, if any."""
    for _record_id, graduated in store.list_graduations():
        if _identity_matches(graduated, judge_config, level):
            return graduated
    return None


def list_graduations(store: MetrologyStore) -> list[GraduatedConfig]:
    """Return all persisted graduated-config records."""
    return [graduated for _record_id, graduated in store.list_graduations()]
