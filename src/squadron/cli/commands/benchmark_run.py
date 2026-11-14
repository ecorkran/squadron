"""``sq benchmark run``: replay a case set's producers under each model (slice 424).

``make_run_command`` takes the one seam, ``services_factory``: production passes
``build_production_services``; tests pass a factory of doubles, so no test runs a model.
Nothing here grades (slice 425).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from squadron.benchmark.auth_check import AuthAnswer
from squadron.benchmark.bench_configs import bench_config, producer_config_ref
from squadron.benchmark.bench_plan import (
    DISPATCH_BOUNDED_PROFILES,
    BenchConfig,
    BenchmarkPlan,
    BenchmarkRefusal,
    Caps,
    benchmark_id,
    build_plan,
    config_key,
    format_bound,
    resolve_caps,
)
from squadron.benchmark.bench_refusals import SAMPLES_FLAG, check_plan
from squadron.benchmark.bench_runner import (
    begin_benchmark,
    delete_harness_replays,
    exit_code_for,
    run_benchmark,
)
from squadron.benchmark.build_errors import BuildHalted
from squadron.benchmark.production_deps import build_production_services
from squadron.benchmark.replay_deps import ReplayStoreError
from squadron.benchmark.run_services import ReplayContext, RunServices
from squadron.benchmark.scrubbed_env import MissingCredentialError, MissingHarnessHomeError
from squadron.cli.commands.benchmark_common import repo_root_for, stderr_exit
from squadron.cli.commands.benchmark_run_report import (
    ReplayReporter,
    kept_lines,
    summary_lines,
)
from squadron.config.keys import BENCHMARK_PLANNED_SAMPLES_KEY, COST_CAP_KEY
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.errors import MetrologyStoreError
from squadron.providers.base import ProfileName

ServicesFactory = Callable[[Path], RunServices]

#: Failures a run reports as `Error: <message>` with exit 1, not a traceback: refusals, store
#: failures, and an environment a replay cannot be built in (case build halted, a credential or
#: the harness HOME missing).
_REFUSED_ERRORS = (
    BenchmarkRefusal,
    MetrologyStoreError,
    ReplayStoreError,
    BuildHalted,
    MissingCredentialError,
    MissingHarnessHomeError,
)


def _refuse(message: str) -> typer.Exit:
    return stderr_exit(f"Error: {message}")


def _resolve_samples(flag: int | None, services: RunServices) -> int | None:
    """The flag, else ``benchmark.planned_samples``; ``None`` when neither is set."""
    value: object = flag if flag is not None else services.read_config(BENCHMARK_PLANNED_SAMPLES_KEY)
    if value is None:
        return None
    source = SAMPLES_FLAG if flag is not None else BENCHMARK_PLANNED_SAMPLES_KEY
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise BenchmarkRefusal(f"{source} must be a positive integer, got {value!r}")
    return value


def _load_cases(
    services: RunServices, set_name: str, set_version: int | None
) -> tuple[str, int, dict[str, BenchmarkCase]]:
    case_set = services.store.get_case_set(set_name, set_version)
    if case_set is None:
        wanted = set_name if set_version is None else f"{set_name} v{set_version}"
        raise BenchmarkRefusal(
            f"no case set '{wanted}' in the store; build one with `sq benchmark fix-cases build`"
        )
    cases: dict[str, BenchmarkCase] = {}
    for case_id in case_set.case_ids:
        case = services.store.get_case(case_id)
        if case is None:
            raise BenchmarkRefusal(
                f"case set {case_set.name} v{case_set.version} names {case_id}, "
                f"which is not in the store"
            )
        cases[case_id] = case
    return case_set.name, case_set.version, cases


def _configs(models: list[str]) -> list[BenchConfig]:
    if len(set(models)) != len(models):
        raise BenchmarkRefusal("--model names the same alias more than once")
    return [bench_config(alias) for alias in models]


@dataclass(frozen=True)
class RunOptions:
    """The command's options, as given."""

    set_name: str
    set_version: int | None
    models: list[str]
    samples: int | None
    max_cost: float | None
    max_cost_per_replay: float | None
    only_cases: list[str] | None
    retry_harness: bool
    keep: bool


def _auth_state(services: RunServices, configs: list[BenchConfig]) -> Mapping[ProfileName, AuthAnswer]:
    """Auth answers for the profiles that can be leak-scanned; the plan refuses the rest."""
    aliases = [
        c.alias
        for c in configs
        if c.profile is not None and services.transcript_sources(ProfileName(c.profile)) is not None
    ]
    return services.auth_check(aliases) if aliases else {}


def _make_plan(
    services: RunServices,
    options: RunOptions,
    set_name: str,
    set_version: int,
    cases: dict[str, BenchmarkCase],
    configs: list[BenchConfig],
    samples: int,
) -> BenchmarkPlan:
    identifier = benchmark_id(set_name, set_version, [config_key(c) for c in configs], samples)
    existing = {record_id for record_id, _ in services.store.replays_for(identifier)}
    return build_plan(
        set_name=set_name,
        set_version=set_version,
        case_ids=list(cases),
        configs=configs,
        samples=samples,
        existing_record_ids=existing,
        only_cases=options.only_cases,
    )


