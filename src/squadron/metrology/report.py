"""Aggregation core for metrology reporting — surface-agnostic, no Typer.

Reads 320's ``MetrologyStore`` and the persisted 300 review files it
references; never writes either. ``enrich_samples`` is the one join pass
agreement/dispersion/trend all consume: it derives each sample's
``ArtifactLevel``, re-reads and content-verifies the referenced judge
result, and resolves the artifact's ``source_document`` — the initial
frontmatter read serves both the agreement join and the dispersion group
key, plus one further re-read to recompute the content hash for
change detection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from squadron.config.manager import get_config, get_typed_config
from squadron.metrology.errors import MetrologyTargetError
from squadron.metrology.identity import (
    SOURCE_DOC_KEY,
    VERDICT_KEY,
    derive_result_ref,
    read_review_frontmatter,
)
from squadron.metrology.levels import ArtifactLevel, derive_artifact_level
from squadron.metrology.models import JudgeConfigId, ProjectId, SampleVerdict
from squadron.metrology.report_models import (
    AgreementCell,
    AgreementReport,
    ArtifactKey,
    DispersionCell,
    DispersionReport,
    ExclusionSummary,
    GroupKey,
    TrendBucket,
    TrendReport,
)
from squadron.review.models import Verdict

_logger = logging.getLogger(__name__)


@dataclass
class EnrichedSample:
    """One sample joined to its judge verdict and classified for grouping.

    ``admissible`` is the join outcome: a sample whose referenced review
    file is missing, changed since capture, or unparseable is
    ``"stale-judge-result"`` and carries ``judge_verdict=None`` — it is never
    joined to the wrong verdict.
    """

    sample: SampleVerdict
    artifact_level: ArtifactLevel
    judge_verdict: Verdict | None
    source_document: str | None
    admissible: Literal["admissible", "stale-judge-result"]
    unversioned: bool


def _parse_judge_verdict(frontmatter: dict[str, object]) -> Verdict | None:
    raw = frontmatter.get(VERDICT_KEY)
    if not isinstance(raw, str):
        return None
    try:
        return Verdict(raw.strip().upper())
    except ValueError:
        return None


def _resolve_review_path(relative_path: str, cwd: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute():
        return candidate
    return Path(cwd) / candidate


def _enrich_one(sample: SampleVerdict, cwd: str) -> EnrichedSample:
    # The sample carries no review-type field itself; the artifact level is
    # only known once the referenced review file's frontmatter is read below.
    unversioned = sample.judge_config.template_content_hash is None
    review_path = _resolve_review_path(sample.result_ref.relative_review_path, cwd)

    try:
        frontmatter = read_review_frontmatter(review_path)
    except MetrologyTargetError as exc:
        _logger.warning(
            "Excluding sample %s from agreement: review file unreadable (%s)",
            sample.sample_id,
            exc,
        )
        return EnrichedSample(
            sample=sample,
            artifact_level=ArtifactLevel.UNCLASSIFIED,
            judge_verdict=None,
            source_document=None,
            admissible="stale-judge-result",
            unversioned=unversioned,
        )

    review_type_raw = frontmatter.get("reviewType")
    review_type = review_type_raw if isinstance(review_type_raw, str) else ""
    level = derive_artifact_level(review_type)

    source_document_raw = frontmatter.get(SOURCE_DOC_KEY)
    source_document = source_document_raw if isinstance(source_document_raw, str) else None
    if source_document is None:
        _logger.warning(
            "Sample %s: review file %s has no sourceDocument — excluded from dispersion",
            sample.sample_id,
            review_path,
        )

    try:
        current_ref = derive_result_ref(
            review_path,
            ProjectId(value=sample.result_ref.project_id, source=sample.project_id.source),
            cwd=cwd,
        )
    except MetrologyTargetError as exc:
        _logger.warning(
            "Excluding sample %s from agreement: review file %s no longer hashable (%s)",
            sample.sample_id,
            review_path,
            exc,
        )
        return EnrichedSample(
            sample=sample,
            artifact_level=level,
            judge_verdict=None,
            source_document=source_document,
            admissible="stale-judge-result",
            unversioned=unversioned,
        )

    if current_ref.content_hash != sample.result_ref.content_hash:
        _logger.warning(
            "Excluding sample %s from agreement: review file %s changed since capture "
            "(content_hash mismatch)",
            sample.sample_id,
            review_path,
        )
        return EnrichedSample(
            sample=sample,
            artifact_level=level,
            judge_verdict=None,
            source_document=source_document,
            admissible="stale-judge-result",
            unversioned=unversioned,
        )

    judge_verdict = _parse_judge_verdict(frontmatter)
    if judge_verdict is None:
        _logger.warning(
            "Excluding sample %s from agreement: review file %s has no parseable verdict",
            sample.sample_id,
            review_path,
        )
        return EnrichedSample(
            sample=sample,
            artifact_level=level,
            judge_verdict=None,
            source_document=source_document,
            admissible="stale-judge-result",
            unversioned=unversioned,
        )

    return EnrichedSample(
        sample=sample,
        artifact_level=level,
        judge_verdict=judge_verdict,
        source_document=source_document,
        admissible="admissible",
        unversioned=unversioned,
    )


def enrich_samples(samples: list[SampleVerdict], cwd: str) -> list[EnrichedSample]:
    """Join each sample to its judge verdict and classify it for grouping.

    Per sample: one frontmatter read yields both the judge verdict
    (agreement) and the resolved ``source_document`` (dispersion key),
    plus a second read inside ``derive_result_ref`` to recompute the
    content hash from a fresh read — required to detect a file changed
    since capture, not avoidable I/O.
    """
    return [_enrich_one(sample, cwd) for sample in samples]


def _min_evidence_n(cwd: str) -> int:
    try:
        value = get_typed_config("metrology.min_evidence_n", int, cwd=cwd)
    except ValueError as exc:
        raise MetrologyTargetError(
            f"{exc}. Fix it with 'sq config set metrology.min_evidence_n <n>'."
        ) from exc
    assert isinstance(value, int)
    return value


def _comparability_key(judge_config: JudgeConfigId) -> tuple[str, str, str | None]:
    """The grouping key for comparability: distinct configs are distinct
    groups; unversioned records group by (name, model) only, so they never
    silently pool with a hash-bearing same-name record (segregated via
    ``unversioned``, not merged into it)."""
    return (judge_config.template_name, judge_config.model, judge_config.template_content_hash)


def agreement_report(samples: list[SampleVerdict], cwd: str) -> AgreementReport:
    """Judge-vs-human match rate, grouped by ``(ArtifactLevel, JudgeConfigId)``.

    Excludes ``stale-judge-result`` samples from the match computation
    (counted in ``ExclusionSummary``). Unversioned records are grouped
    separately from hash-bearing same-name+model records — never pooled.
    """
    enriched = enrich_samples(samples, cwd)
    floor = _min_evidence_n(cwd)

    stale_count = sum(1 for item in enriched if item.admissible == "stale-judge-result")
    unversioned_count = sum(
        1 for item in enriched if item.admissible == "admissible" and item.unversioned
    )

    groups: dict[tuple[ArtifactLevel, tuple[str, str, str | None]], list[EnrichedSample]] = {}
    for item in enriched:
        if item.admissible != "admissible":
            continue
        key = (item.artifact_level, _comparability_key(item.sample.judge_config))
        groups.setdefault(key, []).append(item)

    cells: list[AgreementCell] = []
    for (level, _comparability), members in groups.items():
        n = len(members)
        matches = sum(1 for item in members if item.sample.human_verdict == item.judge_verdict)
        match_rate = matches / n if n > 0 else 0.0
        cells.append(
            AgreementCell(
                group=GroupKey(artifact_level=level, judge_config=members[0].sample.judge_config),
                n=n,
                match_rate=match_rate,
                below_floor=n < floor,
            )
        )

    return AgreementReport(
        cells=cells,
        excluded=ExclusionSummary(
            total_excluded=stale_count + unversioned_count,
            stale_judge_result=stale_count,
            unversioned=unversioned_count,
        ),
    )


def dispersion_report(samples: list[SampleVerdict], cwd: str) -> DispersionReport:
    """Judge-vs-judge disagreement on the same artifact across distinct
    judge configurations, grouped by **artifact identity**
    ``(project_id, source_document, ArtifactLevel)`` — not by ``result_ref``,
    which differs per config and would make cross-config dispersion
    impossible (slice-review F001).

    A sample with no resolvable ``source_document`` is excluded from
    dispersion (no stable artifact identity) but still counts for agreement.
    Only artifacts graded by >=2 distinct ``JudgeConfigId``s produce a cell —
    this is the cross-config dispersion the slice ships. The same-config
    repeated-measurement path (multiple judgments under one identical
    ``JudgeConfigId``) is structurally supported by this same grouping but
    stays dormant until 300 FW#1 persists repeated same-config results.
    """
    enriched = enrich_samples(samples, cwd)

    stale_count = sum(1 for item in enriched if item.admissible == "stale-judge-result")
    unversioned_count = sum(
        1 for item in enriched if item.admissible == "admissible" and item.unversioned
    )
    missing_source_document_count = sum(
        1 for item in enriched if item.admissible == "admissible" and item.source_document is None
    )

    groups: dict[tuple[str, str, ArtifactLevel], list[EnrichedSample]] = {}
    for item in enriched:
        if item.admissible != "admissible" or item.source_document is None:
            continue
        key = (item.sample.project_id.value, item.source_document, item.artifact_level)
        groups.setdefault(key, []).append(item)

    cells: list[DispersionCell] = []
    for (project_id, source_document, level), members in groups.items():
        distinct_configs = list(
            {_comparability_key(item.sample.judge_config): item for item in members}.values()
        )
        if len(distinct_configs) < 2:
            continue

        pairs = 0
        disagreements = 0
        for i in range(len(distinct_configs)):
            for j in range(i + 1, len(distinct_configs)):
                pairs += 1
                if distinct_configs[i].judge_verdict != distinct_configs[j].judge_verdict:
                    disagreements += 1
        disagreement_rate = disagreements / pairs if pairs > 0 else 0.0

        cells.append(
            DispersionCell(
                artifact=ArtifactKey(
                    project_id=project_id,
                    source_document=source_document,
                    artifact_level=level,
                ),
                judge_configs=[item.sample.judge_config for item in distinct_configs],
                n=len(distinct_configs),
                disagreement_rate=disagreement_rate,
            )
        )

    return DispersionReport(
        cells=cells,
        excluded=ExclusionSummary(
            total_excluded=stale_count + unversioned_count + missing_source_document_count,
            stale_judge_result=stale_count,
            unversioned=unversioned_count,
            missing_source_document=missing_source_document_count,
        ),
    )


def _default_trend_bucket(cwd: str) -> str:
    value = get_config("metrology.trend_bucket", cwd=cwd)
    if not isinstance(value, str) or not value.strip():
        raise MetrologyTargetError(
            f"metrology.trend_bucket must be a non-empty string, got {value!r}. "
            "Fix it with 'sq config set metrology.trend_bucket <bucket>'."
        )
    return value.strip()


def _bucket_label(captured_at: datetime, bucket: str) -> str:
    """Map a timestamp to its bucket label. ``month`` -> ``YYYY-MM``,
    ``week`` -> ISO ``YYYY-Www``, ``day`` -> ``YYYY-MM-DD``."""
    if bucket == "month":
        return captured_at.strftime("%Y-%m")
    if bucket == "week":
        iso = captured_at.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    if bucket == "day":
        return captured_at.strftime("%Y-%m-%d")
    raise MetrologyTargetError(
        f"Unsupported trend bucket {bucket!r}. Expected one of: day, week, month."
    )


def trend_report(samples: list[SampleVerdict], cwd: str, bucket: str | None = None) -> TrendReport:
    """Agreement/dispersion figures bucketed over time on the same
    per-level/per-config grain as ``agreement_report``/``dispersion_report``
    (reused per bucket, not re-derived). Series is ordered oldest to newest.
    """
    resolved_bucket = bucket if bucket is not None else _default_trend_bucket(cwd)

    buckets: dict[str, list[SampleVerdict]] = {}
    for sample in samples:
        label = _bucket_label(sample.captured_at, resolved_bucket)
        buckets.setdefault(label, []).append(sample)

    series = [
        TrendBucket(
            bucket_label=label,
            agreement=agreement_report(buckets[label], cwd),
            dispersion=dispersion_report(buckets[label], cwd),
        )
        for label in sorted(buckets)
    ]

    return TrendReport(bucket=resolved_bucket, series=series)
