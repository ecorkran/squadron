"""Expanding recipes to pending live stages (slice 430 D2, D4, D8)."""

from __future__ import annotations

import pytest

from squadron.benchmark.recall.refusal import RecallRefusal
from squadron.benchmark.recall.run_plan import expand_pending
from squadron.core.models import Effort
from squadron.metrology.recall_run_models import (
    LIVE_SOURCE,
    RecallLeakVerdict,
    RecallRun,
    StageConfig,
    StageEntry,
    StageKind,
    StageOutcome,
)
from squadron.recipes.recipe import Recipe, ReviewerOptions, rules_sha256
from tests.benchmark.recall.scoring_support import comb, config, make_case, review

CASE = make_case()
RECIPE = Recipe(name="r", reviewers=("haiku", "sol"), combs=("luna", "opus"))


LINE_RULES = "Read the changed lines.\n"
LINE_PASS = ReviewerOptions(tools=False, rules="line.md").model_copy(
    update={"rules_content": LINE_RULES}
)


def config_for(
    alias: str, kind: StageKind, options: ReviewerOptions | None = None
) -> tuple[StageConfig, Effort | None]:
    cfg = config(f"{alias}-model", f"live-{kind.value}")
    if options is not None:
        cfg = cfg.model_copy(update={"tool_use": options.tools, "rules_hash": rules_sha256(options)})
    return cfg, Effort.high


def test_a_reviewer_with_options_is_keyed_and_carried_with_them() -> None:
    plain = Recipe(name="plain", reviewers=("haiku",))
    line = Recipe(
        name="line", reviewers=("haiku",), combs=("luna",), reviewer_options={"haiku": LINE_PASS}
    )
    plain_review, line_review, line_comb = expand_pending([plain, line], [CASE], [1], {}, config_for)
    assert plain_review.options is None and plain_review.config.tool_use is True
    assert line_review.options == LINE_PASS
    assert line_review.config.tool_use is False
    assert line_review.config.rules_hash == rules_sha256(LINE_PASS)
    assert line_review.review_key != plain_review.review_key
    # The comb is its own call: it reads the review under the review's key, with no options.
    assert line_comb.options is None and line_comb.review_key == line_review.review_key
    assert line_comb.config.tool_use is True and line_comb.config.rules_hash is None


def test_options_that_change_nothing_expand_as_no_options() -> None:
    plain = Recipe(name="plain", reviewers=("haiku",))
    same = Recipe(name="same", reviewers=("haiku",), reviewer_options={"haiku": ReviewerOptions()})
    (only,) = expand_pending([plain, same], [CASE], [1], {}, config_for)
    assert only.options is None


def test_a_rules_file_that_was_never_read_is_refused() -> None:
    unread = Recipe(
        name="line", reviewers=("haiku",), reviewer_options={"haiku": ReviewerOptions(rules="line.md")}
    )
    with pytest.raises(RecallRefusal, match="line.md"):
        expand_pending([unread], [CASE], [1], {}, config_for)


def _live_review(
    alias: str,
    outcome: StageOutcome = StageOutcome.OK,
    leak: RecallLeakVerdict = RecallLeakVerdict.CONFINED,
) -> StageEntry:
    cfg, effort = config_for(alias, StageKind.REVIEW)
    entry = review(alias, (), source=LIVE_SOURCE, outcome=outcome, leak=leak)
    return entry.model_copy(update={"config": cfg, "effort_configured": effort})


def test_fan_out_with_two_stage_comb_expands_in_order() -> None:
    pending = expand_pending([RECIPE], [CASE], [1, 2], {}, config_for)
    assert len(pending) == 2 * 2 * 3
    first = pending[:3]
    assert [(p.kind, p.alias) for p in first] == [
        (StageKind.REVIEW, "haiku"), (StageKind.COMB, "luna"), (StageKind.COMB, "opus"),
    ]  # fmt: skip
    assert first[2].parent_slot == first[1].slot
    assert first[1].parent_slot is None
    run_one = [p for p in pending if p.run_index == 1]
    assert len({p.file_key for p in run_one}) == len(run_one) == 6


def test_shared_stages_across_recipes_appear_once() -> None:
    single = Recipe(name="h", reviewers=("haiku",))
    pending = expand_pending([single, RECIPE], [CASE], [1], {}, config_for)
    assert sum(p.kind is StageKind.REVIEW and p.alias == "haiku" for p in pending) == 1


def test_stored_live_entries_are_skipped_and_imported_never_count() -> None:
    live = _live_review("haiku")
    imported = review("haiku", ())
    run = RecallRun(
        case_id=CASE.case_id, run_index=1, reviews={live.entry_key: live, imported.entry_key: imported}
    )
    pending = expand_pending(
        [Recipe(name="h", reviewers=("haiku", "sol"))],
        [CASE],
        [1],
        {(CASE.case_id, 1): run},
        config_for,
    )
    assert [p.alias for p in pending] == ["sol"]
    only_imported = RecallRun(case_id=CASE.case_id, run_index=1, reviews={imported.entry_key: imported})
    pending = expand_pending(
        [Recipe(name="h", reviewers=("haiku",))],
        [CASE],
        [1],
        {(CASE.case_id, 1): only_imported},
        config_for,
    )
    assert [p.alias for p in pending] == ["haiku"]


def test_retry_harness_repends_harness_and_leak_entries() -> None:
    failed = _live_review("haiku", outcome=StageOutcome.HARNESS_FAILURE)
    leaked = _live_review("sol", leak=RecallLeakVerdict.LEAKED)
    run = RecallRun(
        case_id=CASE.case_id, run_index=1, reviews={failed.entry_key: failed, leaked.entry_key: leaked}
    )
    recipe = Recipe(name="h", reviewers=("haiku", "sol"))
    assert expand_pending([recipe], [CASE], [1], {(CASE.case_id, 1): run}, config_for) == []
    retry = expand_pending(
        [recipe], [CASE], [1], {(CASE.case_id, 1): run}, config_for, retry_harness=True
    )
    assert [(p.alias, p.replaces) for p in retry] == [("haiku", failed), ("sol", leaked)]


def test_retrying_a_review_repends_its_stored_combs() -> None:
    failed = _live_review("haiku", outcome=StageOutcome.HARNESS_FAILURE)
    recipe = Recipe(name="h", reviewers=("haiku",), combs=("luna", "opus"))
    first_pass = expand_pending([recipe], [CASE], [1], {}, config_for)
    run = RecallRun(case_id=CASE.case_id, run_index=1, reviews={failed.entry_key: failed})
    combs = {}
    for stage in first_pass[1:]:
        cfg, effort = config_for(stage.alias, StageKind.COMB)
        combs[stage.slot] = comb(stage.alias, {}, source=LIVE_SOURCE).model_copy(
            update={"config": cfg, "effort_configured": effort}
        )
    run.combs.update(combs)
    runs = {(CASE.case_id, 1): run}
    assert expand_pending([recipe], [CASE], [1], runs, config_for) == []
    retry = expand_pending([recipe], [CASE], [1], runs, config_for, retry_harness=True)
    assert [(p.kind, p.alias) for p in retry] == [
        (StageKind.REVIEW, "haiku"), (StageKind.COMB, "luna"), (StageKind.COMB, "opus"),
    ]  # fmt: skip
    assert retry[0].replaces == failed
    assert [p.replaces for p in retry[1:]] == [combs[p.slot] for p in retry[1:]]
