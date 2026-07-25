"""Graduated-config registry: version-scoped graduation records (322).

Surface-agnostic (no Typer imports) — matches 320/321's pattern. A
graduation is a statement about an instrument, not a name: matching is on
the full ``JudgeConfigId`` (including ``template_content_hash``), never the
looser ``(template_name, model)`` pair — see the slice design's
"Graduation is version-scoped" decision.
"""

from __future__ import annotations

import logging
from pathlib import Path

from squadron.metrology.calibration_models import OfferTarget
from squadron.metrology.discovery import discover_judge_results
from squadron.metrology.errors import MetrologyTargetError
from squadron.metrology.identity import (
    derive_judge_config_id,
    derive_project_id,
    derive_result_ref,
    read_review_frontmatter,
)
from squadron.metrology.levels import ArtifactLevel, derive_artifact_level
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


def _review_reviewtype(review_file: Path) -> str | None:
    """Return a persisted review's ``reviewType`` frontmatter, or ``None``.

    Malformed/unreadable frontmatter is skipped (WARNING) rather than
    raised — one bad review must not sink the whole selection pass.
    """
    try:
        frontmatter = read_review_frontmatter(review_file)
    except MetrologyTargetError:
        _logger.warning("Skipping unreadable review file during offer selection: %s", review_file)
        return None
    raw_type = frontmatter.get("reviewType")
    return raw_type if isinstance(raw_type, str) and raw_type else None


def select_residual_offers(
    store: MetrologyStore,
    graduated: list[GraduatedConfig],
    *,
    rate: float,
    cwd: str,
) -> list[OfferTarget]:
    """Select a ``rate`` fraction of each graduated config's unsampled results.

    For each persisted judge review discovered by ``discover_judge_results``,
    derives its ``JudgeConfigId`` and artifact level, and matches it against
    every graduated config's exact identity. A matching result is unsampled
    when no stored ``SampleVerdict`` has a ``result_ref`` pointing at it. A
    graduated config whose identity matches **no** current judge result has
    lapsed (its template/model has since changed) and contributes zero
    offers — the same outcome, at this function's level, as an exhausted
    config with no unsampled matches. Callers that need to report the lapse
    explicitly (T16's CLI) re-derive it via ``find_graduation`` against
    current discovered results, per the design's stated allowance.
    """
    project_id = derive_project_id(cwd)
    sampled_refs = {
        (sample.result_ref.relative_review_path, sample.result_ref.content_hash)
        for sample in store.list_samples()
    }

    offers_by_config: dict[int, list[OfferTarget]] = {id(config): [] for config in graduated}
    for review_file in discover_judge_results(cwd):
        review_type = _review_reviewtype(review_file)
        if review_type is None:
            continue

        try:
            judge_config = derive_judge_config_id(review_file)
            result_ref = derive_result_ref(review_file, project_id, cwd=cwd)
        except MetrologyTargetError:
            _logger.warning("Skipping unreadable judge result during offer selection: %s", review_file)
            continue

        level = derive_artifact_level(review_type)
        already_sampled = (result_ref.relative_review_path, result_ref.content_hash) in sampled_refs
        if already_sampled:
            continue

        for config in graduated:
            if _identity_matches(config, judge_config, level):
                offers_by_config[id(config)].append(
                    OfferTarget(
                        review_path=result_ref.relative_review_path,
                        judge_config=judge_config,
                        reason="residual-sampling",
                    )
                )

    selected: list[OfferTarget] = []
    for config in graduated:
        unsampled_matches = offers_by_config[id(config)]
        take = round(len(unsampled_matches) * rate)
        selected.extend(unsampled_matches[:take])
    return selected
