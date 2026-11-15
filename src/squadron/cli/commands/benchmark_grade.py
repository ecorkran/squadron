"""``sq benchmark grade`` and ``sq benchmark report`` (slice 425).

``make_grade_command`` and ``make_report_command`` take the one seam, ``services_factory``:
production passes ``build_production_grade_services``; tests pass a factory of doubles, so no
test runs a model, a sandbox or git. The commands hold no grading or report logic: they load the
benchmark, plan or assemble, and print.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from squadron.benchmark.bench_report import build_report, latest_grader
from squadron.benchmark.bench_report_render import render_json, render_text
from squadron.benchmark.build_errors import BuildHalted
from squadron.benchmark.grade_estimate import EstimateInputs
from squadron.benchmark.grade_plan import GradePlan, GradeRefusal, plan_grading
from squadron.benchmark.grade_review import MissingReviewTemplateError
from squadron.benchmark.grade_runner import GradeStatus, GradeSummary, run_grading
from squadron.benchmark.grade_services import GradeServices, build_production_grade_services
from squadron.benchmark.grading_config import (
    check_review_floor_runs,
    check_review_timeout,
    check_target_difference,
)
from squadron.benchmark.report_tables import UnregisteredCaseKind
from squadron.benchmark.scrubbed_env import MissingCredentialError, MissingHarnessHomeError
from squadron.cli.commands.benchmark_common import repo_root_for, stderr_exit
from squadron.config.keys import (
    BENCHMARK_GRADING_REVIEW_MODEL_KEY,
    BENCHMARK_REVIEW_FLOOR_RUNS_KEY,
    BENCHMARK_REVIEW_TIMEOUT_KEY,
    BENCHMARK_TARGET_PASS_RATE_DIFFERENCE_KEY,
)
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.benchmark_replay_models import BenchmarkRun, ImplementationReplay
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.grade_models import ReviewerRef
from squadron.models.aliases import UnknownModelAliasError

GradeServicesFactory = Callable[[Path], GradeServices]
EXIT_CAP_REACHED = 2

#: Failures reported as ``Error: <message>`` with exit 1 rather than a traceback.
_REFUSED_ERRORS = (
    GradeRefusal,
    UnknownModelAliasError,
    MissingReviewTemplateError,
    UnregisteredCaseKind,
    MetrologyStoreError,
    BuildHalted,
    MissingCredentialError,
    MissingHarnessHomeError,
)


@dataclass(frozen=True)
class GradeOptions:
    """The command's options, as given."""

    benchmark_id: str
    max_cost: float | None
    review_model: str | None
    review_cost: float | None
    repos: list[Path] | None
    only_cases: list[str] | None
    retry_harness: bool
    keep: bool


@dataclass(frozen=True)
class LoadedBenchmark:
    run: BenchmarkRun
    cases: dict[str, BenchmarkCase]
    replays: list[tuple[str, ImplementationReplay]]


def _config_value[T](check: Callable[[object], T], services: GradeServices, key: str) -> T:
    """A config value through its validator; an invalid one is a refusal naming the key."""
    try:
        return check(services.read_config(key))
    except ValueError as exc:
        raise GradeRefusal(str(exc)) from exc


def load_benchmark(services: GradeServices, benchmark_id: str) -> LoadedBenchmark:
    """The stored run, its case set's cases and its replays; absent ones are refusals."""
    run = services.store.get_run(benchmark_id)
    if run is None:
        raise GradeRefusal(f"no benchmark '{benchmark_id}' in the store")
    case_set = services.store.get_case_set(run.case_set, run.case_set_version)
    if case_set is None:
        raise GradeRefusal(
            f"benchmark {benchmark_id} names case set {run.case_set} v{run.case_set_version}, "
            f"which is not in the store"
        )
    cases: dict[str, BenchmarkCase] = {}
    for case_id in case_set.case_ids:
        case = services.store.get_case(case_id)
        if case is None:
            raise GradeRefusal(f"case set {run.case_set} names {case_id}, which is not in the store")
        cases[case_id] = case
    return LoadedBenchmark(run, cases, services.store.replays_for(benchmark_id))


