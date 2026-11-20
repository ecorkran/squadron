"""The kept-findings rule over a two-comb chain (slice 434, D5)."""

from __future__ import annotations

from squadron.metrology.recall_run_models import CombDecision, CombVerdict
from squadron.recipes.kept_findings import (
    apply_comb,
    chain_result,
    comb_input,
    decisions_by_finding,
    pass_through,
)
from tests.recipes.support import recall_finding

KEEP = CombDecision(verdict=CombVerdict.KEEP)
DROP = CombDecision(verdict=CombVerdict.DROP)


def test_keep_drop_undecided_over_a_two_comb_chain() -> None:
    f1, f2, f3, f4 = (recall_finding(i) for i in range(1, 5))
    first = apply_comb([f1, f2, f3, f4], {"F1": KEEP, "F2": DROP, "F4": KEEP})
    assert (first.kept, first.dropped, first.undecided) == ((f1, f4), (f2,), (f3,))
    second_input = first.kept
    assert f3 not in second_input  # undecided is not sent to the next comb
    second = apply_comb(second_input, {"F1": DROP})
    assert (second.kept, second.dropped, second.undecided) == ((), (f1,), (f4,))
    assert chain_result([f1, f2, f3, f4], [first, second]) == (f3, f4)


def test_note_and_pass_are_never_combed() -> None:
    concern, fail = recall_finding(1, "CONCERN"), recall_finding(2, "FAIL")
    note, passed = recall_finding(3, "NOTE"), recall_finding(4, "PASS")
    split = comb_input([concern, note, fail, passed])
    assert split.scored == (concern, fail)
    assert split.unscored == (note, passed)


def test_empty_input_gives_empty_steps() -> None:
    step = apply_comb([], {})
    assert (step.kept, step.dropped, step.undecided) == ((), (), ())
    assert chain_result([], [step]) == ()
    assert chain_result([recall_finding(1)], []) == (recall_finding(1),)


def test_positional_decisions_map_to_finding_ids() -> None:
    f3, f7 = recall_finding(3), recall_finding(7)
    mapped = decisions_by_finding([f3, f7], {"F1": DROP, "F2": KEEP})
    assert mapped == {"F3": DROP, "F7": KEEP}


def test_failed_comb_passes_its_input_through() -> None:
    f1 = recall_finding(1)
    assert pass_through([f1]).kept == (f1,)
