"""``run``'s refusals, cost bound and auth preflight (slice 430 D6, D9; run plan part 2).

Per-call figure: the largest observed ``cost_usd`` for the stage's ``config_key`` in recall
run records, else ``--call-cost``. Bound: the sum over priced pending calls plus the
largest figure once (the overshoot: the cap is checked before each call). Plan-billed calls
(Codex) count $0 toward the dollar cap and are capped by ``--max-plan-calls`` instead.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from squadron.benchmark.auth_check import AuthCheckResult
from squadron.benchmark.bench_refusals import AUTH_YES
from squadron.benchmark.grading_config import check_review_timeout
from squadron.benchmark.recall.refusal import RecallRefusal
from squadron.benchmark.recall.run_plan import PendingStage
from squadron.config.keys import BENCHMARK_REVIEW_TIMEOUT_KEY
from squadron.core.process_runner import ProcessRunner
from squadron.metrology.recall_run_models import RecallRun
from squadron.providers.base import ProfileName, ProviderType
from squadron.providers.profiles import get_profile

_logger = logging.getLogger(__name__)

#: Providers billed against a plan, not per call: $0 toward the dollar cap (D9).
PLAN_BILLED_PROVIDERS = frozenset({ProviderType.OPENAI_OAUTH})
MAX_COST_FLAG = "--max-cost"
CALL_COST_FLAG = "--call-cost"
MAX_PLAN_CALLS_FLAG = "--max-plan-calls"
ESTIMATE_LABEL = "estimate"
CALL_COST_LABEL = f"from {CALL_COST_FLAG}"

AuthCheck = Callable[
    [Sequence[str], ProcessRunner, Path, Mapping[str, str], str, float], list[AuthCheckResult]
]


def require_review_timeout(value: object) -> float:
    """``benchmark.review_timeout_s`` through ``check_review_timeout``; unset refuses (D9)."""
    timeout = check_review_timeout(value)
    if timeout is None:
        raise RecallRefusal(f"{BENCHMARK_REVIEW_TIMEOUT_KEY} is not set; run refuses without it")
    return timeout


def is_plan_billed(profile: str) -> bool:
    return get_profile(profile).provider in PLAN_BILLED_PROVIDERS


@dataclass(frozen=True)
class CallFigure:
    usd: float
    observed: bool


@dataclass(frozen=True)
class RunBound:
    pending: list[PendingStage]
    max_cost: float
    max_plan_calls: int | None
    figures: dict[str, CallFigure] = field(default_factory=dict[str, CallFigure])

    def is_plan_billed(self, stage: PendingStage) -> bool:
        return stage.config.config_key not in self.figures

    @property
    def priced(self) -> list[PendingStage]:
        return [stage for stage in self.pending if not self.is_plan_billed(stage)]

    @property
    def plan_billed_calls(self) -> int:
        return len(self.pending) - len(self.priced)

    @property
    def largest(self) -> float:
        return max((figure.usd for figure in self.figures.values()), default=0.0)

    @property
    def bound_usd(self) -> float:
        priced = self.priced
        return sum(self.figures[s.config.config_key].usd for s in priced) + (
            self.largest if priced else 0.0
        )

    @property
    def label(self) -> str:
        return ESTIMATE_LABEL if any(f.observed for f in self.figures.values()) else CALL_COST_LABEL


def observed_costs(runs: list[RecallRun]) -> dict[str, float]:
    """The largest recorded positive ``cost_usd`` per ``config_key`` over live entries.

    A $0 record (a call that made no request, or a free model) is no per-call figure: it
    would make the bound and ``ReviewBudget``'s figure zero, so it falls to ``--call-cost``.
    """
    found: dict[str, float] = {}
    for run in runs:
        for entry in [*run.reviews.values(), *run.combs.values(), *run.superseded]:
            cost = entry.usage.cost_usd
            if entry.is_live and cost is not None and cost > 0:
                key = entry.config.config_key
                found[key] = max(found.get(key, 0.0), cost)
    return found


def build_run_bound(
    pending: list[PendingStage],
    runs: list[RecallRun],
    max_cost: float | None,
    call_cost: float | None,
    max_plan_calls: int | None,
    leak_judgeable: Callable[[ProfileName], bool],
) -> RunBound:
    """The bound for *pending*; every D9 refusal raises ``RecallRefusal``."""
    if max_cost is None or max_cost <= 0:
        raise RecallRefusal(f"{MAX_COST_FLAG} is required and must be positive")
    observed = observed_costs(runs)
    figures: dict[str, CallFigure] = {}
    plan_billed = 0
    for stage in pending:
        profile = ProfileName(str(stage.config.profile))
        if not leak_judgeable(profile):
            raise RecallRefusal(
                f"profile {profile.value} ({stage.alias}) has no transcript source and no jailed "
                "builtin tools, so its calls cannot be leak-checked"
            )
        if is_plan_billed(profile):
            plan_billed += 1
            continue
        key = stage.config.config_key
        if key in observed:
            figures[key] = CallFigure(observed[key], observed=True)
        elif call_cost is not None:
            figures[key] = CallFigure(call_cost, observed=False)
        else:
            raise RecallRefusal(f"no observed cost for {stage.alias}: set {CALL_COST_FLAG}")
    if plan_billed and max_plan_calls is None:
        raise RecallRefusal(f"{plan_billed} plan-billed calls are pending: set {MAX_PLAN_CALLS_FLAG}")
    return RunBound(pending=pending, max_cost=max_cost, max_plan_calls=max_plan_calls, figures=figures)


def render_bound(bound: RunBound) -> str:
    """The block printed before the first call (D9), worded after ``grade_plan.render_bound``."""
    if not bound.pending:
        return "0 stages to run"
    lines = [f"{len(bound.pending)} stages to run"]
    groups: dict[tuple[str, str, str], int] = {}
    for stage in bound.pending:
        key = (stage.kind.value, stage.alias, str(stage.config.profile))
        groups[key] = groups.get(key, 0) + 1
    for (kind, alias, profile), count in groups.items():
        stage = next(s for s in bound.pending if (s.kind.value, s.alias) == (kind, alias))
        if bound.is_plan_billed(stage):
            price = "plan-billed"
        else:
            figure = bound.figures[stage.config.config_key]
            price = f"× ${figure.usd:.2f} ({'observed' if figure.observed else CALL_COST_LABEL})"
        lines.append(f"  {kind} {alias} ({profile}): {count} calls {price}")
    priced = len(bound.priced)
    if priced:
        total = bound.bound_usd
        lines.append(
            f"bound: {priced} priced calls ${total - bound.largest:.2f} + one call of overshoot "
            f"${bound.largest:.2f} → at most ${total:.2f} ({bound.label}), "
            f"capped at ${bound.max_cost:.2f}"
        )
        lines.append("       no per-call cap: a call can cost more than its figure")
    else:
        lines.append(f"bound: no priced calls, capped at ${bound.max_cost:.2f}")
    if bound.plan_billed_calls:
        lines.append(f"plan-billed calls: {bound.plan_billed_calls}, cap {bound.max_plan_calls}")
    return "\n".join(lines)


def auth_preflight(
    aliases: Sequence[str],
    runner: ProcessRunner,
    root: Path,
    harness_env: Mapping[str, str],
    sq_path: str,
    timeout_s: float,
    auth_check: AuthCheck,
) -> list[AuthCheckResult]:
    """D6: every distinct profile must answer yes; otherwise ERROR naming it and refuse."""
    rows = auth_check(aliases, runner, root, harness_env, sq_path, timeout_s)
    failed = [row for row in rows if row.answer not in AUTH_YES]
    for row in failed:
        _logger.error(
            "recall auth preflight: profile %s (%s) answered %s: %s",
            row.profile.value,
            row.alias,
            row.answer.value,
            row.stderr.strip()[:300],
        )
    if failed:
        names = ", ".join(row.profile.value for row in failed)
        raise RecallRefusal(
            f"auth preflight failed for profile(s): {names}; run sq benchmark auth-check"
        )
    return rows
