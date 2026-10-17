"""Helpers shared by the ``sq replay`` commands (slice 177)."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich import get_console
from rich.markup import escape

from squadron.config.manager import get_typed_config
from squadron.metrology.errors import MetrologyIdentityError
from squadron.metrology.identity import derive_project_id
from squadron.metrology.project_id import ProjectId
from squadron.metrology.replay_models import ModelRef, ProducerConfigRef, ReplayPhase
from squadron.models.aliases import get_all_aliases
from squadron.replay.start_point import StartPoint, StartPointError, resolve_start_point
from squadron.review.git_utils import run_git
from squadron.stats.git_history import GitHistory, GitHistoryError


def fail(message: str) -> typer.Exit:
    """Print an error and return the exit to raise: ``raise fail("...")``."""
    get_console().print(f"[red]Error: {escape(message)}[/red]")
    return typer.Exit(code=1)


def int_config(key: str, repo_root: Path) -> int:
    """An integer config value; a malformed one exits 1 naming the key to fix."""
    try:
        return get_typed_config(key, int, cwd=str(repo_root))
    except ValueError as exc:
        raise fail(f"{exc}. Fix it with 'sq config set {key} <n>'.") from exc


def model_ref(alias: str) -> ModelRef:
    known = get_all_aliases()
    if alias not in known:
        raise fail(f"unknown model alias '{alias}'")
    return ModelRef(alias=alias, model=known[alias]["model"])


def config_ref(alias: str) -> ProducerConfigRef:
    known = get_all_aliases()
    if alias not in known:
        raise fail(f"unknown model alias '{alias}'")
    entry = known[alias]
    return ProducerConfigRef(
        alias=alias, model=entry["model"], profile=entry["profile"], effort_sent=None
    )


def resolve_project_id(repo_root: Path) -> ProjectId:
    try:
        return derive_project_id(str(repo_root))
    except MetrologyIdentityError as exc:
        raise fail(str(exc)) from exc


def start_point(phase: ReplayPhase, index: int, repo_root: Path) -> StartPoint:
    history = GitHistory(repo_root, run=run_git)
    try:
        history.load()
        return resolve_start_point(phase, index, history)
    except (StartPointError, GitHistoryError) as exc:
        raise fail(str(exc)) from exc


def is_interactive() -> bool:
    return sys.stdin.isatty()
