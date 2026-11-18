"""Turn a stage's output file into a ``StageEntry`` (slice 430 D4, D6, D8).

Used right after a call and, on resume, for an orphan output file whose entry was never
stored. An unparseable output is a ``config_failure``; a comb that decides some findings
only is ``ok`` with the rest ``UNDECIDED``. Raw output goes into the ``REVIEWS`` sidecar.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from pydantic import TypeAdapter

from squadron.benchmark.recall.decisions import parse_decisions
from squadron.benchmark.recall.review_output import (
    ReviewOutputError,
    finding_id_at,
    read_effort,
    read_findings,
    read_usage,
)
from squadron.benchmark.recall.run_plan import PendingStage
from squadron.metrology.content_sidecars import ContentSidecars
from squadron.metrology.recall_run_models import (
    LIVE_SOURCE,
    CombDecision,
    CombVerdict,
    RecallFinding,
    RecallLeakVerdict,
    StageEntry,
    StageKind,
    StageOutcome,
    StageUsage,
)
from squadron.pipeline.usage_capture import effort_sent_by_profile

_logger = logging.getLogger(__name__)
_FINDINGS = TypeAdapter(list[RecallFinding])
STDERR_TAIL_CHARS = 500
UNPARSEABLE = "output file holds no parseable result"
NO_DECISION_LINE = "comb output holds no parseable decision line"


@dataclass(frozen=True)
class IngestContext:
    sidecar: ContentSidecars
    case_set: str
    clock: Callable[[], datetime]


def stage_label(stage: PendingStage) -> str:
    """``case <name> run <n> stage <kind> <alias>``: every WARNING names these."""
    return f"case {stage.case.name} run {stage.run_index} stage {stage.kind.value} {stage.alias}"


def failure_entry(
    stage: PendingStage,
    outcome: StageOutcome,
    reason: str,
    context: IngestContext,
    leak: RecallLeakVerdict = RecallLeakVerdict.NOT_SCANNED,
) -> StageEntry:
    """An entry for a call that gave no usable output; logged at WARNING (D8)."""
    _logger.warning("recall %s: %s: %s", stage_label(stage), outcome.value, reason)
    return _entry(stage, context, outcome=outcome, outcome_reason=reason, leak=leak)


def empty_comb_entry(stage: PendingStage, context: IngestContext) -> StageEntry:
    """A comb whose input is empty: nothing to decide, so no call is made."""
    return _entry(stage, context, outcome=StageOutcome.OK, leak=RecallLeakVerdict.CONFINED)


def read_comb_input(path: Path) -> list[RecallFinding]:
    return _FINDINGS.validate_json(path.read_bytes())


def write_comb_input(path: Path, findings: list[RecallFinding]) -> None:
    path.write_bytes(_FINDINGS.dump_json(findings, indent=2))


def ingest_output(
    stage: PendingStage,
    output: Path,
    comb_input: list[RecallFinding] | None,
    leak: RecallLeakVerdict,
    context: IngestContext,
) -> StageEntry:
    """The entry for an output file that exists: parsed, or ``config_failure`` if not."""
    data = output.read_bytes()
    raw_ref = context.sidecar.put(data)
    try:
        document = _document(data)
        call = {"raw_ref": raw_ref, "usage": read_usage(document), "effort_sent": read_effort(document)}
        if stage.kind is StageKind.REVIEW:
            parts: dict[str, Any] | None = {"findings": read_findings(document)}
        else:
            parts = _comb_parts(stage, document, comb_input or [])
    except ReviewOutputError as exc:
        entry = failure_entry(
            stage, StageOutcome.CONFIG_FAILURE, f"{UNPARSEABLE}: {exc}", context, leak
        )
        return entry.model_copy(update={"raw_ref": raw_ref})
    if parts is None:
        entry = failure_entry(stage, StageOutcome.CONFIG_FAILURE, NO_DECISION_LINE, context, leak)
        return entry.model_copy(update=call)
    return _entry(stage, context, outcome=StageOutcome.OK, leak=leak, **call, **parts)


def _document(data: bytes) -> dict[str, Any]:
    try:
        document = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewOutputError(f"not valid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise ReviewOutputError("not a JSON object")
    return cast(dict[str, Any], document)


def _comb_parts(
    stage: PendingStage, document: dict[str, Any], findings: list[RecallFinding]
) -> dict[str, Any] | None:
    """Decisions keyed by finding id; ``None`` when the output holds no decision line."""
    raw = document.get("raw_output")
    if not isinstance(raw, str):
        raise ReviewOutputError("missing field 'raw_output'")
    by_fid = {finding_id_at(i): finding.finding_id for i, finding in enumerate(findings)}
    parsed = parse_decisions(raw, list(by_fid))
    if parsed.is_empty:
        return None
    decisions: dict[str, CombDecision] = {by_fid[fid]: d for fid, d in parsed.decisions.items()}
    undecided = sum(d.verdict is CombVerdict.UNDECIDED for d in decisions.values())
    if undecided:
        _logger.warning(
            "recall %s: comb decided %d of %d findings",
            stage_label(stage),
            len(decisions) - undecided,
            len(decisions),
        )
    return {
        "decisions": decisions,
        "duplicate_decisions": parsed.duplicate_decisions,
        "unknown_ids": parsed.unknown_ids,
    }


def _entry(stage: PendingStage, context: IngestContext, **fields: Any) -> StageEntry:
    base: dict[str, Any] = {
        "kind": stage.kind,
        "config": stage.config,
        "effort_configured": stage.effort_configured,
        # 420 D5: a call that failed or was never made carries the effort it would have
        # sent, so the entry keeps its stage identity and is scored (dropped or a miss)
        # rather than vanishing from the recipe. A parsed output overrides this.
        "effort_sent": effort_sent_by_profile(str(stage.config.profile), stage.effort_configured),
        "usage": StageUsage(),
        "source": LIVE_SOURCE,
        "case_set": context.case_set,
        "alias": stage.alias,
        "created": context.clock(),
    }
    return StageEntry.model_validate({**base, **fields})
