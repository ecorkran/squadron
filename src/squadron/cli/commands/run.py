"""run command — execute, inspect, and manage pipeline runs."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections.abc import Coroutine
from contextlib import AbstractAsyncContextManager, ExitStack, nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

import typer
import yaml
from pydantic import ValidationError
from rich import print as rprint
from rich.markup import escape
from rich.table import Table

if TYPE_CHECKING:
    from squadron.pipeline.intelligence.pools.backend import PoolBackend

from squadron.cli.commands.run_dry_run import render_steps
from squadron.cli.commands.run_item import check_item_flags, handle_item_resume
from squadron.cli.run_views import render_run_status, status_color
from squadron.events import EventType, bootstrap_event_actions
from squadron.events.contexts import PostActionContext
from squadron.events.discovery import PluginLoadError
from squadron.events.dispatcher import OutcomeErrorKind, run_event
from squadron.events.manifest import ManifestError
from squadron.integrations.context_forge import (
    ContextForgeClient,
    ContextForgeError,
    ContextForgeNotAvailable,
)
from squadron.pipeline.batch_report import BatchReport, ItemDecision, ItemRerun
from squadron.pipeline.classification import (
    ClassificationError,
    PipelineClassification,
    PipelineShape,
    PoolClassificationPolicy,
    StepClass,
    classify_pipeline,
    has_profile_param,
)
from squadron.pipeline.control_params import reserved_param_error
from squadron.pipeline.executor import (
    ExecutionStatus,
    LazySessionConnectError,
    PipelineResult,
    execute_pipeline,
    resolve_placeholders,
)
from squadron.pipeline.git_ops import GitEnvironmentError
from squadron.pipeline.intelligence.pools.backend import DefaultPoolBackend
from squadron.pipeline.intelligence.pools.models import PoolNotFoundError
from squadron.pipeline.loader import (
    load_pipeline,
    pipeline_file_path,
    pipeline_identity,
    validate_pipeline,
)
from squadron.pipeline.models import ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.prompt_renderer import (
    CompletionResult,
    StepInstructions,
    render_step_instructions,
)
from squadron.pipeline.resolver import ModelPoolNotImplemented, ModelResolutionError, ModelResolver
from squadron.pipeline.run_heartbeat import RunHeartbeat, heartbeat_interval_s
from squadron.pipeline.run_lock import RunLockError, pipeline_mutates, project_run_lock
from squadron.pipeline.sdk_session import SDKExecutionSession, open_pipeline_session
from squadron.pipeline.state import (
    ExecutionMode,
    RunOwner,
    RunState,
    SchemaVersionError,
    StateManager,
)
from squadron.pipeline.steps.phase import PhaseStepType

_logger = logging.getLogger(__name__)

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
                raise typer.BadParameter(f"Pipeline '{definition.name}' requires a '{name}' argument.")
            return (name, target)
    return None


def _apply_param_overrides(params: dict[str, object], param_list: list[str] | None) -> None:
    """Apply ``--param key=value`` entries to *params* in place (they override defaults)."""
    for entry in param_list or []:
        key, _, value = entry.partition("=")
        if not key:
            raise typer.BadParameter(f"Invalid --param format: '{entry}'")
        if (reserved := reserved_param_error(key)) is not None:
            raise typer.BadParameter(reserved)
        params[key] = value


def _assemble_params(
    definition: PipelineDefinition,
    target: str | None,
    model: str | None,
    param_list: list[str] | None,
) -> dict[str, object]:
    """Build the runtime params dict from CLI inputs.

    - Starts with default parameters from the pipeline definition.
    - Binds the positional *target* to the first required pipeline param.
    - Parses ``--param key=value`` entries from *param_list* (overrides defaults).
    - Records *model* for state-file resume fidelity (not for model resolution).
    """
    # Start with pipeline defaults, excluding "required" markers
    params: dict[str, object] = {
        key: value for key, value in definition.params.items() if value != "required"
    }

    binding = _resolve_target(definition, target)
    if binding is not None:
        params[binding[0]] = binding[1]

    _apply_param_overrides(params, param_list)

    if model is not None:
        params["model"] = model

    return params


def _resolve_execution_mode(prompt_only: bool) -> ExecutionMode:
    """Determine pipeline execution mode from flags and environment.

    Returns:
        ``ExecutionMode.PROMPT_ONLY`` when ``--prompt-only`` is set.
        ``ExecutionMode.SDK`` when running from a standard terminal.

    Raises:
        typer.Exit(1): When invoked from inside a Claude Code session.
    """
    if prompt_only:
        return ExecutionMode.PROMPT_ONLY
    if os.environ.get("CLAUDECODE"):
        rprint(
            "[red]Error: SDK pipeline execution cannot run inside a Claude Code "
            "session.[/red]\n"
            "Use [bold]--prompt-only[/bold] mode or run from a standard terminal."
        )
        raise typer.Exit(1)
    return ExecutionMode.SDK


def _run_record_identity(pipeline_arg: str) -> tuple[str, str | None]:
    """The (name, absolute source path) a new run is recorded under (slice 940 D4).

    A file-path argument records the file's identity as the name and its
    absolute path; a pipeline name records itself and no path.
    """
    source_file = pipeline_file_path(pipeline_arg)
    if source_file is None:
        return pipeline_arg, None
    return pipeline_identity(source_file), str(source_file.resolve())


def _load_run_definition(state: RunState, *, file: TextIO) -> PipelineDefinition:
    """Reload the pipeline a recorded run belongs to, or exit 1 naming what failed.

    A path run reloads its recorded file; a missing file is an error, never a
    fallback to a same-named pipeline (slice 940 D4).
    """
    target = state.load_target
    try:
        return load_pipeline(target)
    except FileNotFoundError:
        rprint(f"[red]Error: Pipeline '{escape(target)}' not found.[/red]", file=file)
    except (ValidationError, yaml.YAMLError) as exc:
        rprint(
            f"[red]Error: Pipeline '{escape(target)}' failed to load: {escape(str(exc))}[/red]",
            file=file,
        )
    raise typer.Exit(1)


def _check_cf(cf_client: ContextForgeClient) -> None:
    """Verify that Context Forge is available before execution.

    Raises ``typer.Exit(1)`` with a clear message on failure.
    """
    try:
        cf_client.get_project()
    except ContextForgeNotAvailable:
        rprint(
            "[red]Error: Context Forge (cf) is not installed or not on PATH.[/red]\n"
            "Install it with: [bold]npm install -g @context-forge/cli[/bold]\n"
            "Then run: [bold]sq install-commands[/bold]"
        )
        raise typer.Exit(1) from None
    except ContextForgeError as exc:
        rprint(f"[red]Error: Context Forge pre-flight check failed — {escape(str(exc))}[/red]")
        raise typer.Exit(1) from None


def _resolve_resume_iteration(state_mgr: StateManager, run_id: str, step_name: str) -> int:
    """Look up the round to resume *step_name* at (slice 915 Part B).

    Single source for both resume entry points (--resume and implicit
    paused-run detection) so neither carries its own copy of the lookup.
    """
    return state_mgr.resume_iteration_for(run_id, step_name)


async def _run_pipeline(
    pipeline_name: str,
    params: dict[str, object],
    model_override: str | None = None,
    runs_dir: Path | None = None,
    from_step: str | None = None,
    from_iteration: int = 0,
    sdk_session: object | None = None,
    run_id: str | None = None,
    execution_mode: ExecutionMode = ExecutionMode.SDK,
    _action_registry: dict[str, object] | None = None,
    pool_backend: PoolBackend | None = None,
    pool_policy: PoolClassificationPolicy = PoolClassificationPolicy.LAZY,
    item_rerun: ItemRerun | None = None,
) -> PipelineResult:
    """Load, validate, and execute a pipeline end-to-end.

    This is the async core called from the sync ``run()`` Typer command via
    ``asyncio.run()``.  All dependency construction happens here so that
    integration tests can call this directly.

    When *run_id* is provided the existing state file is reused (resume path);
    ``init_run`` is skipped so no new state file is created.

    Raises ``FileNotFoundError`` when the pipeline cannot be found — the
    caller is responsible for printing the message and exiting.
    """
    definition = load_pipeline(pipeline_name)

    errors = validate_pipeline(definition)
    if errors:
        msg = "; ".join(f"{e.field}: {e.message}" for e in errors)
        raise ValueError(f"Pipeline '{pipeline_name}' has validation errors: {msg}")

    cf_client = ContextForgeClient()
    _check_cf(cf_client)

    state_mgr = StateManager(runs_dir=runs_dir)
    # SDK runs are owned and heartbeated (slice 174 D13); prompt-only runs stay unowned.
    sdk_run = execution_mode == ExecutionMode.SDK
    interval = heartbeat_interval_s() if sdk_run else None
    resuming = run_id is not None
    if run_id is None:
        owner = RunOwner.current(interval) if interval is not None else None
        run_name, run_path = _run_record_identity(pipeline_name)
        run_id = state_mgr.init_run(
            run_name, params, execution_mode=execution_mode, owner=owner, pipeline_path=run_path
        )

    _run_id = run_id  # capture for closure below
    if pool_backend is None:
        pool_backend = DefaultPoolBackend()
    resolver = ModelResolver(
        cli_override=model_override,
        pipeline_model=definition.model,
        pool_backend=pool_backend,
        on_pool_selection=lambda sel: state_mgr.log_pool_selection(_run_id, sel),
        profile_source=has_profile_param(params),
    )

    # A failed claim propagates before the try: the run was never ours to finalize.
    heartbeat: AbstractAsyncContextManager[object] = (
        RunHeartbeat(state_mgr, run_id, interval, claim=resuming)
        if interval is not None
        else nullcontext()
    )
    async with heartbeat:
        try:
            result = await execute_pipeline(
                definition,
                params,
                resolver=resolver,
                cf_client=cf_client,
                run_id=run_id,
                start_from=from_step,
                start_from_iteration=from_iteration,
                sdk_session=sdk_session,  # type: ignore[arg-type]
                pool_policy=pool_policy,
                observer=state_mgr.observer(run_id),
                runs_dir=runs_dir,
                item_rerun=item_rerun,
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


def _classify_for_run(
    definition: PipelineDefinition,
    *,
    model_override: str | None,
    params: dict[str, object],
    strict: bool,
) -> PipelineClassification:
    """Classify *definition* the one way every ``sq run`` path does.

    Owns the policy (YAML ``auth_policy`` < ``--strict``), the classification
    pool backend and resolver, and the ``classify_pipeline`` call, so a run,
    ``--explain`` and ``--dry-run`` cannot disagree. Raises ``ClassificationError``;
    each caller words its own message.
    """
    policy = PoolClassificationPolicy.LAZY
    if definition.auth_policy == PoolClassificationPolicy.STRICT or strict:
        policy = PoolClassificationPolicy.STRICT

    pool_backend = DefaultPoolBackend()
    resolver = ModelResolver(
        cli_override=model_override,
        pipeline_model=definition.model,
        pool_backend=pool_backend,
        profile_source=has_profile_param(params),
    )
    return classify_pipeline(definition, resolver, pool_backend, policy=policy, params=params)


async def _run_pipeline_sdk(
    pipeline_name: str,
    params: dict[str, object],
    model_override: str | None = None,
    runs_dir: Path | None = None,
    from_step: str | None = None,
    from_iteration: int = 0,
    run_id: str | None = None,
    strict: bool = False,
    item_rerun: ItemRerun | None = None,
) -> PipelineResult:
    """Create an SDK session if needed, run the pipeline, and disconnect on exit.

    Classifies the pipeline before session construction; only pipelines whose
    steps require a persistent Claude session will construct and connect an
    ``SDKExecutionSession``.  Non-SDK pipelines pass ``sdk_session=None`` to
    ``execute_pipeline``.

    When *run_id* is provided the existing run state is reused (resume path).

    When *strict* is True (or the pipeline YAML has ``auth_policy: strict``),
    POOL_UNCERTAIN steps are treated as SDK-required and a session is connected
    at startup.  The default LAZY behaviour skips upfront connection for
    uncertain steps and relies on the mid-run hook instead.

    Raises typer.Exit(1) when running inside a Claude Code session or when
    pipeline classification fails.  The session is disconnected in a ``finally``
    block so cleanup happens on success, failure, checkpoint pause, and
    keyboard interrupt.
    """
    _resolve_execution_mode(prompt_only=False)

    # Validate before classification — fail fast on bad YAML
    definition = load_pipeline(pipeline_name)
    errors = validate_pipeline(definition)
    if errors:
        msg = "; ".join(f"{e.field}: {e.message}" for e in errors)
        raise ValueError(f"Pipeline '{pipeline_name}' has validation errors: {msg}")

    try:
        classification = _classify_for_run(
            definition, model_override=model_override, params=params, strict=strict
        )
    except ClassificationError as exc:
        rprint(f"[red]Error: Pipeline classification failed — {escape(str(exc))}[/red]")
        raise typer.Exit(1) from None

    # The authoritative resolver built inside _run_pipeline shares this backend
    # with the executor; classification used its own (it never calls select()).
    pool_backend = DefaultPoolBackend()

    _logger.info(
        "pipeline '%s' shape: %s (%d classified steps)",
        pipeline_name,
        classification.shape,
        len(classification.steps),
    )
    for step in classification.steps:
        _logger.debug(
            "  step '%s' [%s]: %s (alias '%s' → profile '%s')",
            step.step_name,
            step.action_type,
            step.classification,
            step.resolved_alias,
            step.profile,
        )

    session: SDKExecutionSession | None
    if classification.needs_persistent_session:
        session = await open_pipeline_session()
    else:
        session = None

    try:
        result = await _run_pipeline(
            pipeline_name,
            params,
            model_override=model_override,
            runs_dir=runs_dir,
            from_step=from_step,
            from_iteration=from_iteration,
            sdk_session=session,
            run_id=run_id,
            execution_mode=ExecutionMode.SDK,
            pool_backend=pool_backend,
            pool_policy=classification.policy,
            item_rerun=item_rerun,
        )
    except LazySessionConnectError as exc:
        # State is already saved by _run_pipeline's BaseException handler.
        # Surface a user-friendly error pointing to --strict.
        _run_id = run_id or "unknown"
        rprint(
            f"[red]Error: Claude auth required — connection failed mid-run"
            f" at step '{escape(str(exc.step_name))}'.[/red]\n"
            f"Run state saved. Resume with: sq run --resume {_run_id}"
        )
        raise typer.Exit(1) from exc
    except GitEnvironmentError as exc:
        if item_rerun is not None:
            raise  # item resume reports it as HALTED (slice 197 D8)
        # A git fault that every later item would hit too (wrong branch, dirty tree,
        # unknown state) ends the run. State is saved; the operator fixes the checkout.
        _logger.error("pipeline '%s' halted by a git environment fault: %s", pipeline_name, exc)
        rprint(f"[red]Error: {escape(str(exc))}[/red]")
        raise typer.Exit(1) from exc
    finally:
        if session is not None:
            await session.disconnect()

    return result


# ---------------------------------------------------------------------------
# Explain helpers
# ---------------------------------------------------------------------------

_SHAPE_LABELS: dict[PipelineShape, str] = {
    PipelineShape.CLAUDE_REQUIRED_PERSISTENT: "Claude-required (persistent)",
    PipelineShape.CLAUDE_REQUIRED_ONE_SHOT: "Claude-required (one-shot only)",
    PipelineShape.CLAUDE_FREE: "Claude-free",
}

_STEP_CLASS_COLORS: dict[StepClass, str] = {
    StepClass.SDK_REQUIRED: "yellow",
    StepClass.NON_SDK: "green",
    StepClass.POOL_UNCERTAIN: "magenta",
}


def _render_explain(classification: PipelineClassification) -> None:
    """Render a Rich table of per-step classification and a summary panel."""
    table = Table(title=f"Pipeline: {classification.pipeline_name}")
    table.add_column("Step", style="bold")
    table.add_column("Action")
    table.add_column("Alias")
    table.add_column("Model ID")
    table.add_column("Profile")
    table.add_column("Classification")
    table.add_column("Rationale")

    # Track which container step names have already had a header row emitted.
    emitted_container_headers: set[str] = set()

    for step in classification.steps:
        if step.container_path is not None and step.step_name not in emitted_container_headers:
            # Emit a dim header row for the container step itself.
            table.add_row(
                f"[dim]{step.step_name}[/dim]",
                "—",
                "—",
                "—",
                "—",
                "[dim](container)[/dim]",
                "—",
            )
            emitted_container_headers.add(step.step_name)

        color = _STEP_CLASS_COLORS[step.classification]
        cls_val = f"[{color}]{step.classification.value}[/{color}]"
        step_label = f"  ↳ {step.container_path}" if step.container_path is not None else step.step_name
        table.add_row(
            step_label,
            step.action_type,
            step.resolved_alias or "—",
            step.resolved_model_id or "—",
            step.profile or "—",
            cls_val,
            step.rationale,
        )

    rprint(table)

    policy_label = (
        "strict" if classification.policy == PoolClassificationPolicy.STRICT else "lazy (default)"
    )
    rprint(f"[bold]Pipeline shape:[/bold]           {_SHAPE_LABELS[classification.shape]}")
    rprint(f"[bold]Pool policy:[/bold]              {policy_label}")
    needs_session = "yes" if classification.needs_persistent_session else "no"
    needs_one_shot = "yes" if classification.needs_one_shot_claude else "no"
    rprint(f"[bold]Needs persistent session:[/bold] {needs_session}")
    rprint(f"[bold]Needs one-shot Claude:[/bold]    {needs_one_shot}")


def _extract_model_override(model: str | None, param: list[str] | None) -> str | None:
    """Extract the effective model override from --model and --param flags.

    --model takes precedence; otherwise scans --param for a 'model=<value>' entry.
    """
    if model is not None:
        return model
    if param:
        for entry in param:
            key, _, value = entry.partition("=")
            if key == "model" and value:
                return value
    return None


def _handle_explain(
    pipeline_name: str,
    model_override: str | None,
    param: list[str] | None,
    strict: bool,
) -> None:
    """Load, classify, and render explain output for *pipeline_name*."""
    try:
        definition = load_pipeline(pipeline_name)
    except FileNotFoundError:
        rprint(f"[red]Error: Pipeline '{escape(str(pipeline_name))}' not found.[/red]")
        raise typer.Exit(1) from None

    errors = validate_pipeline(definition)
    if errors:
        for err in errors:
            rprint(f"[red]{escape(str(err.field))}: {escape(str(err.message))}[/red]")
        raise typer.Exit(1)

    cli_override = _extract_model_override(model_override, param)

    # Explain has no target, so the merged params are defaults plus overrides.
    explain_params: dict[str, object] = {
        key: value for key, value in definition.params.items() if value != "required"
    }
    _apply_param_overrides(explain_params, param)

    try:
        classification = _classify_for_run(
            definition, model_override=cli_override, params=explain_params, strict=strict
        )
    except ClassificationError as exc:
        rprint(f"[red]Error: Classification failed — {escape(str(exc))}[/red]")
        raise typer.Exit(1) from None

    _render_explain(classification)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _exit_code(result: PipelineResult) -> int:
    """Process exit code for a finished run: 1 when the pipeline failed.

    A paused run (checkpoint) is not a failure; it exits 0 with resume
    instructions already printed.
    """
    return 1 if result.status == ExecutionStatus.FAILED else 0


def _display_result(result: PipelineResult) -> None:
    """Print a brief final summary of a completed pipeline run."""
    color = status_color(result.status.value)
    name = result.pipeline_name
    rprint(f"\n[{color}]Pipeline '{escape(str(name))}' — {result.status.value}[/{color}]")
    rprint(f"  Steps: {len(result.step_results)}")

    for sr in result.step_results:
        verdict_parts: list[str] = []
        error_msg: str | None = None
        for ar in sr.action_results:
            if ar.verdict:
                verdict_parts.append(ar.verdict)
            if ar.error and not error_msg:
                error_msg = ar.error
        verdict_str = f" ({', '.join(verdict_parts)})" if verdict_parts else ""
        rprint(f"    {escape(str(sr.step_name))}: {sr.status.value}{verdict_str}")
        if error_msg:
            rprint(f"      [red]Error: {escape(str(error_msg))}[/red]")

    for sr in result.step_results:
        if sr.batch_report is not None:
            _display_batch_report(sr.batch_report)


def _display_batch_report(report: BatchReport) -> None:
    """One line of counts, the flagged items, and where the report is (D9)."""
    rprint(f"\n[bold]{escape(report.summary_line())}[/bold]")
    for record in report.flagged():
        rprint(f"  [yellow]FLAGGED[/yellow] {escape(record.render_line()[2:])}")
    if report.written_to is not None:
        json_path = report.json_path(report.written_to.parent)
        rprint(f"  Report: {escape(str(report.written_to))}  JSON: {escape(str(json_path))}")


# ---------------------------------------------------------------------------
# Prompt-only handlers
# ---------------------------------------------------------------------------


def _render_prompt_only_step(
    step: StepConfig,
    *,
    step_index: int,
    total_steps: int,
    params: dict[str, object],
    resolver: ModelResolver,
    run_id: str,
    verbosity: int,
) -> StepInstructions:
    """Render one prompt-only step, converting resolver failures to a clean CLI exit.

    CLI process boundary for both ``--prompt-only`` entry points. A misconfigured
    model alias or ``pool:`` reference in the step config raises out of
    ``render_step_instructions`` (the renderer deliberately does not swallow it);
    here it is logged and rendered as ``Error: ...`` + exit 1 rather than a
    traceback, matching ``dispatch_run`` / ``spawn`` / ``summary_run``.
    """
    try:
        return render_step_instructions(
            step,
            step_index=step_index,
            total_steps=total_steps,
            params=params,
            resolver=resolver,
            run_id=run_id,
            verbosity=verbosity,
        )
    except (ModelResolutionError, ModelPoolNotImplemented, PoolNotFoundError) as exc:
        _logger.exception("prompt-only: model resolution failed for step %r", step.name)
        rprint(f"[red]Error: model resolution failed — {escape(str(exc))}[/red]", file=sys.stderr)
        raise typer.Exit(1) from None


def _handle_prompt_only_init(
    pipeline_name: str,
    target: str | None,
    model_override: str | None,
    param_list: list[str] | None,
    verbosity: int = 0,
) -> None:
    """Initialize a prompt-only run and emit the first step's JSON."""
    try:
        definition = load_pipeline(pipeline_name)
    except FileNotFoundError:
        rprint(
            f"[red]Error: Pipeline '{pipeline_name}' not found.[/red]",
            file=sys.stderr,
        )
        raise typer.Exit(1) from None

    errors = validate_pipeline(definition)
    if errors:
        rprint(
            f"[red]Validation errors for '{definition.name}':[/red]",
            file=sys.stderr,
        )
        for err in errors:
            rprint(f"  {escape(str(err.field))}: {escape(str(err.message))}", file=sys.stderr)
        raise typer.Exit(1)

    params = _assemble_params(definition, target, model_override, param_list)
    state_mgr = StateManager()
    run_name, run_path = _run_record_identity(pipeline_name)
    run_id = state_mgr.init_run(
        run_name, params, execution_mode=ExecutionMode.PROMPT_ONLY, pipeline_path=run_path
    )
    rprint(f"run_id={escape(str(run_id))}", file=sys.stderr)

    pool_backend = DefaultPoolBackend()
    resolver = ModelResolver(
        cli_override=model_override,
        pipeline_model=definition.model,
        pool_backend=pool_backend,
        on_pool_selection=lambda sel: state_mgr.log_pool_selection(run_id, sel),
        profile_source=has_profile_param(params),
    )

    # Render first step
    first_step = definition.steps[0]
    instructions = _render_prompt_only_step(
        first_step,
        step_index=0,
        total_steps=len(definition.steps),
        params=params,
        resolver=resolver,
        run_id=run_id,
        verbosity=verbosity,
    )
    print(instructions.to_json())


