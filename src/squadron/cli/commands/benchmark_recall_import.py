"""``sq benchmark recall import``: load the hand-run results as records (slice 430 D10)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from squadron.benchmark.recall.hand_run_import import build_import_plan
from squadron.benchmark.recall.hand_run_overrides import OVERRIDES_PATH
from squadron.benchmark.recall.import_plan import ImportPlan
from squadron.benchmark.recall.import_writer import write_import_plan
from squadron.benchmark.recall.recall_services import (
    RecallRefusal,
    RecallServices,
    RecallServicesFactory,
    recall_lock,
)
from squadron.cli.commands.benchmark_common import stderr_exit
from squadron.cli.commands.benchmark_recall_common import REFUSED_ERRORS, open_services


def render_import_summary(plan: ImportPlan) -> list[str]:
    lines = [
        f"Review entries: {plan.review_entries}",
        f"Comb entries: {plan.comb_entries}",
        f"Run records: {len(plan.runs)}",
        f"Label records: {len(plan.labels)}",
        "Unknown fields: "
        + (
            ", ".join(f"{name} {count}" for name, count in sorted(plan.unknown_counts.items()))
            or "none"
        ),
        f"Duplicates skipped: {len(plan.duplicates)}",
    ]
    lines += [f"  duplicate: {line}" for line in plan.duplicates]
    lines.append(f"Label conflicts (later pass wins): {len(plan.conflicts)}")
    lines += [
        f"  {c.case} {c.content_key[:12]} {c.what}: {c.loser} -> {c.winner}" for c in plan.conflicts
    ]
    lines.append(f"Skipped files and refs: {len(plan.skipped)}")
    lines += [f"  skipped: {s.item}: {s.reason}" for s in plan.skipped]
    return lines


def run_import(services: RecallServices, results_dir: Path, set_ref: str, dry_run: bool) -> int:
    if not results_dir.is_dir():
        raise RecallRefusal(f"results folder {results_dir} does not exist")
    with recall_lock(services):
        case_set = services.store.resolve_set(set_ref)
        cases = [services.store.get_case(case_id) for case_id in case_set.case_ids]
        plan = build_import_plan(
            results_dir,
            [case for case in cases if case is not None],
            f"{case_set.name}@v{case_set.version}",
            services.repo_root / OVERRIDES_PATH,
        )
        for line in render_import_summary(plan):
            typer.echo(line)
        if dry_run:
            typer.echo("Dry run: nothing written.")
        else:
            written = write_import_plan(services.store, plan)
            typer.echo(
                f"Written: {written.runs_written} run records, {written.labels_written} label records"
                if written.changed
                else "No changes."
            )
    if plan.skipped:
        typer.echo(f"Error: {len(plan.skipped)} file(s) or ref(s) skipped", err=True)
        return 1
    return 0


def make_import_command(services_factory: RecallServicesFactory) -> Callable[..., None]:
    def import_command(
        results_dir: Annotated[Path, typer.Argument(help="The hand-run results folder.")],
        set_ref: Annotated[str, typer.Option("--set", help="Case set the entries are produced under.")],
        dry_run: Annotated[
            bool, typer.Option("--dry-run", help="Print counts; write nothing.")
        ] = False,
    ) -> None:
        """Import hand-run review and comb outputs and grading passes as recall records."""
        try:
            code = run_import(open_services(services_factory), results_dir, set_ref, dry_run)
        except REFUSED_ERRORS as exc:
            raise stderr_exit(f"Error: {exc}") from exc
        if code:
            raise typer.Exit(code)

    return import_command
