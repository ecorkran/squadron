"""run command — execute, inspect, and manage pipeline runs."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import typer
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table

from squadron.integrations.context_forge import (
    ContextForgeClient,
    ContextForgeError,
    ContextForgeNotAvailable,
)
from squadron.pipeline.executor import (
    ExecutionStatus,
    PipelineResult,
    execute_pipeline,
)
from squadron.pipeline.loader import (
    discover_pipelines,
    load_pipeline,
    validate_pipeline,
)
from squadron.pipeline.models import PipelineDefinition
from squadron.pipeline.resolver import ModelResolver
from squadron.pipeline.state import SchemaVersionError, StateManager

# ---------------------------------------------------------------------------
# Status display colours
# ---------------------------------------------------------------------------

_STATUS_COLORS: dict[str, str] = {
    "completed": "bright_green",
    "failed": "red",
    "paused": "yellow",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_target(
    definition: PipelineDefinition,
    target: str | None,
) -> tuple[str, str] | None:
    """Map the positional *target* to the pipeline's first required param.

    Returns ``(param_name, target)`` if a required param exists, or ``None``
    if the pipeline has no required params.  Raises ``typer.BadParameter``
    when the pipeline requires a target but none was supplied.
    """
    for name, default in definition.params.items():
        if default == "required":
            if target is None:
                raise typer.BadParameter(
                    f"Pipeline '{definition.name}' requires a '{name}' argument."
                )
            return (name, target)
    return None


def _assemble_params(
    definition: PipelineDefinition,
    target: str | None,
    model: str | None,
    param_list: list[str] | None,
) -> dict[str, object]:
    """Build the runtime params dict from CLI inputs.

    - Binds the positional *target* to the first required pipeline param.
    - Parses ``--param key=value`` entries from *param_list*.
    - Records *model* for state-file resume fidelity (not for model resolution).
    """
    params: dict[str, object] = {}

    binding = _resolve_target(definition, target)
    if binding is not None:
        params[binding[0]] = binding[1]

    if param_list:
        for entry in param_list:
            key, _, value = entry.partition("=")
            if not key:
                raise typer.BadParameter(f"Invalid --param format: '{entry}'")
            params[key] = value

    if model is not None:
        params["model"] = model

    return params


def _check_cf(cf_client: ContextForgeClient) -> None:
    """Verify that Context Forge is available before execution.

    Raises ``typer.Exit(1)`` with a clear message on failure.
    """
    try:
        cf_client.get_project()
    except ContextForgeNotAvailable:
        rprint(
            "[red]Error: Context Forge (cf) is not installed or not on PATH.[/red]\n"
            "Install it with: [bold]sq install-commands[/bold]"
        )
        raise typer.Exit(1)
    except ContextForgeError as exc:
        rprint(f"[red]Error: Context Forge pre-flight check failed — {exc}[/red]")
        raise typer.Exit(1)


async def _run_pipeline(
    pipeline_name: str,
    params: dict[str, object],
    model_override: str | None = None,
    runs_dir: Path | None = None,
    from_step: str | None = None,
    _action_registry: dict[str, object] | None = None,
) -> PipelineResult:
    """Load, validate, and execute a pipeline end-to-end.

    This is the async core called from the sync ``run()`` Typer command via
    ``asyncio.run()``.  All dependency construction happens here so that
    integration tests can call this directly.

    Raises ``FileNotFoundError`` when the pipeline cannot be found — the
    caller is responsible for printing the message and exiting.
    """
    definition = load_pipeline(pipeline_name)

    resolver = ModelResolver(
        cli_override=model_override,
        pipeline_model=definition.model,
    )
    cf_client = ContextForgeClient()
    _check_cf(cf_client)

    state_mgr = StateManager(runs_dir=runs_dir)
    run_id = state_mgr.init_run(pipeline_name, params)

    try:
        result = await execute_pipeline(
            definition,
            params,
            resolver=resolver,
            cf_client=cf_client,
            run_id=run_id,
            start_from=from_step,
            on_step_complete=state_mgr.make_step_callback(run_id),
            _action_registry=_action_registry,
        )
    except BaseException:
        # Finalize with a synthetic failed result on any unhandled exception
        failed = PipelineResult(
            pipeline_name=pipeline_name,
            status=ExecutionStatus.FAILED,
            step_results=[],
            error="Interrupted or unhandled exception",
        )
        state_mgr.finalize(run_id, failed)
        raise

    state_mgr.finalize(run_id, result)
    return result


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _display_run_status(state: object) -> None:
    """Print a Rich Panel summarising a RunState."""
    from squadron.pipeline.state import RunState

    if not isinstance(state, RunState):
        return

    color = _STATUS_COLORS.get(state.status, "dim")
    lines: list[str] = [
        f"[bold]Run:[/bold]      {state.run_id}",
        f"[bold]Pipeline:[/bold] {state.pipeline}",
        f"[bold]Params:[/bold]   {state.params}",
        f"[bold]Status:[/bold]   [{color}]{state.status}[/{color}]",
        f"[bold]Started:[/bold]  {state.started_at:%Y-%m-%d %H:%M:%S}",
        f"[bold]Updated:[/bold]  {state.updated_at:%Y-%m-%d %H:%M:%S}",
        f"[bold]Steps:[/bold]    {len(state.completed_steps)} completed",
    ]
    if state.checkpoint is not None:
        lines.append(
            f"[bold]Checkpoint:[/bold] paused at '{state.checkpoint.step}' "
            f"— {state.checkpoint.reason}"
        )

    rprint(Panel("\n".join(lines), title="Run Status"))


def _display_result(result: PipelineResult) -> None:
    """Print a brief final summary of a completed pipeline run."""
    color = _STATUS_COLORS.get(result.status.value, "dim")
    name = result.pipeline_name
    rprint(f"\n[{color}]Pipeline '{name}' — {result.status.value}[/{color}]")
    rprint(f"  Steps: {len(result.step_results)}")

    for sr in result.step_results:
        verdict_parts: list[str] = []
        for ar in sr.action_results:
            if ar.verdict:
                verdict_parts.append(ar.verdict)
        verdict_str = f" ({', '.join(verdict_parts)})" if verdict_parts else ""
        rprint(f"    {sr.step_name}: {sr.status.value}{verdict_str}")


# ---------------------------------------------------------------------------
# Typer command
# ---------------------------------------------------------------------------


def run(
    pipeline: str | None = typer.Argument(
        None, help="Pipeline name or path to YAML definition."
    ),
    target: str | None = typer.Argument(
        None,
        help="Target for the pipeline's primary required param (e.g. slice index).",
    ),
    model: str | None = typer.Option(None, "--model", "-m", help="Model override."),
    param: list[str] | None = typer.Option(
        None, "--param", "-p", help="Additional param as key=value."
    ),
    from_step: str | None = typer.Option(
        None, "--from", help="Start execution from this step."
    ),
    resume: str | None = typer.Option(
        None, "--resume", "-r", help="Resume a paused run by run-id."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show plan without executing."
    ),
    validate_only: bool = typer.Option(
        False, "--validate", help="Validate pipeline and exit."
    ),
    list_pipelines: bool = typer.Option(
        False, "--list", "-l", help="List available pipelines."
    ),
    status: str | None = typer.Option(
        None, "--status", help="Show run status. Use 'latest' for most recent."
    ),
) -> None:
    """Execute, inspect, and manage pipeline runs."""
    # ---- mutual exclusivity validation ----
    if resume is not None and from_step is not None:
        rprint("[red]Error: --resume and --from cannot be used together.[/red]")
        raise typer.Exit(1)

    if list_pipelines and any(
        [pipeline, model, from_step, resume, dry_run, validate_only, status]
    ):
        rprint("[red]Error: --list cannot be combined with other options.[/red]")
        raise typer.Exit(1)

    if status is not None and any(
        [pipeline, model, from_step, resume, dry_run, validate_only]
    ):
        rprint("[red]Error: --status cannot be combined with execution options.[/red]")
        raise typer.Exit(1)

    if not list_pipelines and status is None and resume is None and pipeline is None:
        rprint(
            "[red]Error: pipeline argument is required"
            " unless using --list, --status, or --resume.[/red]"
        )
        raise typer.Exit(1)

    # ---- --list ----
    if list_pipelines:
        pipelines = discover_pipelines()
        table = Table(title="Available Pipelines")
        table.add_column("Name", style="bold")
        table.add_column("Description")
        table.add_column("Source")
        for p in pipelines:
            table.add_row(p.name, p.description, p.source)
        rprint(table)
        raise typer.Exit(0)

    # ---- --status ----
    if status is not None:
        state_mgr = StateManager()
        if status == "latest":
            runs = state_mgr.list_runs()
            if not runs:
                rprint("No runs found.")
                raise typer.Exit(0)
            _display_run_status(runs[0])
        else:
            try:
                state = state_mgr.load(status)
            except FileNotFoundError:
                rprint(f"[red]Error: Run '{status}' not found.[/red]")
                raise typer.Exit(1)
            except SchemaVersionError as exc:
                rprint(f"[red]Error: {exc}[/red]")
                raise typer.Exit(1)
            _display_run_status(state)
        raise typer.Exit(0)

    # ---- --validate ----
    if validate_only:
        assert pipeline is not None  # guarded above
        try:
            definition = load_pipeline(pipeline)
        except FileNotFoundError:
            rprint(f"[red]Error: Pipeline '{pipeline}' not found.[/red]")
            raise typer.Exit(1)
        errors = validate_pipeline(definition)
        if not errors:
            rprint(
                f"[bright_green]Pipeline '{definition.name}' is valid.[/bright_green]"
            )
            raise typer.Exit(0)
        rprint(f"[red]Validation errors for '{definition.name}':[/red]")
        for err in errors:
            rprint(f"  {err.field}: {err.message}")
        raise typer.Exit(1)

    # ---- --dry-run ----
    if dry_run:
        assert pipeline is not None  # guarded above
        try:
            definition = load_pipeline(pipeline)
        except FileNotFoundError:
            rprint(f"[red]Error: Pipeline '{pipeline}' not found.[/red]")
            raise typer.Exit(1)

        errors = validate_pipeline(definition)
        if errors:
            rprint(f"[red]Validation errors for '{definition.name}':[/red]")
            for err in errors:
                rprint(f"  {err.field}: {err.message}")
            raise typer.Exit(1)

        params = _assemble_params(definition, target, model, param)
        rprint(f"\n[bold]Pipeline:[/bold] {definition.name}")
        rprint(f"[bold]Description:[/bold] {definition.description}")
        rprint(f"[bold]Params:[/bold] {params}")
        rprint("\n[bold]Steps:[/bold]")
        for step in definition.steps:
            rprint(f"  {step.name} ({step.step_type})")
        raise typer.Exit(0)

    # ---- --resume ----
    if resume is not None:
        state_mgr = StateManager()
        try:
            state = state_mgr.load(resume)
        except FileNotFoundError:
            rprint(f"[red]Error: Run '{resume}' not found.[/red]")
            raise typer.Exit(1)
        except SchemaVersionError as exc:
            rprint(f"[red]Error: {exc}[/red]")
            raise typer.Exit(1)

        try:
            definition = load_pipeline(state.pipeline)
        except FileNotFoundError:
            rprint(f"[red]Error: Pipeline '{state.pipeline}' not found.[/red]")
            raise typer.Exit(1)

        next_step = state_mgr.first_unfinished_step(resume, definition)
        if next_step is None:
            rprint("[yellow]All steps already completed. Nothing to resume.[/yellow]")
            raise typer.Exit(0)

        resume_model = (
            model or str(state.params.get("model"))
            if state.params.get("model")
            else model
        )
        resolver = ModelResolver(
            cli_override=resume_model,
            pipeline_model=definition.model,
        )
        cf_client = ContextForgeClient()
        _check_cf(cf_client)

        run_id = resume
        try:
            result = asyncio.run(
                execute_pipeline(
                    definition,
                    dict(state.params),
                    resolver=resolver,
                    cf_client=cf_client,
                    run_id=run_id,
                    start_from=next_step,
                    on_step_complete=state_mgr.make_step_callback(run_id),
                )
            )
        except KeyboardInterrupt:
            rprint("\n[yellow]Interrupted. Run state saved.[/yellow]")
            rprint(f"Resume with: [bold]sq run --resume {run_id}[/bold]")
            raise typer.Exit(1)

        state_mgr.finalize(run_id, result)
        _display_result(result)
        raise typer.Exit(0)

    # ---- standard execution ----
    assert pipeline is not None  # guarded above

    try:
        definition = load_pipeline(pipeline)
    except FileNotFoundError:
        rprint(f"[red]Error: Pipeline '{pipeline}' not found.[/red]")
        raise typer.Exit(1)

    params = _assemble_params(definition, target, model, param)

    # Implicit resume detection
    state_mgr = StateManager()
    if sys.stdin.isatty():
        match = state_mgr.find_matching_run(pipeline, params, status="paused")
        if match is not None:
            if typer.confirm(
                f"Found a paused run ({match.run_id}). Resume?", default=True
            ):
                next_step = state_mgr.first_unfinished_step(match.run_id, definition)
                if next_step is not None:
                    try:
                        result = asyncio.run(
                            _run_pipeline(
                                pipeline,
                                params,
                                model_override=model,
                                from_step=next_step,
                            )
                        )
                    except KeyboardInterrupt:
                        rprint("\n[yellow]Interrupted. Run state saved.[/yellow]")
                        rprint(
                            f"Resume with: [bold]sq run --resume {match.run_id}[/bold]"
                        )
                        raise typer.Exit(1)

                    _display_result(result)
                    raise typer.Exit(0)

    # Fresh run
    try:
        result = asyncio.run(
            _run_pipeline(
                pipeline,
                params,
                model_override=model,
                from_step=from_step,
            )
        )
    except FileNotFoundError:
        # Already printed by _run_pipeline
        raise typer.Exit(1)
    except KeyboardInterrupt:
        rprint("\n[yellow]Interrupted. Run state saved as failed.[/yellow]")
        rprint("Resume with: [bold]sq run --resume <run-id>[/bold]")
        raise typer.Exit(1)

    _display_result(result)
