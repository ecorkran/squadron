"""What a judge invocation will do, and the bound it states first (slice 426 D13-D16).

``plan_judge`` reads a benchmark's slice cases and replays, builds each case's pairs, and
refuses, naming what is missing, before anything is dispatched or written. A case whose
largest prompt is over the limit, or that has a harness-absent replay, is not judged and is
counted. ``render_bound`` prints the cost bound that must appear before the first call.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from squadron.benchmark.diff_judge import OverSize, check_size, normalized_diffs
from squadron.benchmark.diff_pairs import (
    Pair,
    ReplayInput,
    case_judgeable,
    contestants_for,
    forfeit_for,
    pairs_for,
)
from squadron.config.keys import BENCHMARK_JUDGE_MODEL_KEY
from squadron.metrology.benchmark_models import BenchmarkCase, CaseKind
from squadron.metrology.benchmark_replay_models import BenchmarkRun, DiffRef, ImplementationReplay
from squadron.metrology.replay_models import JudgeRef
from squadron.metrology.slice_case_models import DiffJudgment, diff_judgment_id

RUN_CAP_FLAG = "--max-cost"
JUDGE_MODEL_FLAG = "--judge-model"
JUDGE_COST_FLAG = "--judge-cost"
REPO_FLAG = "--repo"


class JudgeRefusal(ValueError):
    """Judging will not start; the message says what is missing and how to supply it."""


class JudgeHalted(Exception):
    """A step the harness could not finish stopped the run (a record that cannot be stored, a
    git call that did not answer); the records before it stay."""


class FigureSource(StrEnum):
    """Where the per-call figure came from, as the bound labels it."""

    MAX_OBSERVED = "max observed"
    FLAG = JUDGE_COST_FLAG


@dataclass(frozen=True)
class ResolvedJudge:
    """The judge as resolved from its alias: what is recorded and where it is called."""

    ref: JudgeRef
    profile: str


@dataclass(frozen=True)
class CasePlan:
    """A case to judge: the pairs with no record yet (forfeits included)."""

    case: BenchmarkCase
    pairs: tuple[Pair, ...]

    @property
    def forfeits(self) -> int:
        return sum(forfeit_for(pair) is not None for pair in self.pairs)


@dataclass(frozen=True)
class JudgePlan:
    benchmark_id: str
    judge: ResolvedJudge
    run_cap_usd: float
    per_call_usd: float
    figure_source: FigureSource
    limit: int
    cases: tuple[CasePlan, ...]
    over_size: tuple[tuple[BenchmarkCase, OverSize], ...]
    #: Each case with a harness-absent replay, and the absence's outcome value.
    harness_absent: tuple[tuple[BenchmarkCase, str], ...]

    @property
    def pairs(self) -> int:
        return sum(len(plan.pairs) for plan in self.cases)

    @property
    def forfeits(self) -> int:
        return sum(plan.forfeits for plan in self.cases)

    @property
    def calls(self) -> int:
        return 2 * (self.pairs - self.forfeits)

    @property
    def case_count(self) -> int:
        return len(self.cases) + len(self.over_size) + len(self.harness_absent)


def largest_call_cost(judgments: Iterable[DiffJudgment]) -> float | None:
    """The largest priced single-call cost among *judgments*, ``None`` when none is priced."""
    costs = [
        usage.cost_usd
        for judgment in judgments
        for usage in (judgment.first_usage, judgment.second_usage)
        if usage is not None and usage.cost_usd is not None
    ]
    return max(costs) if costs else None


def _per_call_figure(observed: float | None, judge_cost: float | None) -> tuple[float, FigureSource]:
    if observed is not None:
        return observed, FigureSource.MAX_OBSERVED
    if judge_cost is None:
        raise JudgeRefusal(
            "no per-call cost figure: no stored judgment by this judge has one; "
            f"pass {JUDGE_COST_FLAG} USD"
        )
    if judge_cost <= 0:
        raise JudgeRefusal(f"the per-call cost must be positive, got {judge_cost}")
    return judge_cost, FigureSource.FLAG


def _check_inputs(max_cost: float | None, judge: ResolvedJudge | None) -> tuple[float, ResolvedJudge]:
    if max_cost is None:
        raise JudgeRefusal(f"no run cap: pass {RUN_CAP_FLAG} USD")
    if max_cost <= 0:
        raise JudgeRefusal(f"the run cap must be positive, got {max_cost}")
    if judge is None:
        raise JudgeRefusal(
            f"no judge: pass {JUDGE_MODEL_FLAG} ALIAS or set the config key {BENCHMARK_JUDGE_MODEL_KEY}"
        )
    return max_cost, judge


def _check_projects(cases: Iterable[BenchmarkCase], repo_projects: Collection[str]) -> None:
    for case in cases:
        if case.project_id.value not in repo_projects:
            raise JudgeRefusal(
                f"case {case.case_id} belongs to project {case.project_id.value}, which no "
                f"{REPO_FLAG} given matches; pass {REPO_FLAG} PATH for it"
            )


def plan_judge(
    *,
    run: BenchmarkRun,
    cases: Mapping[str, BenchmarkCase],
    replays: Sequence[tuple[str, ImplementationReplay]],
    judge: ResolvedJudge | None,
    limit: int,
    max_cost: float | None,
    judge_cost: float | None,
    observed_cost: float | None,
    recorded_ids: Collection[str],
    repo_projects: Collection[str],
    reference_diff_for: Callable[[BenchmarkCase], bytes],
    diff_of: Callable[[DiffRef], bytes],
) -> JudgePlan:
    """The pairs that still need a record, or a ``JudgeRefusal`` naming what is missing.

    ``reference_diff_for`` reads a case's reference diff from the user's checkout and raises
    ``JudgeRefusal`` for a ``tip_sha`` that checkout lacks. A recorded pair (its id in
    ``recorded_ids``) is excluded. Nothing is dispatched or written here.
    """
    cap, chosen = _check_inputs(max_cost, judge)
    slice_cases = [case for case in cases.values() if case.kind is CaseKind.SLICE]
    _check_projects(slice_cases, repo_projects)
    figure, source = _per_call_figure(observed_cost, judge_cost)
    planned: list[CasePlan] = []
    over_size: list[tuple[BenchmarkCase, OverSize]] = []
    absent: list[tuple[BenchmarkCase, str]] = []
    for case in slice_cases:
        inputs = [
            ReplayInput(rid, replay, None if replay.diff is None else diff_of(replay.diff))
            for rid, replay in replays
            if replay.case_id == case.case_id
        ]
        judgeable = case_judgeable(inputs)
        if not judgeable.judgeable:
            absent.append((case, judgeable.reason or "harness absence"))
            continue
        pairs = pairs_for(contestants_for(case, inputs, reference_diff_for(case)))
        too_long = check_size(case, pairs, limit, normalized_diffs(pairs))
        if too_long is not None:
            over_size.append((case, too_long))
            continue
        pending = tuple(
            pair
            for pair in pairs
            if diff_judgment_id(run.benchmark_id, case.case_id, (pair.a.ref, pair.b.ref), chosen.ref)
            not in recorded_ids
        )
        planned.append(CasePlan(case, pending))
    return JudgePlan(
        benchmark_id=run.benchmark_id,
        judge=chosen,
        run_cap_usd=cap,
        per_call_usd=figure,
        figure_source=source,
        limit=limit,
        cases=tuple(planned),
        over_size=tuple(over_size),
        harness_absent=tuple(absent),
    )


def render_bound(plan: JudgePlan) -> str:
    """The block printed before the first call (D16)."""
    judge = plan.judge
    header = (
        f"judge {plan.benchmark_id}  judge {judge.ref.alias} ({judge.profile})  "
        f"limit {plan.limit} chars"
    )
    counts = (
        f"slice cases {plan.case_count}: {len(plan.cases)} to judge · "
        f"{len(plan.over_size)} over size · {len(plan.harness_absent)} harness-absent"
    )
    pairs = f"pairs {plan.pairs} ({plan.forfeits} forfeits) → {plan.calls} calls"
    if plan.calls == 0:
        return f"{header}\n{counts}\n{pairs}\nnothing to judge"
    figure = plan.per_call_usd
    total = plan.calls * figure
    # The figure is shown as it is multiplied: rounding it to cents would print a total
    # that is not calls × the printed figure.
    source = f"{figure:g} ({plan.figure_source.value})"
    if total > plan.run_cap_usd:
        most = plan.run_cap_usd + figure
        lines = [
            f"{pairs} × ${source} = ${total:.2f}, capped at run cap ${plan.run_cap_usd:.2f}",
            f"       + one call of overshoot ${figure:g} → at most ${most:.2f}",
        ]
    else:
        lines = [f"{pairs} × ${source} = ${total:.2f}, under run cap ${plan.run_cap_usd:.2f}"]
    lines.append("       no per-call cap: a call can cost more than its figure")
    return "\n".join([header, counts, *lines])
