"""``sq benchmark replay-show``: print one stored implementation replay (slice 424)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from squadron.cli.commands.benchmark_common import open_store, repo_root_for, stderr_exit
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_replay_models import ImplementationReplay
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.errors import MetrologyStoreError

NONE = "-"


def _text(value: object) -> str:
    return NONE if value is None else str(value)


def _print_record(record_id: str, replay: ImplementationReplay) -> None:
    config = replay.config
    fields = [
        ("record", record_id),
        ("benchmark", replay.benchmark_id),
        ("case", f"{replay.case_id}  (set {replay.case_set} v{replay.case_set_version}, "
                 f"sample {replay.sample})"),
        ("config", f"{config.alias}  model {config.model}  profile {_text(config.profile)}"),
        ("effort_sent", _text(config.effort_sent)),
        ("pipeline", f"{replay.pipeline} / {replay.producer_step}  (run {replay.run_id})"),
        ("outcome", replay.outcome.value),
        ("absence", _text(replay.absence and replay.absence.value)),
        ("detail", _text(replay.failure_detail)),
        ("commit", _text(replay.commit_sha)),
        ("diff", _text(replay.diff and f"{replay.diff.sha256}  {replay.diff.bytes} bytes, "
                                      f"{replay.diff.files_changed} files")),
        ("environment", _text(replay.environment and replay.environment.identity_digest)),
        ("prompt", _text(replay.prompt and f"{replay.prompt.sha256}  {replay.prompt.source}  "
                                           f"squadron {replay.prompt.squadron_version}")),
        ("cost_usd", _text(replay.cost_usd)),
        ("turns", _text(replay.turns)),
        ("wall_seconds", f"{replay.wall_seconds:.1f}"),
        ("squadron_version", replay.squadron_version),
        ("created_at", replay.created_at.isoformat()),
    ]  # fmt: skip
    for name, value in fields:
        typer.echo(f"{name}: {value}")
    _print_leak(replay)
    typer.echo("instruction files:")
    for path, digest in replay.instruction_files:
        typer.echo(f"  {digest}  {path}")
    if not replay.instruction_files:
        typer.echo(f"  {NONE}")


def _print_leak(replay: ImplementationReplay) -> None:
    if replay.leak is None:
        typer.echo(f"leak: {NONE} (the producer never ran)")
        return
    leak = replay.leak
    typer.echo(
        f"leak: {leak.verdict.value}  rules v{leak.rules_version}  "
        f"{leak.tool_calls_seen} tool calls seen" + (f"  ({leak.detail})" if leak.detail else "")
    )
    for hit in leak.hits:
        typer.echo(f"  hit {hit.rule.value}  {hit.tool}: {hit.excerpt}")


def _read(store: BenchmarkRecordStore, record_id: str) -> ImplementationReplay:
    try:
        replay = store.get_replay(record_id)
    except MetrologyStoreError as exc:
        raise stderr_exit(f"Error: {exc}") from exc
    if replay is None:
        raise stderr_exit(f"Error: no replay record {record_id}")
    return replay


def replay_show_command(
    record_id: Annotated[str, typer.Argument(help="An implreplay-… record id.")],
    diff: Annotated[bool, typer.Option("--diff", help="Print the stored diff, exactly.")] = False,
    repo: Annotated[
        Path | None,
        typer.Option("--repo", help="Repository to read (default: the current directory)."),
    ] = None,
) -> None:
    """Print one stored implementation replay; with --diff, the producer's diff."""
    store = open_store(repo_root_for(SubprocessRunner(), repo))
    replay = _read(store, record_id)
    if not diff:
        _print_record(record_id, replay)
        return
    if replay.diff is None:
        raise stderr_exit(f"Error: replay {record_id} has no diff (outcome {replay.outcome.value})")
    try:
        data = store.diffs.get(replay.diff.sha256)
    except MetrologyStoreError as exc:
        raise stderr_exit(f"Error: {exc}") from exc
    # Raw bytes: the diff is printed exactly as stored, not re-decoded.
    typer.echo(data, nl=False)
