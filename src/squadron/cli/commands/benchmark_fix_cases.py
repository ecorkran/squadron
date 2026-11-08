"""``sq benchmark fix-cases build|show`` and ``sq benchmark yield`` (slice 422)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer

from squadron.benchmark.build_errors import BuildHalted
from squadron.benchmark.case_build import BuildDeps, build_fix_cases
from squadron.benchmark.qualify_sandbox import qualify_in_sandbox
from squadron.benchmark.qualify_types import SandboxFactory
from squadron.benchmark.registry import adapter_for
from squadron.benchmark.sandbox import (
    BenchmarkSandbox,
    generate_sandbox_id,
    sweep_benchmark_orphans,
)
from squadron.benchmark.yield_report import build_yield, render_json, render_text
from squadron.cli.commands.benchmark_common import GIT_TIMEOUT_S, git_output, stderr_exit
from squadron.codehost.github_cli import build_github_host
from squadron.config.keys import (
    BENCHMARK_INSTALL_TIMEOUT_KEY,
    BENCHMARK_PLANNED_SAMPLES_KEY,
    BENCHMARK_QUALIFICATION_REPEATS_KEY,
    BENCHMARK_SUITE_TIMEOUT_KEY,
    BENCHMARK_TARGET_PASS_RATE_DIFFERENCE_KEY,
)
from squadron.config.manager import get_open_unit_interval_config, get_positive_int_config
from squadron.core.process_runner import ProcessRunner, SubprocessRunner
from squadron.metrology.benchmark_models import CASE_ID_PREFIX, FixQualification
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.errors import MetrologyIdentityError, MetrologyStoreError
from squadron.metrology.identity import derive_project_id
from squadron.metrology.project_id import ProjectId
from squadron.metrology.snapshot_models import SourceLanguage
from squadron.metrology.store import MetrologyStore, resolve_store_dir

fix_cases_app = typer.Typer(
    name="fix-cases",
    help="Build and inspect fix cases qualified from a project's closing commits.",
    no_args_is_help=True,
)

RepoOption = Annotated[
    Path | None, typer.Option("--repo", help="Repository to read (default: the current directory).")
]


def make_sandbox_factory(
    repo_root: Path, runner: ProcessRunner, *, keep: bool, install_timeout_s: int, suite_timeout_s: int
) -> SandboxFactory:
    """A factory of sandboxes at a commit of ``repo_root``; ``keep`` leaves each one in place."""

    def factory(start_sha: str) -> BenchmarkSandbox:
        sandbox = BenchmarkSandbox(
            start_sha=start_sha,
            sandbox_id=generate_sandbox_id(),
            repo_root=repo_root,
            runner=runner,
            adapter=adapter_for(SourceLanguage.PYTHON),
            harness_env=dict(os.environ),
            install_timeout_s=install_timeout_s,
            suite_timeout_s=suite_timeout_s,
        )
        if keep:
            sandbox.keep()
        return sandbox

    return factory


def _repo_root(runner: ProcessRunner, repo: Path | None) -> Path:
    start = str(repo if repo is not None else Path.cwd())
    return Path(git_output(runner, start, "rev-parse", "--show-toplevel"))


def _open_store(repo_root: Path) -> BenchmarkRecordStore:
    try:
        return BenchmarkRecordStore(MetrologyStore(store_dir=resolve_store_dir(cwd=str(repo_root))))
    except MetrologyStoreError as exc:
        raise stderr_exit(str(exc)) from exc


def _project(repo_root: Path) -> ProjectId:
    try:
        return derive_project_id(str(repo_root))
    except MetrologyIdentityError as exc:
        raise stderr_exit(str(exc)) from exc


def _report_inputs(repo_root: Path) -> tuple[int, float]:
    try:
        samples = get_positive_int_config(BENCHMARK_PLANNED_SAMPLES_KEY, cwd=str(repo_root))
        target = get_open_unit_interval_config(
            BENCHMARK_TARGET_PASS_RATE_DIFFERENCE_KEY, cwd=str(repo_root)
        )
    except ValueError as exc:
        raise stderr_exit(str(exc)) from exc
    return samples, target


@fix_cases_app.command("build")
def build_command(
    set_name: Annotated[str, typer.Option("--set", help="Name of the case set to write.")],
    repo: RepoOption = None,
    commit: Annotated[
        list[str] | None,
        typer.Option("--commit", help="Qualify only this commit (sha prefix; repeatable)."),
    ] = None,
    keep: Annotated[bool, typer.Option("--keep", help="Leave each sandbox in place.")] = False,
) -> None:
    """Discover closing commits, qualify each as a fix case and write the case set."""
    runner = SubprocessRunner()
    repo_root = _repo_root(runner, repo)
    sweep_benchmark_orphans(runner)
    try:
        install_s = get_positive_int_config(BENCHMARK_INSTALL_TIMEOUT_KEY, cwd=str(repo_root))
        suite_s = get_positive_int_config(BENCHMARK_SUITE_TIMEOUT_KEY, cwd=str(repo_root))
        repeats = get_positive_int_config(BENCHMARK_QUALIFICATION_REPEATS_KEY, cwd=str(repo_root))
    except ValueError as exc:
        raise stderr_exit(str(exc)) from exc
    store = _open_store(repo_root)
    deps = BuildDeps(
        host=build_github_host(runner),
        store=store,
        runner=runner,
        sandbox_stages=qualify_in_sandbox,
        sandbox_factory=make_sandbox_factory(
            repo_root, runner, keep=keep, install_timeout_s=install_s, suite_timeout_s=suite_s
        ),
        derive_project_id=derive_project_id,
        repeats=repeats,
        git_timeout_seconds=GIT_TIMEOUT_S,
    )
    try:
        result = build_fix_cases(repo_root, set_name, tuple(commit or ()), deps, typer.echo)
    except BuildHalted as exc:
        raise stderr_exit(str(exc)) from exc
    if result.case_set is None:
        typer.echo("no qualified cases: no case set written")
    else:
        typer.echo(f"case set {result.case_set.name} v{result.case_set.version}")
    typer.echo("")
    samples, target = _report_inputs(repo_root)
    report = build_yield(
        store.list_fix_qualifications(result.project_id), store.list_case_sets(), samples, target
    )
    typer.echo(render_text(report), nl=False)


def _latest(records: list[FixQualification]) -> FixQualification:
    return max(records, key=lambda record: record.created_at)


def _match_records(records: list[FixQualification], target: str) -> list[FixQualification]:
    """Records for a ``case-…`` id, or for commits starting with ``target``."""
    if target.startswith(CASE_ID_PREFIX):
        return [r for r in records if r.case_id == target]
    return [r for r in records if r.commit_sha.startswith(target)]


def _print_record(store: BenchmarkRecordStore, record: FixQualification) -> None:
    environment = record.environment
    typer.echo(f"commit: {record.commit_sha}  (parent {record.parent_sha})")
    typer.echo(f"issue: {record.issue_ref or '-'}")
    typer.echo(
        f"outcome: {record.outcome.value}"
        + (f" ({record.rejection.value})" if record.rejection else "")
    )
    if record.detail:
        typer.echo(f"detail: {record.detail}")
    digest = environment.identity_digest if environment else "none (decided before the sandbox)"
    typer.echo(f"environment: {digest}")
    typer.echo(f"rule version: {record.rule_version}  repeats: {record.repeats}")
    typer.echo("hidden tests:")
    for verdict in record.hidden_verdicts:
        reason = f" {verdict.rejection.value}" if verdict.rejection else ""
        detail = f"  {verdict.detail}" if verdict.detail else ""
        typer.echo(f"  {verdict.kind.value}{reason}  {verdict.node_id}{detail}")
    if record.excluded_with_reasons:
        typer.echo("excluded tests:")
        for node_id, reason in record.excluded_with_reasons:
            typer.echo(f"  {reason.value}  {node_id}")
    if record.case_id is None:
        return
    case = store.get_case(record.case_id)
    if case is None:
        typer.echo(f"case: {record.case_id} (not in the store)")
        return
    typer.echo(f"case: {case.case_id}")
    if case.superseded_tests:
        typer.echo("superseded tests:")
        for node_id in case.superseded_tests:
            typer.echo(f"  {node_id}")
    typer.echo("task text:")
    typer.echo(case.task_text)


@fix_cases_app.command("show")
def show_command(
    target: Annotated[str, typer.Argument(help="A commit sha prefix or a case-… id.")],
    repo: RepoOption = None,
) -> None:
    """Print the latest qualification record for a commit or case."""
    runner = SubprocessRunner()
    repo_root = _repo_root(runner, repo)
    store = _open_store(repo_root)
    try:
        records = _match_records(store.list_fix_qualifications(_project(repo_root)), target)
    except MetrologyStoreError as exc:
        raise stderr_exit(str(exc)) from exc
    if not records:
        raise stderr_exit(f"no qualification record matches {target}")
    commits = sorted({record.commit_sha for record in records})
    if len(commits) > 1:
        listing = "\n".join(f"  {sha}" for sha in commits)
        raise stderr_exit(f"{target} matches several commits:\n{listing}")
    _print_record(store, _latest(records))


def yield_command(
    repo: Annotated[
        list[Path] | None,
        typer.Option("--repo", help="Repository to include (repeatable; default: every project)."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print the report as JSON only.")] = False,
) -> None:
    """Qualified and rejected counts per project, and whether the cases can separate two configs."""
    runner = SubprocessRunner()
    # Without --repo the report covers every stored project, so no git checkout is needed.
    anchor = _repo_root(runner, repo[0]) if repo else Path.cwd()
    store = _open_store(anchor)
    samples, target = _report_inputs(anchor)
    try:
        if repo:
            wanted = {_project(_repo_root(runner, path)).value for path in repo}
            records = [r for r in store.list_fix_qualifications() if r.project_id.value in wanted]
        else:
            records = store.list_fix_qualifications()
        report = build_yield(records, store.list_case_sets(), samples, target)
    except MetrologyStoreError as exc:
        raise stderr_exit(str(exc)) from exc
    typer.echo(render_json(report) if as_json else render_text(report), nl=as_json)
