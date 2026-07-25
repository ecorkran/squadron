"""Blind, non-blocking, budgeted human-sample capture core.

Surface-agnostic orchestration (no Typer imports): the CLI is a thin shell
over this, and a future MCP tool wraps the same functions. Blindness is a
data-layer property — ``build_capture_payload`` loads only the artifact and
its ground truth and never the judge's score/verdict/findings, so a test can
assert on the payload object that judge output is absent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from squadron.metrology.errors import MetrologyTargetError
from squadron.metrology.identity import (
    CRITERIA_KEY,
    FINDINGS_KEY,
    SCORE_KEY,
    SOURCE_DOC_KEY,
    VERDICT_KEY,
    derive_judge_config_id,
    derive_project_id,
    derive_result_ref,
    read_review_frontmatter,
)
from squadron.metrology.models import SampleVerdict
from squadron.metrology.store import MetrologyStore, generate_sample_id
from squadron.review.models import Verdict

_logger = logging.getLogger(__name__)

#: Where review/persistence.py writes results, relative to the project root.
#: Filenames are ``{index}-review.{type}.{slice}.{ext}``. Public so other
#: metrology modules (e.g. ``discovery.py``) reference the same definition
#: rather than duplicating the literal.
REVIEWS_SUBDIR = Path("project-documents/user/reviews")


@dataclass(frozen=True)
class CapturePayload:
    """What the capture surface is allowed to show before the human commits.

    Deliberately holds the artifact and its ground truth only. The judge's
    score/verdict/findings are absent by construction — this is the
    load-bearing blindness property, assertable by a test on this object.
    """

    review_file: Path
    artifact_path: str | None
    ground_truth_text: str | None


@dataclass(frozen=True)
class CaptureOutcome:
    """Result of a ``record_sample`` attempt.

    ``sample_id`` is set when a record was written; ``budget_reached`` is True
    when the write was refused because the project's write-ceiling was hit
    (a normal outcome the surface reports and exits cleanly on, not an error).
    """

    sample_id: str | None
    budget_reached: bool
    budget_limit: int | None = None


def resolve_target(
    target: str,
    review_type: str | None,
    cwd: str,
) -> Path:
    """Resolve a target to exactly one persisted review file.

    ``target`` is either a path to a review file, or a bare slice index
    combined with ``review_type``. Zero matches → ``MetrologyTargetError``;
    multiple candidate types for a bare index → ``MetrologyTargetError``
    listing the candidates so the caller can disambiguate with ``--type``.
    """
    as_path = Path(target)
    if as_path.suffix and (as_path.is_file() or as_path.is_absolute() or "/" in target):
        # Looks like a path (has an extension and a path-ish shape).
        if not as_path.is_file():
            raise MetrologyTargetError(f"Review file not found: {as_path}")
        return as_path

    if not target.isdigit():
        raise MetrologyTargetError(
            f"Target {target!r} is neither an existing review file nor a slice "
            "index. Pass a review-file path, or an index with --type."
        )

    reviews_dir = Path(cwd) / REVIEWS_SUBDIR
    index = target
    candidates = sorted(reviews_dir.glob(f"{index}-review.*"))
    if not candidates:
        raise MetrologyTargetError(
            f"No review result for index {index} under {reviews_dir}. "
            "Produce one (e.g. 'sq review slice <n>') first."
        )

    # The authoritative review type is the file's ``reviewType`` frontmatter,
    # not a filename segment — a type like ``judge.slice-vs-arch`` contains
    # dots, so parsing it out of ``{index}-review.{type}.{slice}.{ext}`` by
    # splitting on '.' is unreliable. Read each candidate's frontmatter.
    by_type = _candidates_by_type(candidates)

    if review_type is not None:
        typed = by_type.get(review_type, [])
        if not typed:
            available = sorted(by_type)
            raise MetrologyTargetError(
                f"No review of type {review_type!r} for index {index}. "
                f"Available: {', '.join(available) or '(none)'}."
            )
        if len(typed) > 1:
            raise MetrologyTargetError(
                f"Multiple review files match index {index} type {review_type!r}: "
                f"{', '.join(c.name for c in typed)}."
            )
        return typed[0]

    # No explicit type: only unambiguous when exactly one candidate exists.
    if len(candidates) == 1:
        return candidates[0]
    available = sorted(by_type)
    raise MetrologyTargetError(
        f"Index {index} is ambiguous — multiple review types exist: "
        f"{', '.join(available)}. Re-run with --type <one-of-these>."
    )


def _candidates_by_type(candidates: list[Path]) -> dict[str, list[Path]]:
    """Group candidate review files by their ``reviewType`` frontmatter.

    A file whose frontmatter can't be read is grouped under its filename's
    first post-``-review.`` segment as a lenient fallback, so a malformed
    sibling still surfaces as a distinct candidate rather than vanishing.
    """
    grouped: dict[str, list[Path]] = {}
    for candidate in candidates:
        review_type = _read_review_type(candidate)
        grouped.setdefault(review_type, []).append(candidate)
    return grouped


def _read_review_type(candidate: Path) -> str:
    """Return a candidate's ``reviewType``, or a filename-derived fallback."""
    try:
        frontmatter = read_review_frontmatter(candidate)
    except MetrologyTargetError:
        frontmatter = {}
    raw_type = frontmatter.get("reviewType")
    if isinstance(raw_type, str) and raw_type:
        return raw_type
    # Fallback: first segment after "{index}-review." in the filename.
    name = candidate.name
    marker = "-review."
    if marker in name:
        return name.split(marker, 1)[1].split(".", 1)[0]
    return name