def _reviewer(services: GradeServices, flag: str | None) -> ReviewerRef | None:
    alias = flag or services.read_config(BENCHMARK_GRADING_REVIEW_MODEL_KEY)
    if not alias:
        return None
    return services.resolve_reviewer(str(alias))


def _plan(
    services: GradeServices, options: GradeOptions, loaded: LoadedBenchmark, repos: list[Path]
) -> GradePlan:
    floor_runs = _config_value(check_review_floor_runs, services, BENCHMARK_REVIEW_FLOOR_RUNS_KEY)
    timeout = _config_value(check_review_timeout, services, BENCHMARK_REVIEW_TIMEOUT_KEY)
    return plan_grading(
        run=loaded.run,
        cases=loaded.cases,
        replays=loaded.replays,
        store=services.grade_store,
        reviewer=_reviewer(services, options.review_model),
        review_floor_runs=floor_runs,
        review_timeout_s=timeout,
        max_cost=options.max_cost,
        review_cost=options.review_cost,
        repo_project_ids={services.project_id_of(path) for path in repos},
        only_cases=options.only_cases,
        retry_harness=options.retry_harness,
    )


def summary_lines(summary: GradeSummary, plan: GradePlan) -> list[str]:
    """The counts after the per-subject lines."""
    lines = [
        f"graded {summary.references_graded} references, {summary.replays_graded} replays: "
        f"{summary.passed} passed, {summary.failed} failed"
    ]
    if summary.absences:
        kinds = ", ".join(f"{kind.value} {n}" for kind, n in sorted(summary.absences.items()))
        lines.append(f"absent: {kinds}")
    if summary.dropped_cases:
        lines.append(f"dropped cases: {', '.join(summary.dropped_cases)}")
    lines.append(
        f"spent ${summary.spent_usd:.2f} of run cap ${plan.run_cap_usd:.2f}; "
        f"{summary.unpriced_reviews} reviews reported no cost and were counted at "
        f"${plan.per_review_usd:.2f} each"
    )
    if summary.status is GradeStatus.CAP_REACHED:
        lines.append("stopped at the run cap; rerun with a larger --max-cost to continue")
    return lines


def kept_lines(services: GradeServices) -> list[str]:
    """One line per sandbox left on disk, saying it holds the reference's hidden tests."""
    return [
        f"kept: {kept.tree} (holds the reference's hidden tests; delete it when done)"
        for kept in services.kept_sandboxes()
    ]


def _execute(
    services: GradeServices, options: GradeOptions, loaded: LoadedBenchmark, repos: list[Path]
) -> int:
    services.sweep(services.process_runner, services.lock_root)
    plan = _plan(services, options, loaded, repos)
    target = _config_value(check_target_difference, services, BENCHMARK_TARGET_PASS_RATE_DIFFERENCE_KEY)
    estimate = EstimateInputs(
        run=loaded.run,
        case_ids=list(loaded.cases),
        replays=loaded.replays,
        target_difference=target,
    )
    summary = run_grading(
        plan,
        lambda budget: services.make_deps(budget, plan, repos, options.keep),
        lock_root=services.lock_root,
        process_runner=services.process_runner,
        print_line=typer.echo,
        grade=services.grade,
        estimate=estimate,
    )
    for line in summary_lines(summary, plan):
        typer.echo(line)
    if options.keep:
        for line in kept_lines(services):
            typer.echo(line)
    return EXIT_CAP_REACHED if summary.status is GradeStatus.CAP_REACHED else 0


def _grade(services_factory: GradeServicesFactory, options: GradeOptions) -> int:
    runner = SubprocessRunner()
    given = options.repos or [None]
    repos = [repo_root_for(runner, path) for path in given]
    services = services_factory(repos[0])
    loaded = load_benchmark(services, options.benchmark_id)
    return _execute(services, options, loaded, repos)


