"""Item eligibility rules shared by item resume and the run listing (slice 199 D3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.pipeline import item_resume
from squadron.pipeline.batch_report import (
    BatchItemRecord,
    BatchReport,
    FlagKind,
    ItemDecision,
    ItemOutcome,
    report_json_path,
)
from squadron.pipeline.item_eligibility import (
    RESUMABLE_OUTCOMES,
    ItemResumeUnsupportedError,
    item_decisions,
    single_each_step,
)
from squadron.pipeline.item_resume import ResumeRequest
from squadron.pipeline.models import PipelineDefinition, StepConfig
from squadron.pipeline.steps import StepTypeName

_FLAG_KINDS: list[FlagKind | None] = [None, *FlagKind]


def _record(outcome: ItemOutcome, flag_kind: FlagKind | None) -> BatchItemRecord:
    return BatchItemRecord("1", "item", outcome, flag_kind=flag_kind)


def _expected(outcome: ItemOutcome, flag_kind: FlagKind | None) -> frozenset[ItemDecision]:
    if outcome not in (ItemOutcome.FLAGGED, ItemOutcome.NOT_RUN):
        return frozenset()
    if flag_kind is FlagKind.REVIEW_UNRESOLVED:
        return frozenset({ItemDecision.RETRY, ItemDecision.ACCEPT})
    return frozenset({ItemDecision.RETRY})


def test_resumable_outcomes_are_flagged_and_not_run() -> None:
    assert RESUMABLE_OUTCOMES == {ItemOutcome.FLAGGED, ItemOutcome.NOT_RUN}


@pytest.mark.parametrize("outcome", list(ItemOutcome))
@pytest.mark.parametrize("flag_kind", _FLAG_KINDS)
def test_item_decisions_over_every_outcome_and_flag_kind(
    outcome: ItemOutcome, flag_kind: FlagKind | None
) -> None:
    assert item_decisions(_record(outcome, flag_kind)) == _expected(outcome, flag_kind)


def _definition(each_count: int) -> PipelineDefinition:
    steps = [StepConfig(step_type="phase", name="design", config={})]
    steps += [
        StepConfig(step_type=StepTypeName.EACH, name=f"each-{i}", config={}) for i in range(each_count)
    ]
    return PipelineDefinition(name="batch", description="", params={}, steps=steps)


def test_single_each_step_returns_the_one_each_step() -> None:
    assert single_each_step(_definition(1)).name == "each-0"


@pytest.mark.parametrize("each_count", [0, 2])
def test_single_each_step_rejects_other_counts(each_count: int) -> None:
    with pytest.raises(ItemResumeUnsupportedError) as caught:
        single_each_step(_definition(each_count))

    assert caught.value.each_count == each_count
    assert caught.value.pipeline == "batch"
    assert f"has {each_count} each steps; --item needs exactly one" in str(caught.value)


@pytest.mark.parametrize("outcome", list(ItemOutcome))
@pytest.mark.parametrize("flag_kind", _FLAG_KINDS)
@pytest.mark.parametrize("decision", list(ItemDecision))
def test_check_record_agrees_with_item_decisions(
    tmp_path: Path, outcome: ItemOutcome, flag_kind: FlagKind | None, decision: ItemDecision
) -> None:
    """Item resume rejects a decision exactly when item_decisions omits it (D3 parity)."""
    report = BatchReport("batch", "run-a", "slices", records=[_record(outcome, flag_kind)])
    report.write(tmp_path)
    path = report_json_path(tmp_path, "run-a", "slices")
    loaded = BatchReport.load(path)
    request = ResumeRequest(run_id="run-a", index="1", decision=decision)

    try:
        item_resume._check_record(loaded, request, path)  # pyright: ignore[reportPrivateUsage]
        accepted = True
    except item_resume._Stop:  # pyright: ignore[reportPrivateUsage]
        accepted = False

    assert accepted == (decision in item_decisions(loaded.records[0]))