def build_capture_payload(review_file: Path, cwd: str) -> CapturePayload:
    """Load artifact + ground truth for the target — never judge output.

    Reads the graded artifact path from the review's ``sourceDocument`` and
    loads that document's text as the ground truth. The judge's
    score/verdict/findings are intentionally not read into the payload.
    """
    frontmatter = read_review_frontmatter(review_file)
    raw_source = frontmatter.get(SOURCE_DOC_KEY)
    artifact_path = str(raw_source) if isinstance(raw_source, str) and raw_source else None

    ground_truth_text: str | None = None
    if artifact_path:
        source_file = Path(cwd) / artifact_path
        if source_file.is_file():
            ground_truth_text = source_file.read_text(encoding="utf-8")
        else:
            _logger.warning("Ground-truth source not found for %s: %s", review_file, source_file)

    return CapturePayload(
        review_file=review_file,
        artifact_path=artifact_path,
        ground_truth_text=ground_truth_text,
    )


def record_sample(
    payload: CapturePayload,
    human_verdict: Verdict,
    note: str | None,
    *,
    store: MetrologyStore,
    cwd: str,
    sample_budget: int,
    artifact_level: str | None = None,
    blind: bool = True,
) -> CaptureOutcome:
    """Persist a blind human verdict against the payload's judge result.

    Derives project identity, the content-addressed result ref, and the
    judge-config id, then writes a ``SampleVerdict``. Before writing, enforces
    the per-project write ceiling: if the project already has
    ``sample_budget`` captures, the write is refused cleanly (no record, no
    error) and a budget-reached outcome is returned.

    This slice enforces the budget as a ceiling on *captures written*, not on
    *offering* — the offer/selection policy is deferred to 321, and there is
    no offer queue here to gate. The store sees every write, so the
    write-ceiling is the enforceable slice of the design's budget criterion.
    """
    project_id = derive_project_id(cwd)

    prior = store.count_samples(project_id.value)
    if prior >= sample_budget:
        _logger.info(
            "Sample budget reached for %s (%d/%d) — nothing written",
            project_id.value,
            prior,
            sample_budget,
        )
        return CaptureOutcome(sample_id=None, budget_reached=True, budget_limit=sample_budget)

    result_ref = derive_result_ref(payload.review_file, project_id, cwd=cwd)
    judge_config = derive_judge_config_id(payload.review_file)

    sample = SampleVerdict(
        sample_id=generate_sample_id(),
        project_id=project_id,
        result_ref=result_ref,
        judge_config=judge_config,
        human_verdict=human_verdict,
        human_note=note,
        artifact_level=artifact_level,
        captured_at=datetime.now(UTC),
        blind=blind,
    )
    sample_id = store.write_sample(sample)
    return CaptureOutcome(sample_id=sample_id, budget_reached=False)


def reveal(review_file: Path) -> dict[str, object]:
    """Return the judge's output for optional POST-COMMIT display only.

    Never call this before ``record_sample`` — it is the anchoring material
    blindness withholds. Returns the judge fields from the persisted review.
    """
    frontmatter = read_review_frontmatter(review_file)
    return {
        "verdict": frontmatter.get(VERDICT_KEY),
        "score": frontmatter.get(SCORE_KEY),
        "criteria": frontmatter.get(CRITERIA_KEY),
        "findings": frontmatter.get(FINDINGS_KEY),
    }