def make_grade_command(services_factory: GradeServicesFactory) -> Callable[..., None]:
    """The ``grade`` command, with *services_factory* as its collaborators."""

    def grade_command(
        benchmark_id: Annotated[str, typer.Argument(help="The benchmark to grade (bench-…).")],
        max_cost: Annotated[
            float | None, typer.Option("--max-cost", help="Run cap for this invocation, USD.")
        ] = None,
        review_model: Annotated[
            str | None,
            typer.Option(
                "--review-model",
                help=f"Alias of the grading reviewer (default: {BENCHMARK_GRADING_REVIEW_MODEL_KEY}).",
            ),
        ] = None,
        review_cost: Annotated[
            float | None,
            typer.Option(
                "--review-cost",
                help="Per-review cost for the bound when no stored grade has one, USD.",
            ),
        ] = None,
        repo: Annotated[
            list[Path] | None,
            typer.Option(
                "--repo", help="Repository holding the cases' project (repeatable; default: here)."
            ),
        ] = None,
        case: Annotated[
            list[str] | None, typer.Option("--case", help="Grade only this case id (repeatable).")
        ] = None,
        retry_harness: Annotated[
            bool,
            typer.Option("--retry-harness", help="Grade again what the harness failed to grade."),
        ] = False,
        keep: Annotated[
            bool, typer.Option("--keep", help="Leave each sandbox in place, hidden tests included.")
        ] = False,
    ) -> None:
        """Grade a benchmark's replays and each case's reference, with a stated cost bound."""
        options = GradeOptions(
            benchmark_id, max_cost, review_model, review_cost, repo, case, retry_harness, keep
        )
        try:
            code = _grade(services_factory, options)
        except _REFUSED_ERRORS as exc:
            raise stderr_exit(f"Error: {exc}") from exc
        if code != 0:
            raise typer.Exit(code)

    return grade_command


grade_command = make_grade_command(build_production_grade_services)


def _report(
    services_factory: GradeServicesFactory, benchmark_id: str, as_json: bool, repo: Path | None
) -> str:
    services = services_factory(repo_root_for(SubprocessRunner(), repo))
    loaded = load_benchmark(services, benchmark_id)
    grades = [grade for _, grade in services.grade_store.grades_for(benchmark_id)]
    grader = latest_grader(grades)
    if grader is None:
        raise GradeRefusal(
            f"benchmark {benchmark_id} has no grades; run `sq benchmark grade {benchmark_id}` first"
        )
    report = build_report(
        run=loaded.run,
        cases=loaded.cases,
        case_ids=list(loaded.cases),
        replays=loaded.replays,
        grades=grades,
        grader=grader,
        reference_for=lambda case_id, digest: services.grade_store.get_reference_grade(
            case_id, grader.digest, digest
        ),
        estimate=services.grade_store.estimate_for(benchmark_id),
    )
    return render_json(report) if as_json else render_text(report)


def make_report_command(services_factory: GradeServicesFactory) -> Callable[..., None]:
    """The ``report`` command, with *services_factory* as its collaborators."""

    def report_command(
        benchmark_id: Annotated[str, typer.Argument(help="The benchmark to report (bench-…).")],
        json_output: Annotated[
            bool, typer.Option("--json", help="Emit the report model as JSON.")
        ] = False,
        repo: Annotated[
            Path | None,
            typer.Option("--repo", help="Repository to read (default: the current directory)."),
        ] = None,
    ) -> None:
        """Print a graded benchmark's report: grades, paired comparison, review, cost, absences."""
        try:
            text = _report(services_factory, benchmark_id, json_output, repo)
        except _REFUSED_ERRORS as exc:
            raise stderr_exit(f"Error: {exc}") from exc
        typer.echo(text)

    return report_command


report_command = make_report_command(build_production_grade_services)
