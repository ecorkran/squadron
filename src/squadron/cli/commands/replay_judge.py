"""``sq replay judge``: compare the replayed first drafts pairwise (slice 177 D5)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich import get_console

from squadron.cli.commands import replay_common as common
from squadron.cli.replay_views import DECLINED, render_judge_plan, render_judge_summary
from squadron.config.manager import get_typed_config
from squadron.metrology.replay_models import JudgeRef, ReplayPhase
from squadron.metrology.store import MetrologyStore, resolve_store_dir
from squadron.pipeline.resolver import ModelResolutionError
from squadron.replay.judge import judge_prompt_hash
from squadron.replay.judge_dispatch import one_shot_judge_dispatcher
from squadron.replay.judge_jobs import build_jobs, judge_jobs, total_calls
from squadron.replay.judging import JudgeCallError, JudgeInputError

NO_REPLAYS = "No replays for this slice and phase; run `sq replay run` first."
NOTHING_TO_JUDGE = "Every pair has already been judged by this judge."


def replay_judge(
    phase: ReplayPhase = typer.Option(..., "--phase", help="The artifact that was replayed."),
    slice_index: int = typer.Option(..., "--slice", help="The slice index."),
    judge: str = typer.Option(..., "--judge", help="The judge's model alias."),
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation prompt."),
) -> None:
    """Judge each pair of replayed first drafts, and the original, in both orders."""
    console = get_console()
    if not yes and not common.is_interactive():
        raise common.fail("not interactive: pass --yes to confirm the judge calls")
    judge_model = common.model_ref(judge)
    repo_root = Path.cwd()
    project_id = common.resolve_project_id(repo_root)
    store = MetrologyStore(store_dir=resolve_store_dir(cwd=str(repo_root)))
    judge_ref = JudgeRef(
        alias=judge_model.alias, model=judge_model.model, prompt_hash=judge_prompt_hash()
    )
    jobs = build_jobs(
        store,
        project_id,
        phase,
        slice_index,
        judge_ref,
        lambda: common.start_point(phase, slice_index, repo_root),
    )
    if not jobs:
        console.print(NO_REPLAYS)
        raise typer.Exit(code=0)
    pairs, calls = total_calls(jobs)
    if pairs == 0:
        console.print(NOTHING_TO_JUDGE)
        raise typer.Exit(code=0)
    render_judge_plan(pairs, calls, judge_ref.alias, judge_ref.prompt_hash, console)
    if not yes and not typer.confirm("Run these judge calls?", default=False):
        console.print(DECLINED)
        raise typer.Exit(code=1)
    try:
        dispatcher = one_shot_judge_dispatcher(judge_ref.alias)
        summary = asyncio.run(
            judge_jobs(
                jobs,
                store=store,
                dispatcher=dispatcher,
                timeout_s=get_typed_config("metrology.judge_timeout_s", int, cwd=str(repo_root)),
            )
        )
    except (JudgeInputError, JudgeCallError, ModelResolutionError) as exc:
        raise common.fail(str(exc)) from exc
    render_judge_summary(summary.judged, summary.failed, summary.invalid, console)
    raise typer.Exit(code=1 if summary.failed else 0)
