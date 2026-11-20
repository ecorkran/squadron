"""``sq benchmark recall run``: call the missing stages for recipes over a case set (D6, D9).

Order: lock, refusals (timeout, ``--max-cost``, leak-checkable profiles, ``--call-cost``,
``--max-plan-calls``), auth preflight, the bound, then the serial loop. Exit 0 complete,
2 when a cap stopped it with work left, 1 refused or error.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from squadron.benchmark.bench_plan import BenchmarkRefusal
from squadron.benchmark.grade_budget import ReviewBudget
from squadron.benchmark.recall.recall_services import RecallServices, RecallServicesFactory, recall_lock
from squadron.benchmark.recall.recipe_dirs import benchmark_recipe_dirs
from squadron.benchmark.recall.refusal import RecallRefusal
from squadron.benchmark.recall.report_build import set_label
from squadron.benchmark.recall.run_bound import (
    RunBound,
    auth_preflight,
    build_run_bound,
    render_bound,
    require_review_timeout,
)
from squadron.benchmark.recall.run_loop import LoopResult, LoopStatus, live_loop_deps, run_pending
from squadron.benchmark.recall.run_plan import PendingStage, expand_pending
from squadron.benchmark.recall.stage_identity import StageIdentityError
from squadron.benchmark.recall.stage_ingest import IngestContext
from squadron.benchmark.recall.stage_runner import StageDeps
from squadron.cli.commands.benchmark_common import stderr_exit
from squadron.cli.commands.benchmark_grade import EXIT_CAP_REACHED
from squadron.cli.commands.benchmark_recall_common import REFUSED_ERRORS, open_services
from squadron.config.keys import BENCHMARK_REVIEW_TIMEOUT_KEY
from squadron.metrology.recall_case_models import RealBugCase
from squadron.recipes.recipe import RecipeError
from squadron.recipes.recipe_search import load_recipes

RUN_ERRORS = (*REFUSED_ERRORS, RecipeError, StageIdentityError, BenchmarkRefusal)


@dataclass(frozen=True)
class RunOptions:
    recipe_refs: list[str]
    set_ref: str
    runs: int
    max_cost: float | None
    call_cost: float | None
    max_plan_calls: int | None
    retry_harness: bool
    case_names: list[str]


def _cases(services: RecallServices, set_ref: str, names: list[str]) -> tuple[str, list[RealBugCase]]:
    case_set = services.store.resolve_set(set_ref)
    cases = [case for cid in case_set.case_ids if (case := services.store.get_case(cid)) is not None]
    if names:
        unknown = sorted(set(names) - {case.name for case in cases})
        if unknown:
            raise RecallRefusal(f"case(s) not in set {set_ref}: {', '.join(unknown)}")
        cases = [case for case in cases if case.name in names]
    return set_label(case_set), cases


def _plan(services: RecallServices, options: RunOptions) -> tuple[str, RunBound]:
    if options.runs < 1:
        raise RecallRefusal("--runs must be at least 1")
    recipes = load_recipes(options.recipe_refs, benchmark_recipe_dirs(services.repo_root))
    label, cases = _cases(services, options.set_ref, options.case_names)
    stored = services.store.list_runs()
    runs = {(run.case_id, run.run_index): run for run in stored}
    indexes = list(range(1, options.runs + 1))
    pending = expand_pending(
        recipes, cases, indexes, runs, services.live.config_for, options.retry_harness
    )
    bound = build_run_bound(
        pending,
        stored,
        options.max_cost,
        options.call_cost,
        options.max_plan_calls,
        services.live.leak_judgeable,
    )
    return label, bound


def _dispatch(
    services: RecallServices, label: str, bound: RunBound, timeout: float, sq_path: str
) -> LoopResult:
    live = services.live
    deps = StageDeps(
        runner=services.process_runner,
        bench_root=services.bench_root,
        sq_path=Path(sq_path),
        harness_env=live.harness_env,
        review_timeout=timeout,
        leak_checker=live.leak_checker(services.process_runner),
        ingest=IngestContext(sidecar=services.store.reviews, case_set=label, clock=services.clock),
    )
    budget = ReviewBudget(bound.max_cost, bound.largest) if bound.priced else None
    sandboxes = live.sandboxes(services.kind_context(), services.bench_root)
    return run_pending(bound, live_loop_deps(services.store, sandboxes, deps, budget))


def _remaining_lines(remaining: list[PendingStage]) -> list[str]:
    return [
        f"  left: {stage.case.name} run {stage.run_index} {stage.kind.value} {stage.alias}"
        for stage in remaining
    ]


def run_recall(services: RecallServices, options: RunOptions) -> int:
    timeout = require_review_timeout(services.read_config(BENCHMARK_REVIEW_TIMEOUT_KEY))
    with recall_lock(services):
        label, bound = _plan(services, options)
        if not bound.pending:
            typer.echo(render_bound(bound))
            return 0
        sq_path = services.live.sq_path()
        aliases = sorted({stage.alias for stage in bound.pending})
        rows = auth_preflight(
            aliases,
            services.process_runner,
            services.bench_root,
            services.live.harness_env,
            sq_path,
            services.live.auth_timeout(),
            services.live.auth_check,
        )
        for row in rows:
            typer.echo(f"auth {row.profile.value} ({row.alias}): {row.answer.value}")
        typer.echo(render_bound(bound))
        result = _dispatch(services, label, bound, timeout, sq_path)
    typer.echo(f"stored {result.stored} entries; {result.status.value}")
    if result.status is LoopStatus.CAPPED:
        typer.echo(f"cap reached: {result.reason}; {len(result.remaining)} stages left")
        for line in _remaining_lines(result.remaining):
            typer.echo(line)
        return EXIT_CAP_REACHED
    if result.status is LoopStatus.ERROR:
        typer.echo(f"Error: {result.reason}", err=True)
        return 1
    return 0


def make_run_command(services_factory: RecallServicesFactory) -> Callable[..., None]:
    def run_command(
        recipe_refs: Annotated[
            list[str], typer.Option("--recipe", help="Recipe name or file (repeatable).")
        ],
        set_ref: Annotated[str, typer.Option("--set", help="Case set, NAME or NAME@VERSION.")],
        runs: Annotated[int, typer.Option("--runs", help="Run indexes 1..N.")] = 1,
        max_cost: Annotated[
            float | None, typer.Option("--max-cost", help="Dollar cap (required).")
        ] = None,
        call_cost: Annotated[
            float | None, typer.Option("--call-cost", help="Per-call figure when none is observed.")
        ] = None,
        max_plan_calls: Annotated[
            int | None, typer.Option("--max-plan-calls", help="Cap on plan-billed (Codex) calls.")
        ] = None,
        retry_harness: Annotated[
            bool, typer.Option("--retry-harness", help="Rerun harness failures and leak drops.")
        ] = False,
        case_names: Annotated[
            list[str] | None, typer.Option("--case", help="Only this case (repeatable).")
        ] = None,
    ) -> None:
        """Run the missing stages (costs money: prints a bound first, stops at the caps)."""
        options = RunOptions(
            recipe_refs,
            set_ref,
            runs,
            max_cost,
            call_cost,
            max_plan_calls,
            retry_harness,
            case_names or [],
        )
        try:
            code = run_recall(open_services(services_factory), options)
        except RUN_ERRORS as exc:
            raise stderr_exit(f"Error: {exc}") from exc
        if code:
            raise typer.Exit(code)

    return run_command