def _handle_prompt_only_next(
    run_id: str,
    model_override: str | None,
    verbosity: int = 0,
) -> None:
    """Emit the next unfinished step's JSON for an existing run."""
    state_mgr = StateManager()
    try:
        state = state_mgr.load(run_id)
    except FileNotFoundError:
        rprint(
            f"[red]Error: Run '{run_id}' not found.[/red]",
            file=sys.stderr,
        )
        raise typer.Exit(1) from None
    except SchemaVersionError as exc:
        rprint(f"[red]Error: {escape(str(exc))}[/red]", file=sys.stderr)
        raise typer.Exit(1) from None

    definition = _load_run_definition(state, file=sys.stderr)

    next_name = state_mgr.first_unfinished_step(run_id, definition)
    if next_name is None:
        # All done — finalize and return completion
        from squadron.pipeline.executor import PipelineResult

        state_mgr.finalize(
            run_id,
            PipelineResult(
                pipeline_name=state.pipeline,
                status=ExecutionStatus.COMPLETED,
                step_results=[],
            ),
        )
        result = CompletionResult(
            status="completed",
            message="All steps complete",
            run_id=run_id,
        )
        print(result.to_json())
        return

    # Find the step config and its index
    step_index = 0
    step_config = None
    for i, step in enumerate(definition.steps):
        if step.name == next_name:
            step_index = i
            step_config = step
            break

    if step_config is None:
        rprint(
            f"[red]Error: Step '{next_name}' not found in pipeline.[/red]",
            file=sys.stderr,
        )
        raise typer.Exit(1)

    resume_model = (
        model_override or str(state.params.get("model"))
        if state.params.get("model")
        else model_override
    )
    pool_backend = DefaultPoolBackend()
    resolver = ModelResolver(
        cli_override=resume_model,
        pipeline_model=definition.model,
        pool_backend=pool_backend,
        on_pool_selection=lambda sel: state_mgr.log_pool_selection(run_id, sel),
        profile_source=has_profile_param(state.params),
    )
    params = dict(state.params)

    instructions = _render_prompt_only_step(
        step_config,
        step_index=step_index,
        total_steps=len(definition.steps),
        params=params,
        resolver=resolver,
        run_id=run_id,
        verbosity=verbosity,
    )
    print(instructions.to_json())


