"""``sq benchmark judge`` (slice 426): pairwise judging of slice-case implementation diffs.

The command is built from a services factory, as ``grade`` is: ``judge_deps`` fills it with
the real collaborators, and command tests substitute doubles so no model is called.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from squadron.benchmark.bench_plan import BenchmarkRefusal
from squadron.benchmark.diff_judge_plan import (
    JudgeHalted,
    JudgePlan,
    JudgeRefusal,
    ResolvedJudge,
    largest_call_cost,
    plan_judge,
)
from squadron.benchmark.diff_judge_reference import ReferenceDiffReader
from squadron.benchmark.diff_judge_runner import (
    EXIT_CAP_REACHED,
    JudgeStatus,
    run_judging,
    summary_lines,
)
from squadron.benchmark.diff_judge_services import JudgeServices
from squadron.benchmark.diff_prompt import diff_judge_prompt_hash
from squadron.benchmark.sandbox import benchmark_root
from squadron.cli.commands.benchmark_common import open_store, repo_root_for, stderr_exit
from squadron.codehost.git_refs import GIT_QUERY_TIMEOUT_SECONDS
from squadron.config.keys import (
    BENCHMARK_JUDGE_MAX_PROMPT_CHARS_KEY,
    BENCHMARK_JUDGE_MODEL_KEY,
    METROLOGY_JUDGE_TIMEOUT_KEY,
)
from squadron.config.manager import check_positive_int, get_config
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.benchmark_replay_models import BenchmarkRun, ImplementationReplay
from squadron.metrology.content_sidecars import ContentSidecars, SidecarKind
from squadron.metrology.errors import MetrologyIdentityError, MetrologyStoreError
from squadron.metrology.identity import derive_project_id
from squadron.metrology.replay_models import JudgeRef
from squadron.metrology.slice_case_store import SliceCaseRecordStore
from squadron.pipeline.resolver import ModelResolutionError, ModelResolver
from squadron.replay.judge_dispatch import judge_effort_sent, one_shot_judge_dispatcher
from squadron.replay.judging import JudgeCallError

JudgeServicesFactory = Callable[[Path], JudgeServices]

_REFUSED = (
    JudgeRefusal,
    JudgeHalted,
    BenchmarkRefusal,
    MetrologyStoreError,
    MetrologyIdentityError,
    ModelResolutionError,
    JudgeCallError,
    ValueError,
)


@dataclass(frozen=True)
class JudgeOptions:
    benchmark_id: str
    max_cost: float | None
    judge_model: str | None
    judge_cost: float | None


@dataclass(frozen=True)
class LoadedBenchmark:
    run: BenchmarkRun
    cases: dict[str, BenchmarkCase]
    replays: list[tuple[str, ImplementationReplay]]


def judge_deps(repo_root: Path) -> JudgeServices:
    """The real collaborators of a judge run for the checkout at *repo_root*; runs no process."""
    runner = SubprocessRunner()
    records = open_store(repo_root)

    def resolve(alias: str) -> ResolvedJudge:
        resolved = ModelResolver().resolve_full(alias)
        if resolved.profile is None:
            raise JudgeCallError(f"alias '{alias}' has no profile, so it cannot be dispatched")
        effort = judge_effort_sent(alias)
        ref = JudgeRef(
            alias=alias,
            model=resolved.model_id,
            prompt_hash=diff_judge_prompt_hash(),
            effort_sent=None if effort is None else effort.value,
        )
        return ResolvedJudge(ref, resolved.profile)

    return JudgeServices(
        repo_root=repo_root,
        store=records,
        slice_store=SliceCaseRecordStore(records),
        process_runner=runner,
        lock_root=benchmark_root(),
        clock=lambda: datetime.now(UTC),
        read_config=lambda key: get_config(key, cwd=str(repo_root)),
        resolve_judge=resolve,
        dispatcher_for=one_shot_judge_dispatcher,
        sidecars=ContentSidecars(records.metrology_store.store_dir, SidecarKind.DIFFS),
        project_id_of=lambda path: derive_project_id(str(path)).value,
    )


def _load(services: JudgeServices, benchmark_id: str) -> LoadedBenchmark:
    """The stored run, its case set's cases and its replays; absent ones are refusals."""
    run = services.store.get_run(benchmark_id)
    if run is None:
        raise JudgeRefusal(f"no benchmark '{benchmark_id}' in the store")
    case_set = services.store.get_case_set(run.case_set, run.case_set_version)
    if case_set is None:
        raise JudgeRefusal(
            f"benchmark {benchmark_id} names case set {run.case_set} v{run.case_set_version}, "
            f"which is not in the store"
        )
    cases: dict[str, BenchmarkCase] = {}
    for case_id in case_set.case_ids:
        case = services.store.get_case(case_id)
        if case is None:
            raise JudgeRefusal(f"case set {run.case_set} names {case_id}, which is not in the store")
        cases[case_id] = case
    return LoadedBenchmark(run, cases, services.store.replays_for(benchmark_id))


