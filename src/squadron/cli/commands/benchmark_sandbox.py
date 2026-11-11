"""``sq benchmark sandbox``: build a benchmark sandbox at a revision and optionally run tests."""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Annotated

import typer

from squadron.benchmark.adapter import (
    EnvironmentResolutionError,
    NodeOutcome,
    SuiteRun,
    SuiteRunError,
    SuiteSelection,
)
from squadron.benchmark.registry import adapter_for
from squadron.benchmark.sandbox import (
    BenchmarkSandbox,
    generate_sandbox_id,
    sweep_benchmark_orphans,
)
from squadron.benchmark.scrubbed_env import MissingHarnessHomeError, MissingHarnessToolError
from squadron.cli.commands.benchmark_common import git_output, stderr_exit
from squadron.config.keys import BENCHMARK_INSTALL_TIMEOUT_KEY, BENCHMARK_SUITE_TIMEOUT_KEY
from squadron.config.manager import get_positive_int_config
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.snapshot_models import SourceLanguage
from squadron.replay.history_free_sandbox import SandboxError

FAILING_OUTCOMES = (NodeOutcome.FAILED, NodeOutcome.ERROR)


def _print_identity(sandbox: BenchmarkSandbox) -> None:
    for name, value in sandbox.identity.model_dump(mode="json").items():
        typer.echo(f"{name}: {value}")


def _print_run(run: SuiteRun) -> None:
    outcomes = Counter(result.outcome.value for result in run.results)
    kinds = Counter(result.failure_kind.value for result in run.results if result.failure_kind)
    typer.echo("outcomes: " + ", ".join(f"{name}={count}" for name, count in sorted(outcomes.items())))
    if kinds:
        typer.echo(
            "failure kinds: " + ", ".join(f"{name}={count}" for name, count in sorted(kinds.items()))
        )
    if run.timed_out:
        typer.echo("the suite run timed out; unreported nodes are not_run")
    for result in run.results:
        if result.outcome in FAILING_OUTCOMES:
            typer.echo(f"  {result.outcome.value} {result.node_id} ({result.failure_kind})")


def sandbox_command(
    rev: Annotated[str, typer.Argument(help="Commit to build the sandbox at.")],
    suite: Annotated[bool, typer.Option("--suite", help="Run every test.")] = False,
    node: Annotated[list[str] | None, typer.Option("--node", help="Run only this node id.")] = None,
    keep: Annotated[bool, typer.Option("--keep", help="Leave the sandbox in place.")] = False,
) -> None:
    """Build a history-free sandbox at REV, install its locked environment, optionally run tests."""
    if suite and node:
        raise typer.BadParameter("--suite and --node cannot be combined")
    runner = SubprocessRunner()
    repo_root = git_output(runner, str(Path.cwd()), "rev-parse", "--show-toplevel")
    start_sha = git_output(runner, repo_root, "rev-parse", "--verify", f"{rev}^{{commit}}")
    sweep_benchmark_orphans(runner)
    sandbox = BenchmarkSandbox(
        start_sha=start_sha,
        sandbox_id=generate_sandbox_id(),
        repo_root=Path(repo_root),
        runner=runner,
        adapter=adapter_for(SourceLanguage.PYTHON),
        harness_env=dict(os.environ),
        install_timeout_s=get_positive_int_config(BENCHMARK_INSTALL_TIMEOUT_KEY, cwd=repo_root),
        suite_timeout_s=get_positive_int_config(BENCHMARK_SUITE_TIMEOUT_KEY, cwd=repo_root),
    )
    try:
        with sandbox:
            _print_identity(sandbox)
            if suite or node:
                selection = SuiteSelection.nodes(tuple(node)) if node else SuiteSelection.all_tests()
                _print_run(sandbox.run_suite(selection))
            if keep:
                sandbox.keep()
                typer.echo(f"tree: {sandbox.tree}\nhome: {sandbox.home}\nout: {sandbox.output_dir}")
    except EnvironmentResolutionError as exc:
        raise stderr_exit(f"environment resolution failed: {exc.reason.value}\n{exc.detail}") from exc
    except (SandboxError, SuiteRunError, MissingHarnessHomeError, MissingHarnessToolError) as exc:
        raise stderr_exit(str(exc)) from exc
