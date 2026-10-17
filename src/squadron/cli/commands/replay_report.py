"""``sq replay report``: the per-phase producer table (slice 177 D7)."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich import get_console

from squadron.cli.commands import replay_common as common
from squadron.cli.replay_report_views import render_replay_report
from squadron.metrology.replay_models import ReplayPhase
from squadron.metrology.store import MetrologyStore, resolve_store_dir
from squadron.replay.report import replay_report

MIN_EVIDENCE_KEY = "metrology.min_evidence_n"


def replay_report_command(
    phase: ReplayPhase | None = typer.Option(None, "--phase", help="design or tasks; default both."),
    judge: str | None = typer.Option(None, "--judge", help="Only this judge alias."),
    as_json: bool = typer.Option(False, "--json", help="Emit the report as JSON."),
) -> None:
    """One table per phase, reviewer and judge: quality, cost, time and failure rate per config."""
    repo_root = Path.cwd()
    project_id = common.resolve_project_id(repo_root)
    store = MetrologyStore(store_dir=resolve_store_dir(cwd=str(repo_root)))
    report = replay_report(
        project_id=project_id.value,
        phase=phase,
        judge_alias=judge,
        store=store,
        min_n=common.int_config(MIN_EVIDENCE_KEY, repo_root),
    )
    if as_json:
        typer.echo(json.dumps(report.to_json_dict(), indent=2))
        return
    render_replay_report(report, get_console())