def _plan(
    services: JudgeServices, options: JudgeOptions, loaded: LoadedBenchmark, repos: list[Path]
) -> tuple[JudgePlan, int]:
    alias = options.judge_model or services.read_config(BENCHMARK_JUDGE_MODEL_KEY)
    judge = services.resolve_judge(str(alias)) if alias else None
    timeout_s = check_positive_int(
        METROLOGY_JUDGE_TIMEOUT_KEY, services.read_config(METROLOGY_JUDGE_TIMEOUT_KEY)
    )
    limit = check_positive_int(
        BENCHMARK_JUDGE_MAX_PROMPT_CHARS_KEY, services.read_config(BENCHMARK_JUDGE_MAX_PROMPT_CHARS_KEY)
    )
    benchmark_id = loaded.run.benchmark_id
    recorded = (
        {j.record_id for j in services.slice_store.diff_judgments_for(benchmark_id, judge.ref.alias)}
        if judge
        else set[str]()
    )
    observed = (
        largest_call_cost(services.slice_store.diff_judgments_by(judge.ref.alias)) if judge else None
    )
    projects = {services.project_id_of(path): path for path in repos}
    reader = ReferenceDiffReader(services.process_runner, projects, GIT_QUERY_TIMEOUT_SECONDS)
    plan = plan_judge(
        run=loaded.run,
        cases=loaded.cases,
        replays=loaded.replays,
        judge=judge,
        limit=limit,
        max_cost=options.max_cost,
        judge_cost=options.judge_cost,
        observed_cost=observed,
        recorded_ids=recorded,
        repo_projects=set(projects),
        reference_diff_for=reader,
        diff_of=lambda ref: services.store.diffs.get(ref.sha256),
    )
    return plan, timeout_s


def _execute(services: JudgeServices, options: JudgeOptions, repos: list[Path]) -> int:
    loaded = _load(services, options.benchmark_id)
    plan, timeout_s = _plan(services, options, loaded, repos)
    result = run_judging(
        plan,
        store=services.slice_store,
        sidecars=services.sidecars,
        dispatcher=services.dispatcher_for(plan.judge.ref.alias),
        timeout_s=timeout_s,
        lock_root=services.lock_root,
        process_runner=services.process_runner,
        print_line=typer.echo,
        clock=services.clock,
    )
    for line in summary_lines(plan, result):
        typer.echo(line)
    return EXIT_CAP_REACHED if result.status is JudgeStatus.CAP_REACHED else 0


def make_judge_command(services_factory: JudgeServicesFactory) -> Callable[..., None]:
    """The ``judge`` command, with *services_factory* as its collaborators."""

    def judge_command(
        benchmark_id: Annotated[str, typer.Argument(help="The benchmark to judge (bench-…).")],
        max_cost: Annotated[
            float | None, typer.Option("--max-cost", help="Run cap for this invocation, USD.")
        ] = None,
        judge_model: Annotated[
            str | None,
            typer.Option(
                "--judge-model",
                help=f"Alias of the judge (default: {BENCHMARK_JUDGE_MODEL_KEY}).",
            ),
        ] = None,
        judge_cost: Annotated[
            float | None,
            typer.Option(
                "--judge-cost", help="Per-call cost for the bound when no stored judgment has one, USD."
            ),
        ] = None,
        repo: Annotated[
            list[Path] | None,
            typer.Option(
                "--repo", help="Repository holding the cases' project (repeatable; default: here)."
            ),
        ] = None,
    ) -> None:
        """Judge a benchmark's slice-case implementations pairwise, with a stated cost bound."""
        options = JudgeOptions(benchmark_id, max_cost, judge_model, judge_cost)
        runner = SubprocessRunner()
        try:
            repos = [repo_root_for(runner, path) for path in (repo or [None])]
            code = _execute(services_factory(repos[0]), options, repos)
        except _REFUSED as exc:
            raise stderr_exit(f"Error: {exc}") from exc
        if code != 0:
            raise typer.Exit(code)

    return judge_command


judge_command = make_judge_command(judge_deps)
