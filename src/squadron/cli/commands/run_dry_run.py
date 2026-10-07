"""``sq run --dry-run`` step rendering: the plan a run would follow, without executing it.

Container steps (``loop``, ``each``) are expanded recursively, so a loop inside an
``each`` body shows. An ``each`` source is evaluated, since sources are read-only
queries, so the preview lists the items the run would select (#149).
"""

from __future__ import annotations

import asyncio
from typing import cast

import typer
from rich import print as rprint
from rich.markup import escape

from squadron.integrations.context_forge import ContextForgeClient, ContextForgeError
from squadron.pipeline.executor import evaluate_each_source, resolve_placeholders
from squadron.pipeline.models import StepConfig
from squadron.pipeline.steps.utils import unpack_inner_steps

DRY_RUN_NO_UNTIL_DISPLAY = "no until — completes after first iteration"
DRY_RUN_COMMIT_EACH_ITERATION_SUFFIX = ", commit_each_iteration: true"
DRY_RUN_NO_ITEMS_DISPLAY = "(no items: nothing to do)"

_LOOP = "loop"
_EACH = "each"
_INDENT = "  "


def render_steps(
    steps: list[StepConfig],
    params: dict[str, object],
    cf_client: ContextForgeClient,
    depth: int = 1,
    *,
    cwd: str,
) -> None:
    """Print *steps*, expanding ``loop`` and ``each`` bodies.

    Raises:
        typer.Exit(1): when an ``each`` source cannot be evaluated; the real run
            would fail at the same point.
    """
    pad = _INDENT * depth
    for step in steps:
        rprint(f"{pad}{step.name} ({step.step_type})")
        # Run-level params resolve; per-item ones such as {slice.index} stay visible.
        shown = resolve_placeholders(step.config, params)
        if step.step_type == _LOOP:
            rprint(f"{pad}{_INDENT}{escape(_loop_line(shown))}")
        elif step.step_type == _EACH:
            _render_each_header(shown, params, cf_client, pad + _INDENT, cwd)
        else:
            continue
        render_steps(_body(step.config), params, cf_client, depth + 1, cwd=cwd)


def _loop_line(config: dict[str, object]) -> str:
    until = config.get("until", DRY_RUN_NO_UNTIL_DISPLAY)
    line = f"max: {config.get('max')}, until: {until}, on_exhaust: {config.get('on_exhaust')}"
    if config.get("commit_each_iteration"):
        line += DRY_RUN_COMMIT_EACH_ITERATION_SUFFIX
    return line


def _render_each_header(
    config: dict[str, object],
    params: dict[str, object],
    cf_client: ContextForgeClient,
    pad: str,
    cwd: str,
) -> None:
    source = str(config.get("source", ""))
    rprint(
        f"{pad}source: {escape(source)}, as: {config.get('as')}, "
        f"on_item_failure: {config.get('on_item_failure')}"
    )
    try:
        _, items = asyncio.run(evaluate_each_source(source, params, cf_client, cwd=cwd))
    except (ContextForgeError, ValueError, KeyError) as exc:
        # CLI boundary: a source that can't be evaluated is reported and fails the
        # preview, because the run itself would stop at the same point.
        rprint(f"[red]{pad}could not evaluate source: {escape(str(exc))}[/red]")
        raise typer.Exit(1) from exc
    if not items:
        rprint(f"{pad}{DRY_RUN_NO_ITEMS_DISPLAY}")
    for item in items:
        rprint(f"{pad}- {escape(_item_label(item))}")


def _item_label(item: dict[str, object]) -> str:
    """``924 Recover a Review…`` for slice items; the raw item for anything else."""
    label = " ".join(str(item[key]) for key in ("index", "name") if key in item) or str(item)
    flag = item.get("flag_reason")
    return f"{label}  [flagged: {flag}]" if flag else label


def _body(config: dict[str, object]) -> list[StepConfig]:
    raw: object = config.get("steps", [])
    if not isinstance(raw, list):
        return []
    entries = cast(list[object], raw)
    return unpack_inner_steps([cast(dict[str, object], s) for s in entries if isinstance(s, dict)])