async def _run_post_action_bindings_for_step_done(
    *,
    run_id: str,
    state: RunState,
    step: StepConfig,
) -> str | None:
    """Run POST_ACTION bindings for every action a prompt-only step expands to.

    Design D9: this is the prompt-only parity for the in-process executor's
    per-action POST_ACTION dispatch (issue #15/909). ``outputs`` is always
    ``{}`` (an honest reading of what --step-done asserts — no in-process
    result to inspect). Stops at the first failing action and returns its
    attributed message; ``None`` means every binding passed.
    """
    from squadron.pipeline.steps import bootstrap_step_types, get_step_type

    bootstrap_step_types()
    bootstrap_event_actions()

    cf_client = ContextForgeClient()
    cwd = os.getcwd()

    step_type_impl = get_step_type(step.step_type)
    expected_kind = (
        step_type_impl.expected_artifact_kind if isinstance(step_type_impl, PhaseStepType) else None
    )
    actions = step_type_impl.expand(step)

    for action_type, action_config in actions:
        resolved_action_config = resolve_placeholders(action_config, state.params)
        result = ActionResult(success=True, action_type=action_type, outputs={})
        context = PostActionContext(
            event=EventType.POST_ACTION,
            cwd=cwd,
            params=resolved_action_config,
            action_type=action_type,
            result=result,
            run_id=run_id,
            run_started_at=state.started_at,
            run_state_error=None,
            step_name=step.name,
            step_type=step.step_type,
            expected_artifact_kind=expected_kind,
            iteration=0,
            cf_client=cf_client,
        )
        outcomes = await run_event(context)
        for outcome in outcomes:
            if outcome.result is not None and not outcome.result.success:
                return f"{outcome.action_name}: {outcome.result.error}"
            if outcome.error_kind is not OutcomeErrorKind.NONE:
                return f"{outcome.action_name}: {outcome.error_kind.value}"

    return None


