"""Import part 2 on the real committed comb outputs (slice 430 D10)."""

from __future__ import annotations

import pytest

from squadron.benchmark.recall.hand_run_combs import comb_template_marker
from squadron.benchmark.recall.hand_run_import import build_import_plan
from squadron.benchmark.recall.import_plan import ImportPlan
from squadron.metrology.recall_run_models import (
    CHAIN_SEPARATOR,
    COMB_KEY_SEPARATOR,
    CombVerdict,
    StageEntry,
    StageOutcome,
    comb_slot,
    parent_chain_key,
)
from tests.benchmark.recall.committed import RESULTS_DIR, committed_cases


@pytest.fixture(scope="module")
def real_plan() -> ImportPlan:
    return build_import_plan(RESULTS_DIR, committed_cases().values(), "real-bugs@v1")


def _two_stage(plan: ImportPlan) -> list[tuple[StageEntry, StageEntry]]:
    """(stage one, stage two) for every imported two-stage chain."""
    pairs: list[tuple[StageEntry, StageEntry]] = []
    for run in plan.runs.values():
        for slot, entry in run.combs.items():
            review_key, chain = slot.split(COMB_KEY_SEPARATOR)
            parent = parent_chain_key(chain)
            if parent is not None:
                pairs.append((run.combs[comb_slot(review_key, parent)], entry))
    return pairs


def test_real_files_give_480_comb_entries(real_plan: ImportPlan) -> None:
    assert real_plan.comb_entries == 480
    assert not real_plan.skipped


def test_two_stage_chain_key_has_two_parts(real_plan: ImportPlan) -> None:
    pairs = _two_stage(real_plan)
    assert len(pairs) == 40
    assert all((one.alias, two.alias) == ("luna-r", "opus-high") for one, two in pairs)
    chains = [slot.split(COMB_KEY_SEPARATOR)[1] for r in real_plan.runs.values() for slot in r.combs]
    assert {len(chain.split(CHAIN_SEPARATOR)) for chain in chains} == {1, 2}


def test_folders_differing_only_by_name_have_different_config_keys(real_plan: ImportPlan) -> None:
    combs = [e for r in real_plan.runs.values() for e in r.combs.values()]
    by_marker = {e.config.template_hash: e.config.config_key for e in combs}
    assert (
        by_marker[comb_template_marker("opus-high")]
        != by_marker[comb_template_marker("luna-r+opus-high")]
    )
    assert len(set(by_marker.values())) == 12


def test_stage_two_decides_exactly_what_stage_one_kept(real_plan: ImportPlan) -> None:
    pairs = _two_stage(real_plan)
    for one, two in pairs:
        kept = {fid for fid, d in one.decisions.items() if d.verdict is CombVerdict.KEEP}
        assert set(two.decisions) == kept
    with_two = [(one, two) for one, two in pairs if len(two.decisions) == 2]
    assert with_two, "expected a chain where stage one kept two findings"
    one, two = with_two[0]
    dropped = {fid for fid, d in one.decisions.items() if d.verdict is CombVerdict.DROP}
    assert dropped and not dropped & set(two.decisions)


def test_stage_one_keeping_nothing_is_ok_with_no_decisions(real_plan: ImportPlan) -> None:
    empty = [two for _, two in _two_stage(real_plan) if not two.decisions]
    assert len(empty) == 4
    assert all(e.outcome is StageOutcome.OK for e in empty)
