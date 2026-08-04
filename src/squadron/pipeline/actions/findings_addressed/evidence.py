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
from datetime import date
from pathlib import Path

from squadron.documents.frontmatter import render_frontmatter_block, yaml_safe
from squadron.documents.schema import GATE_EVIDENCE_DOC_TYPE
from squadron.review.addressed.models import FindingOutcome, SettlingScreen
from squadron.review.persistence import REVIEWS_DIR

_logger = logging.getLogger(__name__)

#: Filename pattern. The ``-gate.`` segment is what keeps it out of the
#: ``*-review.*`` glob; nothing else about the name may reintroduce it.
GATE_EVIDENCE_FILENAME_FORMAT = "{index}-gate.{policy}.{name}-r{revision}.md"

#: Reviews directory, relative to the run's cwd — the same location reviews
#: land in, so a round's evidence assembles in one place. Taken from the
#: persistence module rather than restated, so the two cannot drift.
REVIEWS_SUBDIR = REVIEWS_DIR


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


def gate_evidence_frontmatter(
    evidence: GateEvidence, *, step_name: str, date_created: str
) -> dict[str, object]:
    """The frontmatter mapping, as data — serialized by yaml, never by f-string.

    Notes and locations embed arbitrary model-authored text: a colon-space, a
    leading ``#`` or ``-``, or an embedded newline would corrupt hand-rendered
    frontmatter, and this artifact exists to be machine-readable.

    ``date_created`` is a required keyword rather than a clock call inside
    this function, on the same principle as ``update_frontmatter``'s
    ``today`` keyword — it keeps the renderer testable and free of ambient
    state.
    """
    data: dict[str, object] = {
        "docType": GATE_EVIDENCE_DOC_TYPE,
        "layer": "project",
        "dateCreated": date_created,
        "gateStep": step_name,
        "policy": yaml_safe(evidence.policy),
        "verdict": yaml_safe(evidence.reduced_verdict),
        "addressedVerdict": yaml_safe(evidence.addressed_verdict),
        "reviewVerdict": yaml_safe(evidence.review_verdict),
        "decidingScreen": yaml_safe(evidence.deciding_screen),
        "noPriorRound": evidence.no_prior_round,
        "priorRoundSha": yaml_safe(evidence.prior_round_sha),
        "revision_number": evidence.revision_number,
        "judgeModel": yaml_safe(evidence.judge_model),
        "judgeTemplate": yaml_safe(evidence.judge_template),
    }
    if evidence.outcomes:
        data["findingStatuses"] = [
            {key: yaml_safe(value) for key, value in record.items() if value is not None}
            for record in evidence.finding_records()
        ]
    return data


def render_gate_evidence(evidence: GateEvidence, *, step_name: str, date_created: str) -> str:
    """Render the artifact: frontmatter carrying the whole record, then prose."""
    lines = [
        render_frontmatter_block(
            gate_evidence_frontmatter(evidence, step_name=step_name, date_created=date_created)
        ),
        "",
        f"# Gate Evidence — {step_name} ({evidence.policy})",
        "",
        f"Verdict **{evidence.reduced_verdict}** "
        f"(addressed: {evidence.addressed_verdict}, "
        f"review: {evidence.review_verdict or 'UNKNOWN'}).",
        "",
    ]
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
    today = date.today().strftime("%Y%m%d")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_gate_evidence(evidence, step_name=step_name, date_created=today))
    except OSError:
        _logger.warning("findings-addressed: failed to write gate evidence to %s", path)
        return None
    return path