def _execute(
    services: RunServices,
    options: RunOptions,
    make_plan: Callable[[], BenchmarkPlan],
    cases: dict[str, BenchmarkCase],
    caps: Caps,
) -> int:
    """Lock, print the bound, replay, print the summary; return the exit code."""
    plan = make_plan()
    unpriced = services.unpriced_aliases([c.alias for c in plan.configs])

    def print_bound() -> None:
        # Under the lock: ``--retry-harness`` deletes records only once no other invocation
        # of this benchmark can be running, then the plan is rebuilt to include them.
        nonlocal plan
        if options.retry_harness:
            deleted = delete_harness_replays(services.store, plan.benchmark_id)
            typer.echo(f"deleted {deleted} harness-absent replay records to run again")
            plan = make_plan()
        typer.echo(format_bound(plan, caps, DISPATCH_BOUNDED_PROFILES, unpriced))

    started = begin_benchmark(
        plan=plan,
        config_refs=[producer_config_ref(c.alias) for c in plan.configs],
        caps=caps,
        store=services.store,
        root=services.lock_root,
        process_runner=services.process_runner,
        sweep=services.sweep,
        report=typer.echo,
        print_bound=print_bound,
        clock=services.clock,
    )
    context = ReplayContext(plan.benchmark_id, plan.set_name, plan.set_version, caps, options.keep)
    try:
        final = run_benchmark(
            started, plan, cases, services.replay_function(context), services.store,
            services.clock, ReplayReporter(typer.echo),
        )  # fmt: skip
    finally:
        started.lock.release()
        if kept := services.kept_sandboxes():
            for line in kept_lines(kept):
                typer.echo(line)
    stored = [replay for _, replay in services.store.replays_for(plan.benchmark_id)]
    for line in summary_lines(final, stored):
        typer.echo(line)
    return exit_code_for(final)


def _run(services_factory: ServicesFactory, options: RunOptions, repo: Path | None) -> int:
    services = services_factory(repo_root_for(SubprocessRunner(), repo))
    configs = _configs(options.models)
    caps = resolve_caps(
        options.max_cost, options.max_cost_per_replay, services.read_config(COST_CAP_KEY)
    )
    requested_samples = _resolve_samples(options.samples, services)
    name, version, cases = _load_cases(services, options.set_name, options.set_version)
    samples = check_plan(
        list(cases.values()), configs, requested_samples, services.runners,
        services.transcript_sources, _auth_state(services, configs),
    )  # fmt: skip
    return _execute(
        services,
        options,
        lambda: _make_plan(services, options, name, version, cases, configs, samples),
        cases,
        caps,
    )


def make_run_command(services_factory: ServicesFactory) -> Callable[..., None]:
    """The ``run`` command, with *services_factory* as its collaborators."""

    def run_command(
        set_name: Annotated[str, typer.Option("--set", help="Case set to replay.")],
        models: Annotated[
            list[str],
            typer.Option("--model", help="Model alias to run (repeatable).", show_default=False),
        ],
        max_cost: Annotated[
            float | None, typer.Option("--max-cost", help="Cost cap for this invocation, USD.")
        ] = None,
        set_version: Annotated[
            int | None, typer.Option("--set-version", help="Case set version (default: latest).")
        ] = None,
        samples: Annotated[
            int | None,
            typer.Option(
                "--samples", help="Samples per case and model (default: benchmark.planned_samples)."
            ),
        ] = None,
        max_cost_per_replay: Annotated[
            float | None,
            typer.Option(
                "--max-cost-per-replay", help=f"Cost cap per replay, USD (default: {COST_CAP_KEY})."
            ),
        ] = None,
        case: Annotated[
            list[str] | None, typer.Option("--case", help="Replay only this case id (repeatable).")
        ] = None,
        retry_harness: Annotated[
            bool,
            typer.Option("--retry-harness", help="Rerun replays whose absence was the harness's."),
        ] = False,
        keep: Annotated[bool, typer.Option("--keep", help="Leave each sandbox in place.")] = False,
        repo: Annotated[
            Path | None,
            typer.Option("--repo", help="Repository to read (default: the current directory)."),
        ] = None,
    ) -> None:
        """Run the producer on each case of a set under each model and record the replays."""
        options = RunOptions(
            set_name, set_version, models, samples, max_cost, max_cost_per_replay, case,
            retry_harness, keep,
        )  # fmt: skip
        try:
            code = _run(services_factory, options, repo)
        except _REFUSED_ERRORS as exc:
            raise _refuse(str(exc)) from exc
        if code != 0:
            raise typer.Exit(code)

    return run_command


run_command = make_run_command(build_production_services)
