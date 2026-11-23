"""The real-work table from ``recipe_review`` records (slice 434, D10)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from squadron.benchmark.recall.real_work import (
    CONFIG_DIFFERS,
    EFFORT_DIFFERS,
    build_rows,
    chain_counts,
    render_real_work,
)
from squadron.core.finding_categories import ReviewCategory
from squadron.core.models import Effort
from squadron.metrology.models import RECORD_TYPE_RECIPE_REVIEW, MetrologyRecord
from squadron.metrology.recall_run_models import (
    CombDecision,
    CombVerdict,
    StageConfig,
    StageKind,
    StageOutcome,
    StageUsage,
)
from squadron.metrology.recipe_review_models import RecipeReview, RecipeStage
from squadron.review.models import Verdict
from tests.benchmark.recall.support import FIXED_NOW, PROJECT, fake_services, invoke_recall
from tests.recipes.support import recall_finding

REV = StageConfig(
    model="m-rev", profile="openrouter", template_hash="code", tool_use=True, max_output_tokens=None
)
COMB = StageConfig(
    model="m-comb", profile="openrouter", template_hash="comb", tool_use=True, max_output_tokens=None
)
PLANNED = [REV, COMB]
RAW = "a" * 64


def _review(
    outcome: StageOutcome = StageOutcome.OK,
    effort: Effort | None = Effort.high,
    cost: float | None = 0.1,
) -> RecipeStage:
    called = outcome is not StageOutcome.HARNESS_FAILURE
    return RecipeStage(
        kind=StageKind.REVIEW,
        reviewer="rev",
        alias="rev",
        config=REV,
        effort_sent=effort if called else None,
        findings=[recall_finding(1), recall_finding(2), recall_finding(3), recall_finding(4, "NOTE")],
        usage=StageUsage(cost_usd=cost if called else None),
        outcome=outcome,
        raw_ref=RAW if called else None,
    )


def _comb(decisions: dict[str, CombVerdict] | None, cost: float | None = 0.01) -> RecipeStage:
    if decisions is None:  # empty input: no call
        return RecipeStage(
            kind=StageKind.COMB, reviewer="rev", alias="comb", config=COMB, effort_sent=None,
            usage=StageUsage(), outcome=StageOutcome.OK,
        )  # fmt: skip
    return RecipeStage(
        kind=StageKind.COMB,
        reviewer="rev",
        alias="comb",
        config=COMB,
        effort_sent=None,
        decisions={fid: CombDecision(verdict=v) for fid, v in decisions.items()},
        usage=StageUsage(cost_usd=cost),
        outcome=StageOutcome.OK,
        raw_ref=RAW,
    )


def _record(
    stages: list[RecipeStage],
    *,
    complete: bool = True,
    aborted: str | None = None,
    verdict: Verdict = Verdict.CONCERNS,
    planned: list[StageConfig] | None = None,
    minutes: int = 0,
) -> RecipeReview:
    return RecipeReview(
        record_id=f"rrev-{minutes}",
        project_id=PROJECT,
        recipe="duo",
        recipe_hash="h" * 64,
        template="code",
        template_hash="code",
        planned=planned or PLANNED,
        stages=stages,
        verdict=verdict,
        complete=complete,
        aborted=aborted,
        created=FIXED_NOW + timedelta(minutes=minutes),
    )


DECIDED = {"F1": CombVerdict.KEEP, "F2": CombVerdict.DROP, "F3": CombVerdict.UNDECIDED}


def test_complete_empty_comb_skipped_chain_and_aborted_land_in_one_row() -> None:
    records = [
        _record([_review(), _comb(DECIDED)], minutes=0),
        _record([_review(), _comb(None)], verdict=Verdict.PASS, minutes=1),
        _record(
            [_review(StageOutcome.HARNESS_FAILURE)], complete=False, verdict=Verdict.UNKNOWN, minutes=2
        ),
        _record([_review()], complete=False, aborted="parse bug", verdict=Verdict.UNKNOWN, minutes=3),
    ]
    (row,) = build_rows(records)
    assert len(row.records) == 4 and row.flags == []
    text = render_real_work([row])
    assert "| duo [hhhhhhhh] | 4 | 2 (1) |" in text
    assert "PASS 1 CONCERNS 1 FAIL 0 UNKNOWN 2" in text


def test_chain_counts_keep_drop_undecided() -> None:
    counts = chain_counts(_record([_review(), _comb(DECIDED)]))
    assert (counts.raw, counts.kept, counts.dropped, counts.undecided) == (3, 2, 1, 1)


def test_two_efforts_for_one_alias_are_one_row_flagged() -> None:
    records = [_record([_review(effort=Effort.high)]), _record([_review(effort=Effort.low)], minutes=1)]
    (row,) = build_rows(records)
    assert row.flags == [EFFORT_DIFFERS]


def test_changed_template_hash_starts_a_new_row_flagged_config_differs() -> None:
    changed = REV.model_copy(update={"template_hash": "code-v2"})
    rows = build_rows([_record([_review()]), _record([_review()], planned=[changed, COMB], minutes=1)])
    assert len(rows) == 2 and all(CONFIG_DIFFERS in row.flags for row in rows)


def test_unpriced_count_and_mean_of_known_costs() -> None:
    records = [
        _record([_review(cost=0.1), _comb(DECIDED, cost=None)]),
        _record([_review(cost=0.3), _comb(DECIDED, cost=0.1)], minutes=1),
    ]
    text = render_real_work(build_rows(records))
    assert "| $0.25 (1) |" in text  # (0.1 + 0.4) / 2, one review with an unpriced stage


def test_recipe_filter() -> None:
    assert build_rows([_record([_review()])], ["other"]) == []


def _store_record(services_root: Path, record: RecipeReview) -> None:
    from squadron.metrology.store import MetrologyStore

    envelope = MetrologyRecord(
        schema_version=1, record_type=RECORD_TYPE_RECIPE_REVIEW, recipe_review=record
    )
    MetrologyStore(services_root / "store").write_record(record.record_id, envelope)


def test_real_work_needs_no_set_and_without_either_errors(tmp_path: Path) -> None:
    services = fake_services(tmp_path)
    _store_record(tmp_path, _record([_review(), _comb(DECIDED)]))
    result = invoke_recall(services, "report", "--real-work")
    assert result.exit_code == 0, result.output
    assert "| duo [hhhhhhhh] | 1 | 0 (0) |" in result.output
    neither = invoke_recall(services, "report", "--recipe", "duo")
    assert neither.exit_code == 1 and "--set is required unless --real-work" in neither.output


def test_json_with_real_work_is_refused(tmp_path: Path) -> None:
    result = invoke_recall(fake_services(tmp_path), "report", "--real-work", "--json")
    assert result.exit_code == 1 and "--json is not supported with --real-work" in result.output


def _filtered_record(keep: tuple[ReviewCategory, ...] | None) -> RecipeReview:
    findings = [
        recall_finding(1, "CONCERN", ReviewCategory.CORRECTNESS),
        recall_finding(2, "FAIL", ReviewCategory.TEST_DEBT),
        recall_finding(3, "CONCERN", ReviewCategory.TEST_DEBT),
        recall_finding(4, "NOTE", ReviewCategory.TEST_DEBT),
    ]
    review = _review().model_copy(update={"findings": findings})
    record = _record([review])
    return record.model_copy(update={"keep_categories": keep})


def test_not_gating_findings_are_counted_apart_from_kept() -> None:
    counts = chain_counts(_filtered_record((ReviewCategory.CORRECTNESS,)))
    assert (counts.raw, counts.not_gating, counts.kept) == (3, 2, 1)
    text = render_real_work(build_rows([_filtered_record((ReviewCategory.CORRECTNESS,))]))
    assert "Not gating/review" in text
    assert "| 1 | 0 (0) | 3.0 | 2.0 | 1.0 |" in text


def test_record_without_a_filter_counts_as_before_with_zero_not_gating() -> None:
    counts = chain_counts(_filtered_record(None))
    assert (counts.raw, counts.not_gating, counts.kept) == (3, 0, 3)
    assert "| 1 | 0 (0) | 3.0 | 0.0 | 3.0 |" in render_real_work(build_rows([_filtered_record(None)]))
