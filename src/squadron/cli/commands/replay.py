"""``sq replay``: controlled producer replay and pairwise judging (slice 177).

A thin shell over ``squadron.replay``: it resolves aliases and the start point, prints the
plan for confirmation, wires the real collaborators into the runner, and maps the result to
an exit code.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import typer
from rich import get_console

from squadron.cli.commands import replay_common as common
from squadron.cli.commands.replay_judge import replay_judge
from squadron.cli.commands.replay_report import replay_report_command
from squadron.cli.replay_views import (
    DECLINED,
    render_plan,
    render_record,
    render_skipped,
    render_summary,
)
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.replay_models import ReplayPhase
from squadron.metrology.store import MetrologyStore, generate_replay_id, resolve_store_dir
from squadron.pipeline.state import StateManager
from squadron.replay.drafts import read_drafts
from squadron.replay.runner import (
    ReplayDeps,
    ReplayPlan,
    ReplayRequest,
    ReplaySetSummary,
    run_replay_set,
    run_sq_subprocess,
)
from squadron.replay.sandbox import ReplaySandbox
from squadron.replay.start_point import StartPoint

replay_app = typer.Typer(
    name="replay",
    help="Replay a past slice artifact under different producer configs, then judge the results.",
    no_args_is_help=True,
)


def _sq_executable() -> str:
    found = shutil.which(sys.argv[0])
    if found is None:
        raise common.fail(f"cannot locate the sq executable from '{sys.argv[0]}'")
    # Absolute: `which` returns a relative path as given (`.venv/bin/sq`), and the run
    # starts in the sandbox directory, where that path does not exist.
    return os.path.abspath(found)


def _deps(start: StartPoint, repo_root: Path) -> ReplayDeps:
    runner = SubprocessRunner()
    store = MetrologyStore(store_dir=resolve_store_dir(cwd=str(repo_root)))
    return ReplayDeps(
        store=store,
        run_states=StateManager(),
        sandbox_factory=lambda replay_id: ReplaySandbox(
            start_sha=start.start_sha,
            replay_id=replay_id,
            repo_root=repo_root,
            slice_index=start.slice_index,
            runner=runner,
        ),
        invoker=run_sq_subprocess,
        process_runner=runner,
        read_drafts=lambda path: read_drafts(path, start.phase, start.slice_index),
        sq_executable=_sq_executable(),
    )


def _exit_code(summary: ReplaySetSummary) -> int:
    """0 when every config produced a record, whatever the outcomes; 1 otherwise."""
    return 0 if not summary.skipped and summary.stopped is None and not summary.declined else 1


replay_app.command("judge")(replay_judge)
replay_app.command("report")(replay_report_command)


@replay_app.command("run")
def replay_run(
    phase: ReplayPhase = typer.Option(..., "--phase", help="The artifact to regenerate."),
    slice_index: int = typer.Option(..., "--slice", help="The slice index."),
    configs: list[str] = typer.Option(..., "--config", help="A producer model alias; repeat it."),
    reviewer: str = typer.Option(..., "--reviewer", help="The fixed reviewer's model alias."),
    max_revisions: int = typer.Option(..., "--max-revisions", min=1, help="Revision rounds allowed."),
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation prompt."),
) -> None:
    """Regenerate one slice's design or task breakdown under each config, in a sandbox."""
    console = get_console()
    if not yes and not common.is_interactive():
        raise common.fail("not interactive: pass --yes to confirm the plan")
    config_refs = [common.config_ref(alias) for alias in configs]
    reviewer_ref = common.model_ref(reviewer)
    repo_root = Path.cwd()
    project_id = common.resolve_project_id(repo_root)
    start = common.start_point(phase, slice_index, repo_root)
    request = ReplayRequest(
        project_id=project_id,
        phase=phase,
        configs=config_refs,
        reviewer=reviewer_ref,
        max_revisions=max_revisions,
    )

    def confirm(plan: ReplayPlan) -> bool:
        render_plan(plan, console)
        return yes or typer.confirm("Run this replay?", default=False)

    summary = run_replay_set(
        request,
        start,
        _deps(start, repo_root),
        confirm=confirm,
        new_replay_id=generate_replay_id,
        on_record=lambda _record_id, record: render_record(record, console),
        on_skip=lambda alias, why: render_skipped(alias, why, console),
    )
    if summary.declined:
        console.print(DECLINED)
    else:
        render_summary(summary, console)
    raise typer.Exit(code=_exit_code(summary))
