"""The gate-evidence artifact — one record per gate decision.

Deliberately outside the ``*-review.*`` namespace. Metrology's
``discover_judge_results`` globs that pattern and keeps anything whose template
is a judge template; a gate decision is decider evidence, not an assessment,
and must be excluded by construction rather than by a filter someone has to
remember to write.

One record object backs both the persisted artifact and the gate's in-process
``ActionResult.metadata`` — the same facts are never assembled twice.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from squadron.pipeline.actions.findings_addressed.models import FindingOutcome, SettlingScreen

_logger = logging.getLogger(__name__)

#: Frontmatter docType — provenance-distinct from a review.
GATE_EVIDENCE_DOC_TYPE = "gate-evidence"

#: Filename pattern. The ``-gate.`` segment is what keeps it out of the
#: ``*-review.*`` glob; nothing else about the name may reintroduce it.
GATE_EVIDENCE_FILENAME_FORMAT = "{index}-gate.{policy}.{name}-r{revision}.md"

#: Reviews directory, relative to the run's cwd — the same location reviews
#: land in, so a round's evidence assembles in one place.
REVIEWS_SUBDIR = Path("project-documents/user/reviews")


@dataclass(frozen=True)
class GateEvidence:
    """Everything one gate decision recorded, in one object."""

    policy: str
    reduced_verdict: str
    addressed_verdict: str
    review_verdict: str | None
    outcomes: list[FindingOutcome] = field(default_factory=list[FindingOutcome])
    deciding_screen: SettlingScreen | None = None
    #: The prior round's commit — HEAD at gate time. Round N's own SHA is not
    #: recordable: this artifact is written before the commit that contains it,
    #: so it cannot carry that commit's identity. Round N's commit is
    #: discoverable from git afterwards as the commit containing this file.
    prior_round_sha: str | None = None
    revision_number: int | None = None
    judge_model: str | None = None
    judge_template: str | None = None

    @property
    def no_prior_round(self) -> bool:
        return self.deciding_screen == SettlingScreen.NO_PRIOR_ROUND

    def finding_records(self) -> list[dict[str, object]]:
        """Per-finding outcomes as plain data, for metadata and frontmatter."""
        return [
            {
                "id": outcome.finding_id,
                "status": outcome.status.value,
                "screen": outcome.screen.value,
                "successor": outcome.successor_id,
                "note": outcome.note,
            }
            for outcome in self.outcomes
        ]

    def to_metadata(self) -> dict[str, object]:
        """The in-process record carried on ``ActionResult.metadata``."""
        return {
            "policy": self.policy,
            "addressed_verdict": self.addressed_verdict,
            "review_verdict": self.review_verdict,
            "no_prior_round": self.no_prior_round,
            "deciding_screen": (
                self.deciding_screen.value if self.deciding_screen is not None else None
            ),
            "finding_statuses": self.finding_records(),
            "prior_round_sha": self.prior_round_sha,
            "revision_number": self.revision_number,
            "judge_model": self.judge_model,
            "judge_template": self.judge_template,
        }


def _yaml_scalar(value: object) -> str:
    """Render a scalar for frontmatter; None becomes an explicit null."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def render_gate_evidence(evidence: GateEvidence, *, step_name: str) -> str:
    """Render the artifact: frontmatter carrying the whole record, then prose."""
    lines = [
        "---",
        f"docType: {GATE_EVIDENCE_DOC_TYPE}",
        "layer: project",
        f"gateStep: {step_name}",
        f"policy: {evidence.policy}",
        f"verdict: {evidence.reduced_verdict}",
        f"addressedVerdict: {evidence.addressed_verdict}",
        f"reviewVerdict: {_yaml_scalar(evidence.review_verdict)}",
        f"decidingScreen: {_yaml_scalar(evidence.deciding_screen)}",
        f"noPriorRound: {_yaml_scalar(evidence.no_prior_round)}",
        f"priorRoundSha: {_yaml_scalar(evidence.prior_round_sha)}",
        f"revision_number: {_yaml_scalar(evidence.revision_number)}",
        f"judgeModel: {_yaml_scalar(evidence.judge_model)}",
        f"judgeTemplate: {_yaml_scalar(evidence.judge_template)}",
    ]
    if evidence.outcomes:
        lines.append("findingStatuses:")
        for record in evidence.finding_records():
            lines.append(f"  - id: {record['id']}")
            lines.append(f"    status: {record['status']}")
            lines.append(f"    screen: {record['screen']}")
            if record["successor"] is not None:
                lines.append(f"    successor: {record['successor']}")
            if record["note"] is not None:
                lines.append(f"    note: {record['note']}")
    lines.extend(
        [
            "---",
            "",
            f"# Gate Evidence — {step_name} ({evidence.policy})",
            "",
            f"Verdict **{evidence.reduced_verdict}** "
            f"(addressed: {evidence.addressed_verdict}, "
            f"review: {evidence.review_verdict or 'UNKNOWN'}).",
            "",
        ]
    )
    if evidence.outcomes:
        lines.append("## Prior findings")
        lines.append("")
        for outcome in evidence.outcomes:
            note = f" — {outcome.note}" if outcome.note else ""
            successor = f" (successor: {outcome.successor_id})" if outcome.successor_id else ""
            lines.append(
                f"- `{outcome.finding_id}`: **{outcome.status.value}** "
                f"[{outcome.screen.value}]{successor}{note}"
            )
        lines.append("")
    else:
        lines.append("No prior findings were in scope for this decision.")
        lines.append("")
    return "\n".join(lines)


def save_gate_evidence(
    evidence: GateEvidence,
    *,
    step_name: str,
    slice_index: object,
    cwd: str,
) -> Path | None:
    """Write the artifact, returning its path, or None if it could not be written.

    Written before the iteration's commit — the gate already runs ahead of
    ``commit_each_iteration``, which appends its commit after all inner steps,
    so the artifact enters the round's own commit with no ordering change here.

    Persistence failure is non-fatal and logged at WARNING, mirroring the
    review action: the gate's verdict does not depend on the file existing.
    """
    if slice_index is None:
        _logger.warning(
            "findings-addressed: no slice index available; gate evidence for step '%s' not written",
            step_name,
        )
        return None

    filename = GATE_EVIDENCE_FILENAME_FORMAT.format(
        index=slice_index,
        policy=evidence.policy,
        name=step_name,
        # 0 means "not inside a loop" — the same sentinel ActionContext.iteration uses.
        revision=evidence.revision_number if evidence.revision_number is not None else 0,
    )
    path = Path(cwd) / REVIEWS_SUBDIR / filename
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_gate_evidence(evidence, step_name=step_name))
    except OSError:
        _logger.warning("findings-addressed: failed to write gate evidence to %s", path)
        return None
    return path
