"""The replay report core against hand-computed fixtures (slice 177 D7)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from squadron.metrology.replay_models import (
    JudgeRef,
    PairOutcome,
    PairwiseJudgment,
    ProducerReplay,
    ReplayOutcome,
    ReplayPhase,
)
from squadron.replay.report import replay_report
from squadron.replay.report_models import ORIGINAL_LABEL, ConfigRow, ReplayReport
from tests.metrology.replay_builders import PROJECT, make_judgment, make_replay

_T0 = datetime(2026, 11, 1, tzinfo=UTC)
_ORIGINAL = "original:" + "a" * 40
_OPUS_MODEL = "claude-opus-5-5"
_JUDGE = JudgeRef(alias="judge", model=_OPUS_MODEL, prompt_hash="d" * 64)


class _Store:
    def __init__(
        self, replays: list[tuple[str, ProducerReplay]], judgments: list[PairwiseJudgment]
    ) -> None:
        self._replays, self._judgments = replays, judgments

    def list_replays(
        self, project_id: str, phase: ReplayPhase | None = None, replay_set: str | None = None
    ) -> list[tuple[str, ProducerReplay]]:
        return [r for r in self._replays if phase is None or r[1].phase == phase]

    def list_judgments(
        self, project_id: str, phase: ReplayPhase | None = None, judge: JudgeRef | None = None
    ) -> list[PairwiseJudgment]:
        return [j for j in self._judgments if phase is None or j.phase == phase]


def _replay(minutes: int, **kw: object) -> ProducerReplay:
    return make_replay(created_at=_T0 + timedelta(minutes=minutes), **kw)  # type: ignore[arg-type]


def _r(
    minutes: int, replay_set: str, slice_index: int, who: dict[str, str], **kw: object
) -> ProducerReplay:
    return _replay(minutes, replay_set=replay_set, slice_index=slice_index, **who, **kw)


def _fixture() -> tuple[list[tuple[str, ProducerReplay]], list[PairwiseJudgment]]:
    """Two configs over two slices under reviewer 'sonnet'; opus failed once, haiku exhausted once.

    opus : r1 s176 accepted rounds 1  $1.00 (2,2) 10s | r2 s177 accepted rounds 3 $3.00 (2,2) 30s
           r3 s177 failed             $0.50 (1,1) 20s
    haiku: r4 s176 accepted rounds 2  no cost (0,2) 5s | r5 s177 exhausted rounds 3 $0.10 (2,2) 7s
    """
    opus = {"alias": "opus", "model": _OPUS_MODEL}
    haiku = {"alias": "haiku", "model": "claude-haiku-5-5"}
    replays = [
        ("r1", _r(1, "s176", 176, opus, rounds=1, cost_usd=1.0, priced=(2, 2), wall_seconds=10)),
        ("r2", _r(2, "s177", 177, opus, rounds=3, cost_usd=3.0, priced=(2, 2), wall_seconds=30)),
        (
            "r3",
            _r(3, "s177", 177, opus, outcome=ReplayOutcome.FAILED, rounds=None, cost_usd=0.5,
               priced=(1, 1), wall_seconds=20),
        ),
        ("r4", _r(4, "s176", 176, haiku, rounds=2, cost_usd=None, priced=(0, 2), wall_seconds=5)),
        (
            "r5",
            _r(5, "s177", 177, haiku, outcome=ReplayOutcome.EXHAUSTED, rounds=3, cost_usd=0.1,
               priced=(2, 2), wall_seconds=7, guide_version="v0.21.1"),
        ),
    ]  # fmt: skip

    def judged(a: str, b: str, outcome: PairOutcome, replay_set: str) -> PairwiseJudgment:
        return make_judgment(judge=_JUDGE, replay_set=replay_set, a=a, b=b, outcome=outcome)

    judgments = [
        judged("r1", "r4", PairOutcome.A, "s176"),  # opus beats haiku
        judged("r1", _ORIGINAL, PairOutcome.TIE, "s176"),
        judged("r4", _ORIGINAL, PairOutcome.A, "s176"),  # haiku beats the original
        judged("r2", "r5", PairOutcome.B, "s177"),  # haiku beats opus
        judged("r2", _ORIGINAL, PairOutcome.INCONSISTENT, "s177"),
        judged("r5", _ORIGINAL, PairOutcome.INVALID, "s177"),
    ]
    return replays, judgments


def _build(min_n: int = 3, judge_alias: str | None = None, **overrides: object) -> ReplayReport:
    replays, judgments = _fixture()
    return replay_report(
        project_id=PROJECT,
        phase=None,
        judge_alias=judge_alias,
        store=_Store(overrides.get("replays", replays), overrides.get("judgments", judgments)),  # type: ignore[arg-type]
        min_n=min_n,
    )


def _row(report: ReplayReport, alias: str) -> ConfigRow:
    (table,) = report.tables
    return next(r for r in table.rows if r.config is not None and r.config.alias == alias)


def test_replay_columns_match_hand_values() -> None:
    report = _build()

    opus, haiku = _row(report, "opus"), _row(report, "haiku")
    assert (opus.n, opus.failed, opus.accepted, opus.accepted_of) == (3, 1, 2, 2)
    assert opus.median_rounds == 2.0  # accepted replays only: median of 1 and 3
    assert opus.median_cost_usd == 1.0  # median of 1.0, 3.0, 0.5
    assert (opus.priced, opus.llm_actions) == (5, 5)
    assert opus.median_wall_seconds == 20.0
    assert (haiku.n, haiku.failed, haiku.accepted, haiku.accepted_of) == (2, 0, 1, 2)
    assert haiku.median_rounds == 2.0  # the exhausted replay's 3 rounds are not counted
    assert haiku.median_cost_usd == 0.1  # the unpriced replay has no cost, not $0
    assert (haiku.priced, haiku.llm_actions) == (2, 4)  # k of m priced


def test_pairwise_record_pairs_and_counts() -> None:
    report = _build()

    opus, haiku = _row(report, "opus"), _row(report, "haiku")
    (table,) = report.tables
    original = next(r for r in table.rows if r.label == ORIGINAL_LABEL)
    assert (opus.wins, opus.losses, opus.ties, opus.pairs, opus.inconsistent) == (1, 1, 2, 4, 1)
    assert (haiku.wins, haiku.losses, haiku.ties, haiku.pairs, haiku.invalid) == (2, 1, 0, 4, 1)
    assert (original.wins, original.losses, original.ties) == (0, 1, 2)
    assert (original.pairs, original.invalid, original.inconsistent) == (4, 1, 1)
    assert original.config is None and original.n == 0 and original.median_cost_usd is None


def test_strengths_are_fitted_and_the_original_row_has_one() -> None:
    (table,) = _build().tables

    strengths = {r.label: r.strength for r in table.rows}
    assert all(value is not None for value in strengths.values())
    assert strengths[ORIGINAL_LABEL] is not None
    assert table.strengths_converged and table.strength_components == 1


def test_footer_slices_consistency_and_prompt_identities() -> None:
    (table,) = _build().tables

    assert table.slices == (176, 177)
    assert (table.consistent_pairs, table.verdict_pairs) == (4, 5)  # the invalid pair is excluded
    assert table.prompt_identities == (
        "squadron 0.0.0, cf 0.19.13, guide unknown",
        "squadron 0.0.0, cf 0.19.13, guide v0.21.1",
    )
    assert table.reviewer.alias == "sonnet" and table.judge == _JUDGE


def test_below_floor_configs_get_no_rank_and_ranks_follow_strength() -> None:
    at_three = _build(min_n=3)
    at_four = _build(min_n=4)

    ranks_three = {r.label: r.rank for r in at_three.tables[0].rows if r.config is not None}
    assert sorted(v for v in ranks_three.values() if v is not None) == [1, 2]
    opus, haiku = _row(at_four, "opus"), _row(at_four, "haiku")
    assert opus.below_floor is False and opus.rank == 1  # 4 verdict pairs
    assert haiku.below_floor is True and haiku.rank is None  # 3 verdict pairs, one invalid


def test_self_preference_is_flagged_only_when_the_judge_model_is_a_contestant() -> None:
    assert _build().tables[0].self_preference is True  # judge model == opus config's model

    replays, judgments = _fixture()
    other = [
        j.model_copy(update={"judge": _JUDGE.model_copy(update={"model": "someone-else"})})
        for j in judgments
    ]
    report = replay_report(
        project_id=PROJECT, phase=None, judge_alias=None, store=_Store(replays, other), min_n=3
    )
    assert report.tables[0].self_preference is False


def test_two_reviewers_make_two_tables() -> None:
    replays, judgments = _fixture()
    replays.append(("r6", _replay(6, replay_set="s178", slice_index=178, reviewer_alias="opus")))

    report = _build(replays=replays, judgments=judgments)

    assert [t.reviewer.alias for t in report.tables] == ["opus", "sonnet"]
    unjudged = report.tables[0]
    assert unjudged.judge is None and unjudged.rows[0].pairs == 0 and unjudged.rows[0].n == 1


def test_a_judgment_from_another_prompt_hash_is_its_own_table_and_not_mixed() -> None:
    replays, judgments = _fixture()
    other_hash = make_judgment(
        judge=_JUDGE.model_copy(update={"prompt_hash": "e" * 64}),
        replay_set="s176",
        a="r1",
        b="r4",
        outcome=PairOutcome.B,
    )

    report = _build(replays=replays, judgments=[*judgments, other_hash])

    assert len(report.tables) == 2
    main, other = sorted(report.tables, key=lambda t: t.judge.prompt_hash if t.judge else "")
    assert sum(r.pairs for r in main.rows) == 2 * len(judgments) - 2 * 0  # unchanged by the extra
    assert sum(r.pairs for r in other.rows) == 2


def test_filtering_by_judge_alias_drops_other_judges() -> None:
    replays, judgments = _fixture()
    stranger = make_judgment(
        judge=JudgeRef(alias="stranger", model="m", prompt_hash="f" * 64),
        replay_set="s176",
        a="r1",
        b="r4",
    )

    report = _build(replays=replays, judgments=[*judgments, stranger], judge_alias="judge")

    assert [t.judge.alias for t in report.tables if t.judge] == ["judge"]


def test_a_pair_between_two_replays_of_one_config_is_left_out() -> None:
    replays, _ = _fixture()
    same = make_judgment(judge=_JUDGE, replay_set="s177", a="r2", b="r3", outcome=PairOutcome.A)

    report = _build(replays=replays, judgments=[same])

    assert all(r.pairs == 0 for r in report.tables[0].rows)


def test_a_judgment_naming_an_unknown_replay_is_skipped() -> None:
    replays, _ = _fixture()
    ghost = make_judgment(judge=_JUDGE, replay_set="s176", a="r1", b="gone")

    report = _build(replays=replays, judgments=[ghost])

    assert all(r.pairs == 0 for r in report.tables[0].rows)


def test_an_empty_store_is_an_empty_report() -> None:
    report = replay_report(
        project_id=PROJECT, phase=None, judge_alias=None, store=_Store([], []), min_n=3
    )

    assert report.tables == () and report.min_n == 3


def test_json_mirrors_the_table() -> None:
    data = _build().to_json_dict()

    (table,) = data["tables"]  # type: ignore[misc]
    assert table["slices"] == [176, 177] and table["judge"]["alias"] == "judge"
    labels = [row["label"] for row in table["rows"]]
    assert ORIGINAL_LABEL in labels and len(labels) == 3
    assert data["min_n"] == 3


@pytest.mark.parametrize("phase", [ReplayPhase.DESIGN, ReplayPhase.TASKS])
def test_the_phase_filter_reaches_the_store(phase: ReplayPhase) -> None:
    replays, judgments = _fixture()
    report = replay_report(
        project_id=PROJECT, phase=phase, judge_alias=None, store=_Store(replays, judgments), min_n=3
    )

    assert len(report.tables) == (1 if phase is ReplayPhase.DESIGN else 0)


def test_a_row_whose_opponents_all_lack_a_strength_says_why() -> None:
    """Opus beats haiku and loses to the original: haiku never won and the original never lost,
    so both drop out of the fit and leave opus with nobody to be compared with."""
    replays = [
        ("r1", _r(1, "s", 176, {"alias": "opus", "model": _OPUS_MODEL})),
        ("r2", _r(2, "s", 176, {"alias": "haiku", "model": "claude-haiku-5-5"})),
    ]
    judgments = [
        make_judgment(judge=_JUDGE, replay_set="s", a="r1", b="r2", outcome=PairOutcome.A),
        make_judgment(judge=_JUDGE, replay_set="s", a="r1", b=_ORIGINAL, outcome=PairOutcome.B),
    ]

    (table,) = _build(replays=replays, judgments=judgments).tables

    rows = {r.label.split(" ")[0]: r for r in table.rows}
    assert "no wins" in (rows["haiku"].strength_reason or "")
    assert "never lost" in (rows["original"].strength_reason or "")
    assert rows["opus"].strength is None
    assert "no finite strength" in (rows["opus"].strength_reason or "")