def _handle_step_done(
    run_id: str,
    verdict: str | None,
) -> None:
    """Mark the current step complete in a prompt-only run."""
    state_mgr = StateManager()
    try:
        state = state_mgr.load(run_id)
    except FileNotFoundError:
        rprint(
            f"[red]Error: Run '{run_id}' not found.[/red]",
            file=sys.stderr,
        )
        raise typer.Exit(1) from None
    except SchemaVersionError as exc:
        rprint(f"[red]Error: {escape(str(exc))}[/red]", file=sys.stderr)
        raise typer.Exit(1) from None

    definition = _load_run_definition(state, file=sys.stderr)

    next_name = state_mgr.first_unfinished_step(run_id, definition)
    if next_name is None:
        rprint("[yellow]All steps already completed.[/yellow]")
        return

    # Find step config from definition
    step_config: StepConfig | None = None
    for step in definition.steps:
        if step.name == next_name:
            step_config = step
            break

    step_type = step_config.step_type if step_config is not None else "unknown"

    if step_config is not None:
        try:
            failure = asyncio.run(
                _run_post_action_bindings_for_step_done(run_id=run_id, state=state, step=step_config)
            )
        except (PluginLoadError, ManifestError) as exc:
            rprint(f"[red]Error: {escape(str(exc))}[/red]", file=sys.stderr)
            raise typer.Exit(1) from exc

        if failure is not None:
            rprint(f"[red]Error: {escape(str(failure))}[/red]", file=sys.stderr)
            raise typer.Exit(1)

    state_mgr.record_step_done(run_id, next_name, step_type, verdict=verdict)
    rprint(f"Step '{escape(str(next_name))}' marked complete.", file=sys.stderr)


