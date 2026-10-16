"""``sq replay``: controlled producer replay and pairwise judging (slice 177).

A thin shell over ``squadron.replay``: it resolves aliases and the start point, prints the
plan for confirmation, wires the real collaborators into the runner, and maps the result to
an exit code.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import typer
from rich import get_console
from rich.markup import escape

from squadron.cli.replay_views import (
    DECLINED,
    render_plan,
    render_record,
    render_skipped,
    render_summary,
)
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.errors import MetrologyIdentityError
from squadron.metrology.identity import derive_project_id
from squadron.metrology.replay_models import ModelRef, ProducerConfigRef, ReplayPhase
from squadron.metrology.store import MetrologyStore, generate_replay_id, resolve_store_dir
from squadron.models.aliases import get_all_aliases
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
from squadron.replay.start_point import StartPoint, StartPointError, resolve_start_point
from squadron.review.git_utils import run_git
from squadron.stats.git_history import GitHistory, GitHistoryError

replay_app = typer.Typer(
    name="replay",
    help="Replay a past slice artifact under different producer configs, then judge the results.",
    no_args_is_help=True,
)


def _fail(message: str) -> typer.Exit:
    get_console().print(f"[red]Error: {escape(message)}[/red]")
    return typer.Exit(code=1)


def _model_ref(alias: str) -> ModelRef:
    known = get_all_aliases()
    if alias not in known:
        raise _fail(f"unknown model alias '{alias}'")
    return ModelRef(alias=alias, model=known[alias]["model"])


def _config_ref(alias: str) -> ProducerConfigRef:
    known = get_all_aliases()
    if alias not in known:
        raise _fail(f"unknown model alias '{alias}'")
    entry = known[alias]
    return ProducerConfigRef(
        alias=alias, model=entry["model"], profile=entry["profile"], effort_sent=None
    )


def _start_point(phase: ReplayPhase, index: int, repo_root: Path) -> StartPoint:
    history = GitHistory(repo_root, run=run_git)
    try:
        history.load()
        return resolve_start_point(phase, index, history)
    except (StartPointError, GitHistoryError) as exc:
        raise _fail(str(exc)) from exc


def _is_interactive() -> bool:
    return sys.stdin.isatty()


def _sq_executable() -> str:
    found = shutil.which(sys.argv[0])
    if found is None:
        raise _fail(f"cannot locate the sq executable from '{sys.argv[0]}'")
    return found


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
    if not yes and not _is_interactive():
        raise _fail("not interactive: pass --yes to confirm the plan")
    config_refs = [_config_ref(alias) for alias in configs]
    reviewer_ref = _model_ref(reviewer)
    repo_root = Path.cwd()
    try:
        project_id = derive_project_id(str(repo_root))
    except MetrologyIdentityError as exc:
        raise _fail(str(exc)) from exc
    start = _start_point(phase, slice_index, repo_root)
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
