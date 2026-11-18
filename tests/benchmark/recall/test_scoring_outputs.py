"""Recipe outputs per (case, run): selection, chains, fan-out, pool, drops (slice 430 D2-D4, D8)."""

from __future__ import annotations

from squadron.benchmark.recall.recipe import Recipe
from squadron.benchmark.recall.scoring import recipe_outputs
from squadron.benchmark.recall.scoring_select import ImportOnlyResolver, StageIdentity, identity_of
from squadron.metrology.recall_run_models import (
    LIVE_SOURCE,
    CombVerdict,
    RecallLeakVerdict,
    RecallRun,
    StageOutcome,
)
from tests.benchmark.recall.scoring_support import (
    StubResolver,
    add_chain,
    comb,
    finding,
    make_case,
    make_run,
    review,
)

KEEP, DROP, UNDECIDED = CombVerdict.KEEP, CombVerdict.DROP, CombVerdict.UNDECIDED
CASE = make_case()


def _runs(*runs: RecallRun) -> dict[tuple[str, int], RecallRun]:
    return {(run.case_id, run.run_index): run for run in runs}


def test_fan_out_is_the_union_with_duplicates_and_notes_unscored() -> None:
    a = review("a", (finding(1, "src/a.py"), finding(2, None, severity="NOTE")))
    b = review("b", (finding(1, "src/a.py"), finding(2, "src/b.py", severity="FAIL")))
    rows = recipe_outputs(
        Recipe(name="ab", reviewers=("a", "b")),
        [CASE],
        _runs(make_run(CASE, 1, a, b)),
        [1],
        ImportOnlyResolver(),
    )
    assert len(rows) == 1 and not rows[0].flagged
    pair = rows[0].pairs[0]
    assert [len(r.lower) for r in pair.reviewers] == [1, 2]


def test_pool_keeps_member_outputs() -> None:
    a = review("a", (finding(1, "src/a.py"),))
    b = review("b", ())
    rows = recipe_outputs(
        Recipe(name="p", reviewers=("a", "b"), pool=True),
        [CASE],
        _runs(make_run(CASE, 1, a, b)),
        [1],
        ImportOnlyResolver(),
    )
    assert [r.alias for r in rows[0].pairs[0].reviewers] == ["a", "b"]


def test_two_stage_chain_with_stage_one_undecided() -> None:
    findings = tuple(finding(i, "src/a.py") for i in range(1, 5))
    rev = review("a", findings)
    run = make_run(CASE, 1, rev)
    one = comb("c1", {"F1": KEEP, "F2": KEEP, "F3": UNDECIDED, "F4": DROP})
    two = comb("c2", {"F1": KEEP, "F2": DROP})
    add_chain(run, rev, one, two)
    rows = recipe_outputs(
        Recipe(name="r", reviewers=("a",), combs=("c1", "c2")),
        [CASE],
        _runs(run),
        [1],
        ImportOnlyResolver(),
    )
    output = rows[0].pairs[0].reviewers[0]
    assert [f.finding_id for f in output.lower] == ["F1"]
    assert [f.finding_id for f in output.upper] == ["F1", "F3"]
    assert output.undecided_comb == 1


def test_failed_comb_keeps_nothing() -> None:
    rev = review("a", (finding(1, "src/a.py"),))
    run = make_run(CASE, 1, rev)
    add_chain(run, rev, comb("c1", {}, outcome=StageOutcome.CONFIG_FAILURE))
    rows = recipe_outputs(
        Recipe(name="r", reviewers=("a",), combs=("c1",)), [CASE], _runs(run), [1], ImportOnlyResolver()
    )
    assert rows[0].pairs[0].reviewers[0].upper == ()


def test_harness_and_leak_drops_are_counted() -> None:
    case2, case3 = make_case("demo-2"), make_case("demo-3")
    runs = _runs(
        make_run(CASE, 1, review("a", ())),
        make_run(case2, 1, review("a", (), outcome=StageOutcome.HARNESS_FAILURE)),
        make_run(case3, 1, review("a", (), leak=RecallLeakVerdict.LEAKED)),
    )
    row = recipe_outputs(
        Recipe(name="r", reviewers=("a",)), [CASE, case2, case3], runs, [1], ImportOnlyResolver()
    )[0]
    assert len(row.pairs) == 1
    assert row.dropped == {"harness": 1, "leak:leaked": 1}


def test_superseded_entries_are_ignored() -> None:
    run = make_run(CASE, 1, review("a", (finding(1, "src/a.py"),)))
    run.superseded.append(review("a", (), outcome=StageOutcome.HARNESS_FAILURE))
    row = recipe_outputs(
        Recipe(name="r", reviewers=("a",)), [CASE], _runs(run), [1], ImportOnlyResolver()
    )[0]
    assert len(row.pairs) == 1 and not row.dropped


def test_incomplete_coverage_is_listed() -> None:
    runs = _runs(
        make_run(CASE, 1, review("a", ()), review("b", ())), make_run(CASE, 2, review("a", ()))
    )
    row = recipe_outputs(
        Recipe(name="ab", reviewers=("a", "b")), [CASE], runs, [1, 2, 3], ImportOnlyResolver()
    )[0]
    assert len(row.pairs) == 1
    assert row.left_out == [("demo-1", 2), ("demo-1", 3)]


def test_live_and_imported_give_two_flagged_rows() -> None:
    imported = review("a", (finding(1, "src/a.py"),))
    live = review("a", (), model="live-model", source=LIVE_SOURCE)
    resolver = StubResolver({"a": identity_of(live)})
    rows = recipe_outputs(
        Recipe(name="r", reviewers=("a",)),
        [CASE],
        _runs(make_run(CASE, 1, imported, live)),
        [1],
        resolver,
    )
    assert len(rows) == 2 and all(row.flagged for row in rows)
    assert {row.source_tag for row in rows} == {"live", "imported"}
    assert len({row.label for row in rows}) == 2


def test_live_entry_under_alias_a_scores_for_alias_b_with_same_identity() -> None:
    live = review("alias-a", (finding(1, "src/a.py"),), source=LIVE_SOURCE)
    resolver = StubResolver({"alias-b": StageIdentity(live.config.config_key, live.effort_sent)})
    rows = recipe_outputs(
        Recipe(name="r", reviewers=("alias-b",)), [CASE], _runs(make_run(CASE, 1, live)), [1], resolver
    )
    assert len(rows) == 1 and len(rows[0].pairs) == 1 and not rows[0].left_out


def test_nothing_stored_leaves_every_pair_out() -> None:
    row = recipe_outputs(Recipe(name="r", reviewers=("a",)), [CASE], {}, [1, 2], ImportOnlyResolver())[
        0
    ]
    assert row.pairs == [] and row.left_out == [("demo-1", 1), ("demo-1", 2)]
