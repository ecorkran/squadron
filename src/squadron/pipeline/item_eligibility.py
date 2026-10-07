"""Which batch items can be resumed, and with which decisions (slice 199 D3).

The single statement of the rules item resume applies before it touches git. Item
resume and the run listing both read them, so the listing counts an item as open only
when ``--item`` would accept it. Pure rules: no git, lock, executor or file I/O.
"""

from __future__ import annotations

from squadron.pipeline.batch_report import BatchItemRecord, FlagKind, ItemDecision, ItemOutcome
from squadron.pipeline.models import PipelineDefinition, StepConfig
from squadron.pipeline.steps import StepTypeName

RESUMABLE_OUTCOMES = frozenset({ItemOutcome.FLAGGED, ItemOutcome.NOT_RUN})


class ItemResumeUnsupportedError(ValueError):
    """The pipeline does not have exactly one ``each`` step, so ``--item`` cannot apply."""

    def __init__(self, pipeline: str, each_count: int) -> None:
        super().__init__(f"pipeline {pipeline} has {each_count} each steps; --item needs exactly one")
        self.pipeline = pipeline
        self.each_count = each_count


def item_decisions(record: BatchItemRecord) -> frozenset[ItemDecision]:
    """The decisions item resume accepts for *record*; empty when it cannot resume."""
    if record.outcome not in RESUMABLE_OUTCOMES:
        return frozenset()
    if record.flag_kind is FlagKind.REVIEW_UNRESOLVED:
        return frozenset({ItemDecision.RETRY, ItemDecision.ACCEPT})
    return frozenset({ItemDecision.RETRY})


def single_each_step(definition: PipelineDefinition) -> StepConfig:
    """The definition's one ``each`` step; raises ``ItemResumeUnsupportedError`` otherwise."""
    each = [s for s in definition.steps if s.step_type == StepTypeName.EACH]
    if len(each) != 1:
        raise ItemResumeUnsupportedError(definition.name, len(each))
    return each[0]
