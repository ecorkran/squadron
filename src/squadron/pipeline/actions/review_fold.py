"""Fold a split review's per-part results into the one result a step reports.

A single part is returned unchanged, so a one-file review looks exactly as it
did before split reviews existed. For two or more parts the verdict is the
worst part's, so a loop's ``until``/``skip_if_met`` check cannot pass while any
part falls short.
"""

from __future__ import annotations

from typing import cast

from squadron.pipeline.actions.review_outputs import (
    FINDING_INPUT_FILE,
    ReviewOutputKey,
    review_file,
    review_input_files,
    review_response,
)
from squadron.pipeline.models import ActionResult
from squadron.review.parts import worst_verdict

_TOOL_CALLS_MADE = "tool_calls_made"


def fold_review_parts(parts: list[ActionResult]) -> ActionResult:
    """One ``ActionResult`` for all ``parts``, in part order.

    Raises:
        ValueError: If ``parts`` is empty.
        TypeError: If a part lacks a verdict or does not name exactly one input
            file — both are always set by the review action.
    """
    if not parts:
        raise ValueError("fold_review_parts: no parts to fold")
    if len(parts) == 1:
        return parts[0]

    paths = [_part_input(part) for part in parts]
    verdicts = [_part_verdict(part) for part in parts]
    verdict = worst_verdict(verdicts)
    # The first part holding the worst value, since ties go to the first part.
    worst = verdicts.index(verdict)
    # Chosen independently of the verdict: a judge part degraded to UNKNOWN
    # still leaves the lowest real score visible. min() keeps the first on ties.
    scored = [part for part in parts if part.score is not None]
    lowest = min(scored, key=lambda part: part.score or 0.0) if scored else None

    return ActionResult(
        success=True,
        action_type=parts[0].action_type,
        outputs=_outputs(parts, paths, worst),
        verdict=verdict,
        findings=[
            _tag_finding(finding, path)
            for part, path in zip(parts, paths, strict=True)
            for finding in part.findings
        ],
        score=lowest.score if lowest is not None else None,
        criteria=lowest.criteria if lowest is not None else None,
        provenance=parts[0].provenance,
        metadata=_metadata(parts),
    )


def _outputs(parts: list[ActionResult], paths: list[str], worst: int) -> dict[str, object]:
    review_files = [review_file(part) for part in parts]
    outputs: dict[str, object] = {
        ReviewOutputKey.RESPONSE: "\n\n".join(
            f"## {path}\n\n{review_response(part)}" for part, path in zip(parts, paths, strict=True)
        ),
        ReviewOutputKey.INPUT_FILES: paths,
        ReviewOutputKey.REVIEW_FILES: [path for path in review_files if path is not None],
        # The file that sank the item, so the batch report points at it.
        ReviewOutputKey.INPUT_FILE: paths[worst],
    }
    worst_review_file = review_files[worst]
    if worst_review_file is not None:
        outputs[ReviewOutputKey.REVIEW_FILE] = worst_review_file
    unsaved = [path for path, saved in zip(paths, review_files, strict=True) if saved is None]
    if unsaved:
        outputs[ReviewOutputKey.UNSAVED_PARTS] = unsaved
    return outputs


def _metadata(parts: list[ActionResult]) -> dict[str, object]:
    """First part's metadata (every part shares model and profile), tool calls summed."""
    metadata = dict(parts[0].metadata)
    if _TOOL_CALLS_MADE in metadata:
        counts = [part.metadata.get(_TOOL_CALLS_MADE, 0) for part in parts]
        metadata[_TOOL_CALLS_MADE] = sum(count for count in counts if isinstance(count, int))
    return metadata


def _tag_finding(finding: object, path: str) -> dict[str, object]:
    """A copy of ``finding`` naming the part file it came from."""
    if not isinstance(finding, dict):
        raise TypeError(f"review finding must be a dict, got {type(finding).__name__}")
    # Findings are StructuredFinding.__dict__ copies: str keys by construction.
    return {**cast(dict[str, object], finding), FINDING_INPUT_FILE: path}


def _part_input(part: ActionResult) -> str:
    files = review_input_files(part)
    if len(files) != 1:
        raise TypeError(f"review part must name exactly one input file, got {files}")
    return files[0]


def _part_verdict(part: ActionResult) -> str:
    if part.verdict is None:
        raise TypeError("review part has no verdict")
    return part.verdict