# ---------------------------------------------------------------------------
# Typer command
# ---------------------------------------------------------------------------


def _take_run_lock(stack: ExitStack, definition: PipelineDefinition) -> None:
    """Hold the project run lock for the run when the pipeline mutates (slice 197 D11).

    Any failure to take it exits 2: nothing ran. The cause is already logged at ERROR.
    """
    if not pipeline_mutates(definition):
        return
    try:
        stack.enter_context(project_run_lock(os.getcwd()))
    except (GitEnvironmentError, RunLockError) as exc:
        rprint(f"[red]Error: {escape(str(exc))}[/red]")
        raise typer.Exit(2) from None


def _locked(
    definition: PipelineDefinition, run_coroutine: Coroutine[Any, Any, PipelineResult]
) -> PipelineResult:
    """Run *run_coroutine* holding the project run lock when the pipeline mutates."""
    with ExitStack() as lock:
        try:
            _take_run_lock(lock, definition)
        except typer.Exit:
            run_coroutine.close()  # never started; close it so it is not left unawaited
            raise
        return asyncio.run(run_coroutine)


def run(
    pipeline: str | None = typer.Argument(None, help="Pipeline name or path to YAML definition."),
    target: str | None = typer.Argument(
        None,
        help="Target for the pipeline's primary required param (e.g. slice index).",
    ),
    model: str | None = typer.Option(None, "--model", "-m", help="Model override."),
    param: list[str] | None = typer.Option(
        None, "--param", "-p", help="Additional param as key=value."
    ),
    from_step: str | None = typer.Option(None, "--from", help="Start execution from this step."),
    resume: str | None = typer.Option(None, "--resume", "-r", help="Resume a paused run by run-id."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan without executing."),
    validate_only: bool = typer.Option(False, "--validate", help="Validate pipeline and exit."),
    status: str | None = typer.Option(
        None, "--status", help="Show run status. Use 'latest' for most recent."
    ),
    prompt_only: bool = typer.Option(
        False,
        "--prompt-only",
        help="Output step instructions as JSON without executing.",
    ),
    next_step: bool = typer.Option(
        False,
        "--next",
        help="Emit next unfinished step (requires --prompt-only --resume).",
    ),
    step_done: str | None = typer.Option(
        None,
        "--step-done",
        help="Mark current step complete for a run-id.",
    ),
    verdict: str | None = typer.Option(
        None,
        "--verdict",
        help="Review verdict for --step-done (PASS, CONCERNS, FAIL).",
    ),
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help="Verbosity (-v for action summaries, -vv for full details).",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Force eager session construction for pool-uncertain steps.",
    ),
    explain: bool = typer.Option(
        False,
        "--explain",
        help="Print pipeline classification and exit without executing.",
    ),
    item: str | None = typer.Option(
        None, "--item", help="With --resume: rerun one item of a batch run, by its index."
    ),
    decision: ItemDecision | None = typer.Option(
        None, "--decision", help="With --item: retry the item, or accept its review."
    ),
    instructions: str | None = typer.Option(
        None, "--instructions", help="With --item: instructions prepended to its dispatches."
    ),
) -> None:
    """Execute, inspect, and manage pipeline runs."""
    # ---- mutual exclusivity validation ----
    check_item_flags(resume, item, decision, instructions)
    if resume is not None and from_step is not None:
        rprint("[red]Error: --resume and --from cannot be used together.[/red]")
        raise typer.Exit(1)

    if prompt_only and dry_run:
        rprint("[red]Error: --prompt-only and --dry-run cannot be used together.[/red]")
        raise typer.Exit(1)

    if next_step and not (prompt_only and resume):
        rprint("[red]Error: --next requires both --prompt-only and --resume.[/red]")
        raise typer.Exit(1)

    if step_done is not None and any([prompt_only, dry_run]):
        rprint("[red]Error: --step-done cannot be combined with --prompt-only or --dry-run.[/red]")
        raise typer.Exit(1)

    if verdict is not None and step_done is None:
        rprint("[red]Error: --verdict requires --step-done.[/red]")
        raise typer.Exit(1)

    if explain and resume is not None:
        rprint("[red]Error: --explain cannot be combined with --resume.[/red]")
        raise typer.Exit(1)

    if explain and from_step is not None:
        rprint("[red]Error: --explain cannot be combined with --from.[/red]")
        raise typer.Exit(1)

    if explain and dry_run:
        rprint("[red]Error: --explain cannot be combined with --dry-run.[/red]")
        raise typer.Exit(1)

    if explain and prompt_only:
        rprint("[red]Error: --explain cannot be combined with --prompt-only.[/red]")
        raise typer.Exit(1)

    if explain and validate_only:
        rprint("[red]Error: --explain cannot be combined with --validate.[/red]")
        raise typer.Exit(1)

    if status is not None and any([pipeline, model, from_step, resume, dry_run, validate_only]):
        rprint("[red]Error: --status cannot be combined with execution options.[/red]")
        raise typer.Exit(1)

    # ---- configure logging verbosity ----
    if verbose > 0:
        pipeline_logger = logging.getLogger("squadron.pipeline")
        level = logging.DEBUG if verbose >= 2 else logging.INFO
        pipeline_logger.setLevel(level)
        if not pipeline_logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(logging.Formatter("%(message)s"))
            pipeline_logger.addHandler(handler)

    if status is None and resume is None and step_done is None and pipeline is None:
        rprint(
            "[red]Error: pipeline argument is required"
            " unless using --status, --resume, or --step-done.[/red]"
        )
        raise typer.Exit(1)

    # ---- --step-done ----
    if step_done is not None:
        _handle_step_done(step_done, verdict)
        raise typer.Exit(0)

    # ---- --prompt-only --next --resume ----
    if prompt_only and next_step and resume is not None:
        _handle_prompt_only_next(resume, model, verbosity=verbose)
        raise typer.Exit(0)

    # ---- --prompt-only (init) ----
    if prompt_only:
        if pipeline is None:
            rprint("[red]Error: pipeline argument is required for --prompt-only.[/red]")
            raise typer.Exit(1)
        _handle_prompt_only_init(pipeline.lower(), target, model, param, verbosity=verbose)
        raise typer.Exit(0)

    # ---- --status ----
    if status is not None:
        state_mgr = StateManager()
        if status == "latest":
            runs = state_mgr.list_runs()
            if not runs:
                rprint("No runs found.")
                raise typer.Exit(0)
            render_run_status(runs[0])
        else:
            try:
                state = state_mgr.load(status)
            except FileNotFoundError:
                rprint(f"[red]Error: Run '{escape(str(status))}' not found.[/red]")
                raise typer.Exit(1) from None
            except SchemaVersionError as exc:
                rprint(f"[red]Error: {escape(str(exc))}[/red]")
                raise typer.Exit(1) from None
            render_run_status(state)
        raise typer.Exit(0)

    # ---- --validate ----
    if validate_only:
        assert pipeline is not None  # guarded above
        pipeline = pipeline.lower()
        try:
            definition = load_pipeline(pipeline)
        except FileNotFoundError:
            rprint(f"[red]Error: Pipeline '{escape(str(pipeline))}' not found.[/red]")
            raise typer.Exit(1) from None
        errors = validate_pipeline(definition)
        if not errors:
            rprint(f"[bright_green]Pipeline '{escape(str(definition.name))}' is valid.[/bright_green]")
            raise typer.Exit(0)
        rprint(f"[red]Validation errors for '{escape(str(definition.name))}':[/red]")
        for err in errors:
            rprint(f"  {escape(str(err.field))}: {escape(str(err.message))}")
        raise typer.Exit(1)

    # ---- --explain ----
    if explain:
        if pipeline is None:
            rprint("[red]Error: pipeline argument is required for --explain.[/red]")
            raise typer.Exit(1)
        _handle_explain(pipeline.lower(), model, param, strict)
        raise typer.Exit(0)

    # ---- --dry-run ----
    if dry_run:
        assert pipeline is not None  # guarded above
        pipeline = pipeline.lower()
        try:
            definition = load_pipeline(pipeline)
        except FileNotFoundError:
            rprint(f"[red]Error: Pipeline '{escape(str(pipeline))}' not found.[/red]")
            raise typer.Exit(1) from None

        errors = validate_pipeline(definition)
        if errors:
            rprint(f"[red]Validation errors for '{escape(str(definition.name))}':[/red]")
            for err in errors:
                rprint(f"  {escape(str(err.field))}: {escape(str(err.message))}")
            raise typer.Exit(1)

        params = _assemble_params(definition, target, model, param)
        # The same pre-run check a real run applies, so a typo'd alias or template
        # fails here instead of rendering a plan that cannot run (#175).
        try:
            _classify_for_run(
                definition,
                model_override=_extract_model_override(model, param),
                params=params,
                strict=strict,
            )
        except ClassificationError as exc:
            rprint(f"[red]Error: Pipeline classification failed — {escape(str(exc))}[/red]")
            raise typer.Exit(1) from None
        rprint(f"\n[bold]Pipeline:[/bold] {escape(str(definition.name))}")
        rprint(f"[bold]Description:[/bold] {escape(str(definition.description))}")
        rprint(f"[bold]Params:[/bold] {escape(str(params))}")
        rprint("\n[bold]Steps:[/bold]")
        render_steps(definition.steps, params, ContextForgeClient(), cwd=os.getcwd())
        raise typer.Exit(0)

    # ---- --resume --item (slice 197 D8) ----
    if resume is not None and item is not None:
        assert decision is not None  # check_item_flags
        overrides: dict[str, object] = {}
        _apply_param_overrides(overrides, param)  # rejects reserved keys
        handle_item_resume(
            resume, item, decision, instructions, model, overrides, strict, _run_pipeline_sdk
        )

    # ---- --resume ----
    if resume is not None:
        state_mgr = StateManager()
        try:
            state = state_mgr.load(resume)
        except FileNotFoundError:
            rprint(f"[red]Error: Run '{escape(str(resume))}' not found.[/red]")
            raise typer.Exit(1) from None
        except SchemaVersionError as exc:
            rprint(f"[red]Error: {escape(str(exc))}[/red]")
            raise typer.Exit(1) from None

        definition = _load_run_definition(state, file=sys.stdout)

        resume_from = state_mgr.first_unfinished_step(resume, definition)
        if resume_from is None:
            rprint("[yellow]All steps already completed. Nothing to resume.[/yellow]")
            raise typer.Exit(0)
        resume_iteration = _resolve_resume_iteration(state_mgr, resume, resume_from)

        resume_model = model or str(state.params.get("model")) if state.params.get("model") else model

        run_id = resume
        try:
            match state.execution_mode:
                case ExecutionMode.SDK:
                    result = _locked(
                        definition,
                        _run_pipeline_sdk(
                            state.pipeline,
                            dict(state.params),
                            model_override=resume_model,
                            run_id=run_id,
                            from_step=resume_from,
                            from_iteration=resume_iteration,
                            strict=strict,
                        ),
                    )
                case ExecutionMode.PROMPT_ONLY:
                    result = _locked(
                        definition,
                        _run_pipeline(
                            state.pipeline,
                            dict(state.params),
                            model_override=resume_model,
                            run_id=run_id,
                            from_step=resume_from,
                            from_iteration=resume_iteration,
                        ),
                    )
        except KeyboardInterrupt:
            rprint("\n[yellow]Interrupted. Run state saved.[/yellow]")
            rprint(f"Resume with: [bold]sq run --resume {escape(str(run_id))}[/bold]")
            raise typer.Exit(1) from None

        _display_result(result)
        raise typer.Exit(_exit_code(result))

    # ---- standard execution ----
    assert pipeline is not None  # guarded above
    pipeline = pipeline.lower()

    try:
        definition = load_pipeline(pipeline)
    except FileNotFoundError:
        rprint(f"[red]Error: Pipeline '{escape(str(pipeline))}' not found.[/red]")
        raise typer.Exit(1) from None

    params = _assemble_params(definition, target, model, param)

    # Implicit resume detection
    state_mgr = StateManager()
    if sys.stdin.isatty():
        match = state_mgr.find_matching_run(pipeline, params, status="paused")
        if match is not None:
            if typer.confirm(f"Found a paused run ({match.run_id}). Resume?", default=True):
                implicit_from = state_mgr.first_unfinished_step(match.run_id, definition)
                if implicit_from is not None:
                    implicit_iteration = _resolve_resume_iteration(
                        state_mgr, match.run_id, implicit_from
                    )
                    try:
                        match match.execution_mode:
                            case ExecutionMode.SDK:
                                result = _locked(
                                    definition,
                                    _run_pipeline_sdk(
                                        match.pipeline,
                                        dict(match.params),
                                        model_override=model,
                                        run_id=match.run_id,
                                        from_step=implicit_from,
                                        from_iteration=implicit_iteration,
                                        strict=strict,
                                    ),
                                )
                            case ExecutionMode.PROMPT_ONLY:
                                result = _locked(
                                    definition,
                                    _run_pipeline(
                                        match.pipeline,
                                        dict(match.params),
                                        model_override=model,
                                        run_id=match.run_id,
                                        from_step=implicit_from,
                                        from_iteration=implicit_iteration,
                                    ),
                                )
                    except KeyboardInterrupt:
                        rprint("\n[yellow]Interrupted. Run state saved.[/yellow]")
                        rprint(f"Resume with: [bold]sq run --resume {escape(str(match.run_id))}[/bold]")
                        raise typer.Exit(1) from None

                    _display_result(result)
                    raise typer.Exit(_exit_code(result))

    # Fresh run
    try:
        result = _locked(
            definition,
            _run_pipeline_sdk(
                pipeline,
                params,
                model_override=model,
                from_step=from_step,
                strict=strict,
            ),
        )
    except FileNotFoundError:
        # Already printed by _run_pipeline
        raise typer.Exit(1) from None
    except ValueError as exc:
        rprint(f"[red]Error: {escape(str(exc))}[/red]", file=sys.stderr)
        raise typer.Exit(1) from None
    except KeyboardInterrupt:
        rprint("\n[yellow]Interrupted. Run state saved as failed.[/yellow]")
        rprint("Resume with: [bold]sq run --resume <run-id>[/bold]")
        raise typer.Exit(1) from None

    _display_result(result)
    raise typer.Exit(_exit_code(result))
