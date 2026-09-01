"""Pipeline executor — runs a PipelineDefinition step by step.

Handles:
- Parameter merging and placeholder resolution
- Sequential step/action execution
- Retry loops with configurable exit conditions
- Checkpoint pause and action failure propagation
- `each` collection step execution (via source registry)
"""

from __future__ import annotations

import logging
import os
import re
import sys
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from squadron.events import EventType
from squadron.events.contexts import PostActionContext
from squadron.events.dispatcher import OutcomeErrorKind, run_event
from squadron.pipeline.classification import (
    PERSISTENT_SESSION_STEP_TYPES,
    PoolClassificationPolicy,
)
from squadron.pipeline.models import ActionContext, ActionResult, PipelineDefinition
from squadron.pipeline.steps import StepTypeName
from squadron.pipeline.steps.phase import PhaseStepType
from squadron.pipeline.steps.utils import unpack_inner_steps
from squadron.pipeline.summary_render import gather_cf_params

if TYPE_CHECKING:
    from squadron.integrations.context_forge import ContextForgeClient
    from squadron.pipeline.resolver import ModelResolver
    from squadron.pipeline.sdk_session import SDKExecutionSession

_logger = logging.getLogger(__name__)

__all__ = [
    "ExecutionStatus",
    "StepResult",
    "PipelineResult",
    "LoopCondition",
    "ExhaustBehavior",
    "LoopConfig",
    "CheckpointResolution",
    "CheckpointDecision",
    "LazySessionConnectError",
    "CHECKPOINT_KEY_ACCEPT",
    "CHECKPOINT_KEY_OVERRIDE",
    "CHECKPOINT_KEY_EXIT",
    "resolve_placeholders",
    "evaluate_condition",
    "execute_pipeline",
]

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------


def _summarize_action_config(action_type: str, config: dict[str, object]) -> str:
    """One-line summary of action config for verbose logging."""
    match action_type:
        case "cf-op":
            op = config.get("operation", "?")
            if op == "set_phase":
                return f"set_phase({config.get('phase', '?')})"
            if op == "set_slice":
                return f"set_slice({config.get('slice', '?')})"
            return str(op)
        case "dispatch":
            model = config.get("model", "default")
            return f"model={model}"
        case "review":
            tmpl = config.get("template", "?")
            model = config.get("model", "default")
            return f"template={tmpl}, model={model}"
        case "checkpoint":
            return f"trigger={config.get('trigger', '?')}"
        case "compact":
            return f"template={config.get('template', '?')}"
        case "commit":
            return f"prefix={config.get('message_prefix', '?')}"
        case _:
            return str(config) if config else ""


def _log_action_result(action_type: str, result: ActionResult) -> None:
    """Log action outcome at INFO (success/fail) and DEBUG (details)."""
    if result.success:
        extras: list[str] = []
        if result.verdict:
            extras.append(f"verdict={result.verdict}")
        if model := result.metadata.get("model"):
            extras.append(f"model={model}")
        # A step that was offered tools always renders a tools= segment, even at zero calls:
        # "offered three, called none" must read differently from "never had tools" (SC8).
        given = result.metadata.get("tools_given")
        if isinstance(given, list):
            made = result.metadata.get("tool_calls_made", 0)
            extras.append(f"tools={len(given)}/{made} calls")  # pyright: ignore[reportUnknownArgumentType]
        suffix = f" ({', '.join(extras)})" if extras else ""
        _logger.info("    -> ok%s", suffix)
    else:
        _logger.info("    -> FAILED: %s", result.error or "no details")

    _logger.debug("    outputs=%s metadata=%s", result.outputs, result.metadata)


# ---------------------------------------------------------------------------
# Result types and exceptions
# ---------------------------------------------------------------------------


class LazySessionConnectError(Exception):
    """Raised when the mid-run lazy session hook fails to connect.

    Carries the step name that triggered the connection attempt so callers
    can surface a step-specific error message.
    """

    def __init__(self, step_name: str, cause: BaseException) -> None:
        super().__init__(f"lazy session connect failed before step '{step_name}': {cause}")
        self.step_name = step_name
        self.cause = cause


class ExecutionStatus(StrEnum):
    """Possible outcomes for a step or pipeline execution."""

    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of executing a single pipeline step."""

    step_name: str
    step_type: str
    status: ExecutionStatus
    action_results: list[ActionResult]
    iteration: int = 0
    error: str | None = None


@dataclass
class PipelineResult:
    """Result of executing an entire pipeline."""

    pipeline_name: str
    status: ExecutionStatus
    step_results: list[StepResult]
    paused_at: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Parameter resolution
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\{([\w.\-]+)\}")


def resolve_placeholders(
    config: dict[str, object],
    params: dict[str, object],
) -> dict[str, object]:
    """Recursively resolve ``{name}`` and ``{name.field}`` in *config*.

    - Simple ``{name}`` → ``str(params[name])``; left as-is if missing.
    - Dotted ``{name.field}`` → ``str(params[name][field])``; left as-is if
      params[name] is not a dict or the field is absent.
    - Non-string config values pass through unchanged.
    - Nested dicts and list string-elements are resolved recursively.
    """
    out: dict[str, object] = {}
    for key, value in config.items():
        out[key] = _resolve_value(value, params)
    return out


def _resolve_value(value: object, params: dict[str, object]) -> object:
    if isinstance(value, str):
        return _resolve_str(value, params)
    if isinstance(value, dict):
        return resolve_placeholders(value, params)  # type: ignore[arg-type]
    if isinstance(value, list):
        return [_resolve_value(item, params) for item in value]  # type: ignore[misc]
    return value


def _resolve_str(value: str, params: dict[str, object]) -> str:
    def _sub(match: re.Match[str]) -> str:
        ref = match.group(1)
        if "." in ref:
            parts = ref.split(".", 1)
            container = params.get(parts[0])
            if isinstance(container, dict):
                nested: dict[str, object] = container  # type: ignore[assignment]
                field_val = nested.get(parts[1])
                if field_val is not None:
                    return str(field_val)
            return match.group(0)
        val = params.get(ref)
        if val is None:
            return match.group(0)
        return str(val)

    return _PLACEHOLDER_RE.sub(_sub, value)


# ---------------------------------------------------------------------------
# Loop condition grammar
# ---------------------------------------------------------------------------


class LoopCondition(StrEnum):
    """Closed set of loop exit conditions."""

    REVIEW_PASS = "review.pass"
    REVIEW_CONCERNS_OR_BETTER = "review.concerns_or_better"
    ACTION_SUCCESS = "action.success"


def evaluate_condition(
    condition: LoopCondition,
    action_results: list[ActionResult],
) -> bool:
    """Return True if *condition* is satisfied by *action_results*.

    Returns False if no matching results are found (e.g. no review action).
    """
    match condition:
        case LoopCondition.REVIEW_PASS:
            last_review = _last_with_verdict(action_results)
            return last_review is not None and last_review.verdict == "PASS"
        case LoopCondition.REVIEW_CONCERNS_OR_BETTER:
            last_review = _last_with_verdict(action_results)
            return last_review is not None and last_review.verdict in {
                "PASS",
                "CONCERNS",
            }
        case LoopCondition.ACTION_SUCCESS:
            return bool(action_results) and all(r.success for r in action_results)


def _last_with_verdict(results: list[ActionResult]) -> ActionResult | None:
    for result in reversed(results):
        if result.verdict is not None:
            return result
    return None


# ---------------------------------------------------------------------------
# Retry loop configuration
# ---------------------------------------------------------------------------


class ExhaustBehavior(StrEnum):
    """What to do when a loop reaches max iterations without the condition."""

    FAIL = "fail"
    CHECKPOINT = "checkpoint"
    SKIP = "skip"


@dataclass
class LoopConfig:
    """Parsed loop configuration from a step config dict."""

    max: int
    until: LoopCondition | None = None
    on_exhaust: ExhaustBehavior = ExhaustBehavior.FAIL
    strategy: str | None = None
    commit_each_iteration: bool = False


# ---------------------------------------------------------------------------
# Checkpoint resolution types
# ---------------------------------------------------------------------------


class CheckpointResolution(StrEnum):
    """User's choice at an interactive checkpoint."""

    ACCEPT = "accept"
    OVERRIDE = "override"
    EXIT = "exit"


@dataclass
class CheckpointDecision:
    """Result of the interactive checkpoint prompt."""

    resolution: CheckpointResolution
    override_instructions: str | None  # None when resolution is EXIT


def _is_interactive() -> bool:
    """Return True if stdin is a TTY and SQUADRON_NO_INTERACTIVE is not set."""
    return sys.stdin.isatty() and not os.environ.get("SQUADRON_NO_INTERACTIVE")


_CHECKPOINT_RULE = "─" * 58
CHECKPOINT_KEY_ACCEPT = "a"
CHECKPOINT_KEY_OVERRIDE = "o"
CHECKPOINT_KEY_EXIT = "x"


def _format_findings_as_instructions(findings: list[dict[str, object]]) -> str:
    """Format finding dicts as override instruction lines."""
    lines: list[str] = []
    for finding in findings:
        severity = finding.get("severity", "")
        summary = finding.get("summary", "")
        location = finding.get("location", "")
        line = f"[{severity}] {summary}"
        if location:
            line += f" — {location}"
        lines.append(line)
    return "\n".join(lines)


def _prompt_checkpoint_interactive(
    verdict: str | None,
    findings: list[dict[str, object]],
    run_id: str,
    step_name: str,
) -> CheckpointDecision:
    """Display an interactive checkpoint menu and return the user's decision.

    Falls back to EXIT silently in non-interactive environments.
    """
    if not _is_interactive():
        _logger.warning(
            "checkpoint: non-interactive environment; defaulting to exit"
            " (set SQUADRON_NO_INTERACTIVE=0 to suppress)"
        )
        return CheckpointDecision(CheckpointResolution.EXIT, None)

    _MAX_FINDINGS = 10
    verdict_label = verdict or "N/A"

    print(_CHECKPOINT_RULE)
    print(f"Checkpoint — step '{step_name}' │ Review: {verdict_label}")
    print(_CHECKPOINT_RULE)

    if findings:
        display = findings[:_MAX_FINDINGS]
        extra = len(findings) - _MAX_FINDINGS
        print("Findings:")
        for finding in display:
            severity = finding.get("severity", "")
            summary = finding.get("summary", "")
            location = finding.get("location", "")
            print(f"  [{severity}] {summary}")
            if location:
                print(f"             {location}")
        if extra > 0:
            print(f"  … and {extra} more (see review file)")
    else:
        print("No structured findings. Choose Override to provide explicit instructions.")

    print()
    print("Options:")
    print(
        f"  [{CHECKPOINT_KEY_ACCEPT}] Accept   — continue; findings above become override instructions"
    )
    print(f"  [{CHECKPOINT_KEY_OVERRIDE}] Override — enter custom instructions, then continue")
    print(f"  [{CHECKPOINT_KEY_EXIT}] Exit     — save state; resume: sq run --resume {run_id}")
    print(_CHECKPOINT_RULE)

    while True:
        choice = (
            input(f"Choice [{CHECKPOINT_KEY_ACCEPT}/{CHECKPOINT_KEY_OVERRIDE}/{CHECKPOINT_KEY_EXIT}]: ")
            .strip()
            .lower()
        )
        if choice == CHECKPOINT_KEY_ACCEPT:
            override_instructions = _format_findings_as_instructions(findings)
            return CheckpointDecision(CheckpointResolution.ACCEPT, override_instructions)
        if choice == CHECKPOINT_KEY_OVERRIDE:
            user_text = input("Instructions: ").strip()
            return CheckpointDecision(CheckpointResolution.OVERRIDE, user_text)
        if choice == CHECKPOINT_KEY_EXIT:
            return CheckpointDecision(CheckpointResolution.EXIT, None)
        # Invalid input: loop and re-prompt


def _parse_loop_config(loop_dict: dict[str, object]) -> LoopConfig:
    """Parse a raw loop dict into a LoopConfig.

    Raises ValueError for invalid ``until`` or ``on_exhaust`` values.
    """
    max_iter = loop_dict.get("max")
    if not isinstance(max_iter, int) or max_iter < 1:
        raise ValueError(f"loop.max must be a positive integer, got: {max_iter!r}")

    until_raw = loop_dict.get("until")
    until: LoopCondition | None = None
    if until_raw is not None:
        try:
            until = LoopCondition(until_raw)
        except ValueError:
            valid = [c.value for c in LoopCondition]
            raise ValueError(f"Invalid loop.until value {until_raw!r}. Valid: {valid}") from None

    on_exhaust_raw = loop_dict.get("on_exhaust", ExhaustBehavior.FAIL.value)
    try:
        on_exhaust = ExhaustBehavior(on_exhaust_raw)
    except ValueError:
        valid_ex = [b.value for b in ExhaustBehavior]
        raise ValueError(f"Invalid on_exhaust value {on_exhaust_raw!r}. Valid: {valid_ex}") from None

    strategy = loop_dict.get("strategy")

    return LoopConfig(
        max=max_iter,
        until=until,
        on_exhaust=on_exhaust,
        strategy=strategy if isinstance(strategy, str) else None,
        commit_each_iteration=loop_dict.get("commit_each_iteration") is True,
    )


# ---------------------------------------------------------------------------
# Source registry (for `each` step type)
# ---------------------------------------------------------------------------

SourceFn = Callable[
    [list[str], "ContextForgeClient", dict[str, object]],
    Awaitable[list[dict[str, object]]],
]

_SOURCE_REGISTRY: dict[tuple[str, str], SourceFn] = {}

_SOURCE_RE = re.compile(r"(\w+)\.(\w+)\(([^)]*)\)")


async def _cf_unfinished_slices(
    args: list[str],
    cf_client: ContextForgeClient,
    params: dict[str, object],
) -> list[dict[str, object]]:
    """Return slices whose status is not 'complete'."""
    slices = cf_client.list_slices()
    return [
        {
            "index": str(entry.index),
            "name": entry.name,
            "status": entry.status,
            "design_file": entry.design_file or "",
        }
        for entry in slices
        if entry.status != "complete"
    ]


_SOURCE_REGISTRY[("cf", "unfinished_slices")] = _cf_unfinished_slices


def _parse_source(
    source_str: str,
) -> tuple[str, str, list[str]]:
    """Parse a source string like ``cf.unfinished_slices("{plan}")``.

    Returns (namespace, function, args_list).
    Raises ValueError for unknown namespace/function combinations.
    """
    match = _SOURCE_RE.fullmatch(source_str.strip())
    if not match:
        raise ValueError(
            f"Invalid source string {source_str!r}. Expected format: namespace.function(args)"
        )
    namespace = match.group(1)
    function = match.group(2)
    args_raw = match.group(3).strip()
    args = [a.strip().strip("\"'") for a in args_raw.split(",") if a.strip()] if args_raw else []

    key = (namespace, function)
    if key not in _SOURCE_REGISTRY:
        raise ValueError(
            f"Unknown source '{namespace}.{function}'. Registered sources: {list(_SOURCE_REGISTRY)}"
        )
    return namespace, function, args


# ---------------------------------------------------------------------------
# Core executor
# ---------------------------------------------------------------------------


async def execute_pipeline(
    definition: PipelineDefinition,
    params: dict[str, object],
    *,
    resolver: ModelResolver,
    cf_client: ContextForgeClient,
    cwd: str | None = None,
    run_id: str | None = None,
    start_from: str | None = None,
    start_from_iteration: int = 0,
    sdk_session: SDKExecutionSession | None = None,
    pool_policy: PoolClassificationPolicy = PoolClassificationPolicy.LAZY,
    on_step_complete: Callable[[StepResult], None] | None = None,
    runs_dir: Path | None = None,
    _action_registry: dict[str, object] | None = None,
) -> PipelineResult:
    """Execute *definition* with the given *params*.

    Parameters
    ----------
    definition:
        The loaded PipelineDefinition to execute.
    params:
        Runtime parameters; merged with definition defaults.
    resolver:
        Model resolver for action contexts.
    cf_client:
        ContextForge client for CF operations and source queries.
    cwd:
        Working directory; defaults to ``os.getcwd()``.
    run_id:
        Unique run identifier; auto-generated if not provided.
    start_from:
        Step name to resume from; earlier steps are skipped.
    start_from_iteration:
        Loop round to resume at, applied only to the ``start_from`` step
        (slice 915 Part B / design D3). Clamped to ``>= 1`` when that step
        is a loop; ignored (logged at DEBUG) when it is not, since a
        non-loop step has no rounds to re-enter. ``0`` (default) means "no
        resume round" and behaves exactly as before this parameter existed.
    sdk_session:
        Pre-connected SDK session; ``None`` for non-SDK or lazy pipelines.
    pool_policy:
        Controls lazy vs. strict session construction.  Under ``LAZY``
        (default) the mid-run hook connects the session just before the
        first step that statically requires SDK.  Under ``STRICT`` the
        caller is expected to have passed a connected session for any
        pipeline whose classification returned ``needs_persistent_session``.
    on_step_complete:
        Optional observer called after each step completes (any status).
    runs_dir:
        Directory where run state files live; forwarded to any internal
        ``StateManager`` lookups (SDK-resume seeding, dispatch artifact
        post-condition). Defaults to ``StateManager``'s own default location
        when not provided — must match the ``runs_dir`` used to create
        *run_id*'s state file, or those lookups will not find it.
    _action_registry:
        Internal override for testing; uses the global action registry by default.
    """
    # Import modules to trigger registration
    import squadron.pipeline.actions.cf_op as _a_cf_op  # noqa: F401
    import squadron.pipeline.actions.checkpoint as _a_ckpt  # noqa: F401
    import squadron.pipeline.actions.commit as _a_commit  # noqa: F401
    import squadron.pipeline.actions.compact as _a_compact  # noqa: F401
    import squadron.pipeline.actions.devlog as _a_devlog  # noqa: F401
    import squadron.pipeline.actions.dispatch as _a_dispatch  # noqa: F401
    import squadron.pipeline.actions.review as _a_review  # noqa: F401
    import squadron.pipeline.actions.summary as _a_summary  # noqa: F401
    import squadron.pipeline.intelligence.fan_in.reducers as _fan_in_reducers  # noqa: F401

    _ = (
        _a_cf_op,
        _a_ckpt,
        _a_commit,
        _a_compact,
        _a_devlog,
        _a_dispatch,
        _a_review,
        _a_summary,
        _fan_in_reducers,
    )

    from squadron.events import bootstrap_event_actions
    from squadron.pipeline.actions import get_action
    from squadron.pipeline.steps import bootstrap_step_types, get_step_type

    bootstrap_step_types()
    bootstrap_event_actions()

    effective_cwd = cwd or os.getcwd()
    effective_run_id = run_id or uuid.uuid4().hex[:12]

    # Merge params: definition defaults → caller params (caller wins)
    merged_params: dict[str, object] = {}
    for key, default in definition.params.items():
        if default == "required":
            if key not in params:
                raise ValueError(f"Missing required pipeline parameter: '{key}'")
            merged_params[key] = params[key]
        else:
            merged_params[key] = params.get(key, default)
    # Include any extra caller params not declared in definition
    for key, val in params.items():
        if key not in merged_params:
            merged_params[key] = val

    # Inject _project (project name from CF) so emit destinations can key
    # summary files by project. Only set if not already provided by the caller.
    if "_project" not in merged_params:
        cf_params = gather_cf_params(effective_cwd)
        merged_params["_project"] = cf_params.get("project") or "unknown"

    # Validate start_from refers to an existing step
    if start_from is not None:
        step_names = [s.name for s in definition.steps]
        if start_from not in step_names:
            raise ValueError(
                f"start_from step '{start_from}' not found in pipeline "
                f"'{definition.name}'. Steps: {step_names}"
            )

    step_results: list[StepResult] = []
    # prior_outputs accumulates across all steps
    prior_outputs: dict[str, ActionResult] = {}
    # step_outputs: step-name -> that step's verdict-bearing review result.
    # Additive alongside prior_outputs; does not change prior_outputs semantics.
    step_outputs: dict[str, ActionResult] = {}

    skipping = start_from is not None

    # Resume: seed SDK session with most recent applicable compact summary
    if start_from is not None and sdk_session is not None:
        try:
            from squadron.pipeline.state import StateManager

            _state_mgr = StateManager(runs_dir=runs_dir)
            _run_state = _state_mgr.load(effective_run_id)
            _start_idx = next(
                (i for i, s in enumerate(definition.steps) if s.name == start_from),
                None,
            )
            if _start_idx is not None:
                _active = _run_state.active_compact_summary_for_resume(_start_idx)
                if _active is not None:
                    _logger.info(
                        "executor: resuming at step %d; seeding session from compact summary %s",
                        _start_idx,
                        _active.key,
                    )
                    await sdk_session.seed_context(_active.text)
        except FileNotFoundError:
            _logger.debug("executor: no state file for resume seeding; skipping")

    for step_index, step in enumerate(definition.steps):
        # Handle start_from skip logic
        if skipping:
            if step.name == start_from:
                skipping = False
            else:
                continue

        resolved_config = resolve_placeholders(step.config, merged_params)

        # Mid-run lazy session hook: connect just before the first step that
        # statically requires an SDK session, when none has been connected yet.
        if sdk_session is None and pool_policy == PoolClassificationPolicy.LAZY:
            if _step_needs_sdk(step, resolver, merged_params):
                try:
                    sdk_session = await _connect_lazy_session(run_id=effective_run_id)
                except Exception as exc:
                    _logger.error(
                        "executor: lazy session connect failed before step '%s': %s",
                        step.name,
                        exc,
                    )
                    raise LazySessionConnectError(step.name, exc) from exc

        # Detect each step type
        if step.step_type == "each":
            step_result = await _execute_each_step(
                step=step,
                resolved_config=resolved_config,
                step_index=step_index,
                merged_params=merged_params,
                prior_outputs=prior_outputs,
                step_outputs=step_outputs,
                pipeline_name=definition.name,
                run_id=effective_run_id,
                cwd=effective_cwd,
                resolver=resolver,
                cf_client=cf_client,
                sdk_session=sdk_session,
                get_step_type_fn=get_step_type,
                get_action_fn=_action_registry.__getitem__ if _action_registry else get_action,
                runs_dir=runs_dir,
            )
        elif step.step_type == StepTypeName.FAN_OUT:
            step_result = await _execute_fan_out_step(
                step=step,
                resolved_config=resolved_config,
                step_index=step_index,
                merged_params=merged_params,
                prior_outputs=prior_outputs,
                step_outputs=step_outputs,
                pipeline_name=definition.name,
                run_id=effective_run_id,
                cwd=effective_cwd,
                resolver=resolver,
                cf_client=cf_client,
                sdk_session=sdk_session,
                get_step_type_fn=get_step_type,
                get_action_fn=_action_registry.__getitem__ if _action_registry else get_action,
                runs_dir=runs_dir,
            )
        elif step.step_type == StepTypeName.LOOP:
            step_result = await _execute_loop_body(
                step=step,
                resolved_config=resolved_config,
                step_index=step_index,
                merged_params=merged_params,
                prior_outputs=prior_outputs,
                step_outputs=step_outputs,
                pipeline_name=definition.name,
                run_id=effective_run_id,
                cwd=effective_cwd,
                resolver=resolver,
                cf_client=cf_client,
                sdk_session=sdk_session,
                get_step_type_fn=get_step_type,
                get_action_fn=_action_registry.__getitem__ if _action_registry else get_action,
                runs_dir=runs_dir,
                start_iteration=_resume_start_iteration(
                    step=step, start_from=start_from, start_from_iteration=start_from_iteration
                ),
            )
        else:
            # Check for loop config
            loop_raw = resolved_config.get("loop")
            if loop_raw is not None and isinstance(loop_raw, dict):
                typed_loop: dict[str, object] = loop_raw  # type: ignore[assignment]
                loop_config = _parse_loop_config(typed_loop)
                # Remove loop key from config before passing to step type
                action_config = {k: v for k, v in resolved_config.items() if k != "loop"}
                step_result = await _execute_loop_step(
                    step=step,
                    action_config=action_config,
                    loop_config=loop_config,
                    step_index=step_index,
                    merged_params=merged_params,
                    prior_outputs=prior_outputs,
                    step_outputs=step_outputs,
                    pipeline_name=definition.name,
                    run_id=effective_run_id,
                    cwd=effective_cwd,
                    resolver=resolver,
                    cf_client=cf_client,
                    sdk_session=sdk_session,
                    get_step_type_fn=get_step_type,
                    get_action_fn=_action_registry.__getitem__ if _action_registry else get_action,
                    runs_dir=runs_dir,
                    start_iteration=_resume_start_iteration(
                        step=step,
                        start_from=start_from,
                        start_from_iteration=start_from_iteration,
                    ),
                )
            else:
                if step.name == start_from and start_from_iteration != 0:
                    _logger.debug(
                        "executor: start_from_iteration=%d ignored for non-loop step '%s'",
                        start_from_iteration,
                        step.name,
                    )
                step_result = await _execute_step_once(
                    step=step,
                    resolved_config=resolved_config,
                    step_index=step_index,
                    merged_params=merged_params,
                    prior_outputs=prior_outputs,
                    step_outputs=step_outputs,
                    pipeline_name=definition.name,
                    run_id=effective_run_id,
                    cwd=effective_cwd,
                    resolver=resolver,
                    cf_client=cf_client,
                    sdk_session=sdk_session,
                    get_step_type_fn=get_step_type,
                    get_action_fn=_action_registry.__getitem__ if _action_registry else get_action,
                    runs_dir=runs_dir,
                )

        step_results.append(step_result)

        if on_step_complete is not None:
            on_step_complete(step_result)

        if step_result.status == ExecutionStatus.PAUSED:
            return PipelineResult(
                pipeline_name=definition.name,
                status=ExecutionStatus.PAUSED,
                step_results=step_results,
                paused_at=step.name,
            )

        if step_result.status == ExecutionStatus.FAILED:
            return PipelineResult(
                pipeline_name=definition.name,
                status=ExecutionStatus.FAILED,
                step_results=step_results,
            )

        # Accumulate prior_outputs from this step's action results
        for idx, action_result in enumerate(step_result.action_results):
            key = f"{action_result.action_type}-{idx}"
            prior_outputs[key] = action_result

        # Accumulate step_outputs: step-name -> this step's most recent
        # verdict-bearing result, mirroring _last_with_verdict's "most recent
        # verdict" intent but scoped to this one step (additive; does not
        # change prior_outputs or checkpoint behavior).
        step_verdict_result = _last_with_verdict(step_result.action_results)
        if step_verdict_result is not None:
            step_outputs[step_result.step_name] = step_verdict_result

    return PipelineResult(
        pipeline_name=definition.name,
        status=ExecutionStatus.COMPLETED,
        step_results=step_results,
    )


def _step_needs_sdk(
    step: Any,
    resolver: Any,
    params: dict[str, object],
) -> bool:
    """Return True iff *step* statically resolves to an SDK profile.

    Used by the mid-run lazy session hook to decide whether to connect a
    persistent session before a given step.

    Returns False for:
    - Step types that do not use a persistent session (e.g. review, checkpoint).
    - Steps whose resolved candidate is a pool reference (cannot confirm statically).
    - Any cascade level that resolves to a non-SDK profile.

    Does not mutate resolver state and does not invoke pool selection.
    """
    from squadron.models.aliases import resolve_model_alias
    from squadron.providers.profiles import is_sdk_profile

    if step.step_type not in PERSISTENT_SESSION_STEP_TYPES:
        return False

    action_model = str(params["model"]) if "model" in params else None
    step_model = str(params.get("step_model", "")) or None
    step_action_model = step.config.get("model")
    step_step_model = step.config.get("step_model")

    candidates = resolver.cascade_candidates(
        action_model=str(step_action_model) if isinstance(step_action_model, str) else action_model,
        step_model=str(step_step_model) if isinstance(step_step_model, str) else step_model,
    )
    candidate = next((c for c in candidates if c is not None), None)
    if candidate is None or candidate.startswith("pool:"):
        return False

    _, profile = resolve_model_alias(candidate)
    return is_sdk_profile(profile)


async def _connect_lazy_session(*, run_id: str) -> SDKExecutionSession:
    """Construct and connect a new SDKExecutionSession for mid-run lazy auth.

    Called by execute_pipeline the first time a statically-confirmed SDK step
    is about to run and no session has been connected yet.

    On connection failure, logs at ERROR and re-raises — the caller handles
    state persistence and user-facing error messaging.
    """
    import claude_agent_sdk

    from squadron.pipeline.sdk_session import SDKExecutionSession

    options = claude_agent_sdk.ClaudeAgentOptions(
        cwd=str(__import__("pathlib").Path.cwd()),
        permission_mode="bypassPermissions",
        system_prompt={"type": "preset", "preset": "claude_code"},
    )
    client = claude_agent_sdk.ClaudeSDKClient(options=options)
    session = SDKExecutionSession(client=client, options=options)
    try:
        await session.connect()
    except Exception:
        _logger.exception(
            "executor: lazy session connect failed for run %s",
            run_id,
        )
        raise
    return session


async def _execute_step_once(
    *,
    step: Any,
    resolved_config: dict[str, object],
    step_index: int,
    merged_params: dict[str, object],
    prior_outputs: dict[str, ActionResult],
    step_outputs: dict[str, ActionResult] | None = None,
    pipeline_name: str,
    run_id: str,
    cwd: str,
    resolver: Any,
    cf_client: Any,
    sdk_session: SDKExecutionSession | None = None,
    get_step_type_fn: Any,
    get_action_fn: Any,
    iteration: int = 0,
    prior_iteration_step_outputs: dict[str, ActionResult] | None = None,
    runs_dir: Path | None = None,
) -> StepResult:
    """Execute a single step's action sequence once. Returns a StepResult."""
    step_type_impl = get_step_type_fn(step.step_type)
    actions = step_type_impl.expand(step)

    _logger.info(
        "step %s [%s]: %d actions",
        step.name,
        step.step_type,
        len(actions),
    )

    # Loaded once per step (not per-action) — only needed when this step is a
    # PhaseStepType with a non-None expected_artifact_kind, checked below.
    # A missing/corrupt state file is itself a "cannot confirm" condition
    # (fails closed below, at the dispatch post-condition check) rather than
    # an uncaught crash — e.g. execute_pipeline invoked directly without a
    # prior StateManager().init_run() (as some tests and tooling do).
    run_started_at: datetime | None = None
    run_state_error: str | None = None
    expected_kind = (
        step_type_impl.expected_artifact_kind if isinstance(step_type_impl, PhaseStepType) else None
    )
    if expected_kind is not None:
        from squadron.pipeline.state import StateManager

        try:
            run_started_at = StateManager(runs_dir=runs_dir).load(run_id).started_at
        except (FileNotFoundError, ValueError) as exc:
            run_state_error = f"could not load run state for run_id={run_id!r}: {exc}"
            _logger.warning("dispatch post-condition: %s", run_state_error)

    action_results: list[ActionResult] = []
    step_prior = dict(prior_outputs)  # snapshot; updated within step

    for action_index, (action_type, action_config) in enumerate(actions):
        resolved_action_config = resolve_placeholders(action_config, merged_params)
        merged_action_params = {**merged_params, **resolved_action_config}

        _logger.info(
            "  action %d/%d: %s %s",
            action_index + 1,
            len(actions),
            action_type,
            _summarize_action_config(action_type, resolved_action_config),
        )

        ctx = ActionContext(
            pipeline_name=pipeline_name,
            run_id=run_id,
            params=merged_action_params,
            step_name=step.name,
            step_index=step_index,
            prior_outputs=step_prior,
            resolver=resolver,
            cf_client=cf_client,
            cwd=cwd,
            sdk_session=sdk_session,
            step_outputs=step_outputs if step_outputs is not None else {},
            iteration=iteration,
            prior_iteration_step_outputs=(
                prior_iteration_step_outputs if prior_iteration_step_outputs is not None else {}
            ),
        )

        action_impl = get_action_fn(action_type)
        result: ActionResult = await action_impl.execute(ctx)
        action_results.append(result)

        _log_action_result(action_type, result)

        # POST_ACTION event bindings (slice 173): squadron.dispatch-artifact
        # (909's post-condition) and squadron.revision-stamp (911's stamp)
        # run here by default; a project's events.yaml may add more.
        post_action_ctx = PostActionContext(
            event=EventType.POST_ACTION,
            cwd=cwd,
            params=ctx.params,
            action_type=action_type,
            result=result,
            run_id=run_id,
            run_started_at=run_started_at,
            run_state_error=run_state_error,
            step_name=step.name,
            step_type=step.step_type,
            expected_artifact_kind=expected_kind,
            iteration=ctx.iteration,
            cf_client=cf_client,
        )
        outcomes = await run_event(post_action_ctx)
        for outcome in outcomes:
            if outcome.result is not None and not outcome.result.success:
                result.success = False
                result.error = outcome.result.error
                break
            if outcome.error_kind is not OutcomeErrorKind.NONE:
                result.success = False
                result.error = f"{outcome.action_name}: {outcome.error_kind.value}"
                break

        # Update step_prior for next action in same step
        key = f"{action_type}-{action_index}"
        step_prior[key] = result

        # Checkpoint pause
        if result.outputs.get("checkpoint") == "paused":
            # Findings come from the review action, not the checkpoint action.
            # The checkpoint action sets outputs["checkpoint"] = "paused" AND
            # copies verdict from the prior review for downstream use — so
            # _last_with_verdict walking action_results would return the
            # checkpoint result (which has verdict but empty findings) before
            # the review. Skip the just-appended checkpoint result and search
            # the prior actions only.
            prior_review = _last_with_verdict(action_results[:-1])
            verdict = prior_review.verdict if prior_review else None
            findings: list[dict[str, object]] = (
                [f for f in (prior_review.findings or []) if isinstance(f, dict)]  # type: ignore[misc]
                if prior_review
                else []
            )
            decision = _prompt_checkpoint_interactive(verdict, findings, run_id, step.name)
            if decision.resolution == CheckpointResolution.EXIT:
                return StepResult(
                    step_name=step.name,
                    step_type=step.step_type,
                    status=ExecutionStatus.PAUSED,
                    action_results=action_results,
                    iteration=iteration,
                )
            # Accept or Override: inject instructions and continue to next action
            if decision.override_instructions:
                merged_params["override_instructions"] = decision.override_instructions

        # Action failure
        if not result.success:
            return StepResult(
                step_name=step.name,
                step_type=step.step_type,
                status=ExecutionStatus.FAILED,
                action_results=action_results,
                iteration=iteration,
            )

    return StepResult(
        step_name=step.name,
        step_type=step.step_type,
        status=ExecutionStatus.COMPLETED,
        action_results=action_results,
        iteration=iteration,
    )


def _loop_exhaust_result(
    *,
    step: Any,
    on_exhaust: ExhaustBehavior,
    action_results: list[ActionResult],
    max_iter: int,
) -> StepResult:
    """Build the exhaustion StepResult for the configured ``on_exhaust`` mode.

    Shared by ``_execute_loop_step`` (single-step body) and
    ``_execute_loop_body`` (multi-step body).
    """
    match on_exhaust:
        case ExhaustBehavior.FAIL:
            status = ExecutionStatus.FAILED
        case ExhaustBehavior.CHECKPOINT:
            status = ExecutionStatus.PAUSED
        case ExhaustBehavior.SKIP:
            status = ExecutionStatus.SKIPPED
    return StepResult(
        step_name=step.name,
        step_type=step.step_type,
        status=status,
        action_results=action_results,
        iteration=max_iter,
    )


def _warn_loop_abandoned_on_pause(
    *, pipeline_name: str, step_name: str, iteration: int, loop_max: int
) -> None:
    """Log the observable signal for slice 915 Part A/#48: a checkpoint pause
    inside a loop body silently abandoned every remaining round. Shared by
    both loop shapes (_execute_loop_step, _execute_loop_body) so the message
    is single-sourced rather than duplicated at each short-circuit.
    """
    rounds_not_run = loop_max - iteration
    _logger.warning(
        "pipeline %s: loop step %s paused at round %d of %d; %d round(s) not run",
        pipeline_name,
        step_name,
        iteration,
        loop_max,
        rounds_not_run,
    )


def _resume_start_iteration(*, step: Any, start_from: str | None, start_from_iteration: int) -> int:
    """Resolve the loop round to resume *step* at (slice 915 Part B, D3).

    Applies only to the ``start_from`` step; every other loop step starts at
    round 1. Clamps to ``>= 1`` — ``start_from_iteration=0`` is the "no
    resume round" sentinel and must not become an invalid round 0. Emits the
    resume-time INFO (design D4 signal 2) when re-entering above round 1.
    """
    if step.name != start_from or start_from_iteration <= 0:
        return 1
    iteration = max(1, start_from_iteration)
    if iteration > 1:
        _logger.info(
            "pipeline resume: loop step %s re-entering at round %d",
            step.name,
            iteration,
        )
    return iteration


def _degenerate_start_iteration_result(
    *, step: Any, pipeline_name: str, start_iteration: int, loop_max: int
) -> StepResult:
    """Build the StepResult for a resume request above the loop's max: (slice
    915 Part B). Only reachable from malformed resume state — a recorded
    iteration greater than the loop's configured max. Returning COMPLETED
    for a loop that ran zero rounds would re-create the exact defect class
    this slice fixes (a loop reporting doneness it never reached), so this
    fails loudly instead of falling out of an empty range() silently.
    """
    _logger.warning(
        "pipeline %s: loop step %s resume requested at round %d, above max %d; no rounds run",
        pipeline_name,
        step.name,
        start_iteration,
        loop_max,
    )
    return StepResult(
        step_name=step.name,
        step_type=step.step_type,
        status=ExecutionStatus.FAILED,
        action_results=[],
        iteration=start_iteration,
        error=(f"resume requested at round {start_iteration}, above loop max {loop_max}"),
    )


async def _execute_loop_step(
    *,
    step: Any,
    action_config: dict[str, object],
    loop_config: LoopConfig,
    step_index: int,
    merged_params: dict[str, object],
    prior_outputs: dict[str, ActionResult],
    step_outputs: dict[str, ActionResult] | None = None,
    pipeline_name: str,
    run_id: str,
    cwd: str,
    resolver: Any,
    cf_client: Any,
    sdk_session: SDKExecutionSession | None = None,
    get_step_type_fn: Any,
    get_action_fn: Any,
    runs_dir: Path | None = None,
    start_iteration: int = 1,
) -> StepResult:
    """Execute a step with loop configuration."""
    if loop_config.strategy is not None:
        _logger.warning(
            "Loop strategy '%s' not implemented, falling back to basic max-iteration loop",
            loop_config.strategy,
        )

    # Build a synthetic StepConfig with the loop key removed
    from squadron.pipeline.models import StepConfig

    stripped_step = StepConfig(
        step_type=step.step_type,
        name=step.name,
        config=action_config,
    )

    if start_iteration > loop_config.max:
        return _degenerate_start_iteration_result(
            step=step,
            pipeline_name=pipeline_name,
            start_iteration=start_iteration,
            loop_max=loop_config.max,
        )

    last_result: StepResult | None = None

    for iteration in range(start_iteration, loop_config.max + 1):
        result = await _execute_step_once(
            step=stripped_step,
            resolved_config=action_config,
            step_index=step_index,
            merged_params=merged_params,
            prior_outputs=prior_outputs,
            step_outputs=step_outputs,
            pipeline_name=pipeline_name,
            run_id=run_id,
            cwd=cwd,
            resolver=resolver,
            cf_client=cf_client,
            sdk_session=sdk_session,
            get_step_type_fn=get_step_type_fn,
            get_action_fn=get_action_fn,
            iteration=iteration,
            runs_dir=runs_dir,
        )
        last_result = result

        # Checkpoint pause always stops the loop
        if result.status == ExecutionStatus.PAUSED:
            _warn_loop_abandoned_on_pause(
                pipeline_name=pipeline_name,
                step_name=step.name,
                iteration=iteration,
                loop_max=loop_config.max,
            )
            return result

        # Check until condition if set
        if loop_config.until is not None:
            if evaluate_condition(loop_config.until, result.action_results):
                return StepResult(
                    step_name=step.name,
                    step_type=step.step_type,
                    status=ExecutionStatus.COMPLETED,
                    action_results=result.action_results,
                    iteration=iteration,
                )
        elif result.status == ExecutionStatus.COMPLETED:
            # No until condition — succeed on first completed iteration
            return result

        # Action failure is transient in loops — continue to next iteration

    # Max iterations exhausted
    final_results = last_result.action_results if last_result else []
    return _loop_exhaust_result(
        step=step,
        on_exhaust=loop_config.on_exhaust,
        action_results=final_results,
        max_iter=loop_config.max,
    )


async def _execute_loop_body(
    *,
    step: Any,
    resolved_config: dict[str, object],
    step_index: int,
    merged_params: dict[str, object],
    prior_outputs: dict[str, ActionResult],
    step_outputs: dict[str, ActionResult] | None = None,
    pipeline_name: str,
    run_id: str,
    cwd: str,
    resolver: Any,
    cf_client: Any,
    sdk_session: SDKExecutionSession | None = None,
    get_step_type_fn: Any,
    get_action_fn: Any,
    runs_dir: Path | None = None,
    start_iteration: int = 1,
) -> StepResult:
    """Execute a ``loop:`` step type with a multi-step body.

    Mirrors ``_execute_loop_step`` semantics but iterates over a ``steps:``
    body rather than a single action.  ``_parse_loop_config`` ignores the
    ``steps`` key, so ``resolved_config`` is passed through unchanged.
    """
    loop_config = _parse_loop_config(resolved_config)

    if loop_config.strategy is not None:
        _logger.warning(
            "Loop strategy '%s' not implemented, falling back to basic max-iteration loop",
            loop_config.strategy,
        )

    inner_steps_raw = resolved_config.get("steps", [])
    if isinstance(inner_steps_raw, list):
        raw_list: list[dict[str, object]] = [
            cast(dict[str, object], s)
            for s in inner_steps_raw  # type: ignore[union-attr]
            if isinstance(s, dict)
        ]
    else:
        raw_list = []
    inner_steps = unpack_inner_steps(raw_list)

    # Bound across the loop so the exhaustion path can return the latest
    # iteration's results.  Reassigned at the start of each iteration.
    iteration_action_results: list[ActionResult] = []

    # Accumulates each iteration's results so the next iteration's actions
    # (e.g. DispatchAction's findings-feedback) see what the loop has
    # actually produced so far, not just prior_outputs as it stood at loop
    # entry. Mirrors the step_prior snapshot pattern in _execute_step_once.
    running_prior = dict(prior_outputs)

    # The previous iteration's inner-step outputs, handed down to this
    # iteration's actions. Scoped to the loop body's own steps — snapshotting
    # step_outputs wholesale would leak pre-loop steps into what a policy reads
    # as "the prior round". Empty on iteration 1 (no prior round).
    prior_iteration_step_outputs: dict[str, ActionResult] = {}

    # Steps that ran before the loop, snapshotted once. Each iteration gets a
    # fresh copy to write its own body outputs into, so an inner step's result
    # never outlives its iteration.
    pre_loop_step_outputs = dict(step_outputs) if step_outputs is not None else {}

    if start_iteration > loop_config.max:
        return _degenerate_start_iteration_result(
            step=step,
            pipeline_name=pipeline_name,
            start_iteration=start_iteration,
            loop_max=loop_config.max,
        )

    for iteration in range(start_iteration, loop_config.max + 1):
        iteration_action_results = []
        iteration_step_outputs: dict[str, ActionResult] = {}
        # What the body's actions resolve step names against this round:
        # pre-loop steps plus this iteration's own body steps, and nothing from
        # a previous iteration. Writing body results into the run-wide
        # step_outputs instead would leave round N-1's review standing when
        # round N's review fails, and a gate would read it as this round's
        # evidence with no way to tell.
        visible_step_outputs: dict[str, ActionResult] = dict(pre_loop_step_outputs)

        for inner_step_index, inner_step in enumerate(inner_steps):
            inner_resolved = resolve_placeholders(inner_step.config, merged_params)
            inner_result = await _execute_step_once(
                step=inner_step,
                resolved_config=inner_resolved,
                step_index=step_index,
                merged_params=merged_params,
                prior_outputs=running_prior,
                step_outputs=visible_step_outputs,
                pipeline_name=pipeline_name,
                run_id=run_id,
                cwd=cwd,
                resolver=resolver,
                cf_client=cf_client,
                sdk_session=sdk_session,
                get_step_type_fn=get_step_type_fn,
                get_action_fn=get_action_fn,
                iteration=iteration,
                prior_iteration_step_outputs=prior_iteration_step_outputs,
                runs_dir=runs_dir,
            )
            iteration_action_results.extend(inner_result.action_results)
            # Fold in the inner step's own position so two different inner
            # steps producing the same action_type (e.g. two dispatch:
            # steps) never collide within one iteration — only same-key
            # writes across iterations are meant to overwrite.
            for action_index, result in enumerate(inner_result.action_results):
                key = f"{inner_step_index}-{result.action_type}-{action_index}"
                running_prior[key] = result

            # Publish the inner step's verdict-bearing result under its step
            # name, using the same rule the top-level walk uses. The top-level
            # walk never sees inner steps, so without this a `gate` inside a
            # loop body cannot resolve review_from/judge_from — step_outputs is
            # its only resolution mechanism — and emits UNKNOWN every round.
            # Published into this iteration's view only: the run-wide dict is
            # left untouched, so inner names neither collide with a top-level
            # step nor remain resolvable after the loop exits.
            inner_verdict_result = _last_with_verdict(inner_result.action_results)
            if inner_verdict_result is not None:
                iteration_step_outputs[inner_result.step_name] = inner_verdict_result
                visible_step_outputs[inner_result.step_name] = inner_verdict_result

            # Checkpoint pause short-circuits the loop immediately
            if inner_result.status == ExecutionStatus.PAUSED:
                _warn_loop_abandoned_on_pause(
                    pipeline_name=pipeline_name,
                    step_name=step.name,
                    iteration=iteration,
                    loop_max=loop_config.max,
                )
                return StepResult(
                    step_name=step.name,
                    step_type=step.step_type,
                    status=ExecutionStatus.PAUSED,
                    action_results=iteration_action_results,
                    iteration=iteration,
                )
            # FAILED is transient — continue executing remaining inner steps

        # This iteration's body outputs become the next iteration's "prior
        # round". Assigned after the body completes so no step within an
        # iteration can read its own round through this field.
        prior_iteration_step_outputs = iteration_step_outputs

        # commit_each_iteration (Part A2, #44): append one commit action
        # after the body's inner steps for this iteration, before the
        # until: check, so a dispatch-bodied loop also leaves per-round
        # history. Validation (LoopStepType) already rejects this option
        # when the body itself commits, so no double-commit is possible here.
        if loop_config.commit_each_iteration:
            commit_ctx = ActionContext(
                pipeline_name=pipeline_name,
                run_id=run_id,
                params={"message_prefix": f"loop-{step.name}"},
                step_name=step.name,
                step_index=step_index,
                prior_outputs=running_prior,
                resolver=resolver,
                cf_client=cf_client,
                cwd=cwd,
                sdk_session=sdk_session,
                step_outputs=visible_step_outputs,
                iteration=iteration,
            )
            commit_result = await get_action_fn("commit").execute(commit_ctx)
            iteration_action_results.append(commit_result)
            # Same key scheme as the inner-step loop above; len(inner_steps)
            # is one past the last real inner_step_index, so it can't collide.
            commit_key = f"{len(inner_steps)}-{commit_result.action_type}-0"
            running_prior[commit_key] = commit_result

        # Evaluate until condition after all inner steps complete
        if loop_config.until is not None:
            if evaluate_condition(loop_config.until, iteration_action_results):
                return StepResult(
                    step_name=step.name,
                    step_type=step.step_type,
                    status=ExecutionStatus.COMPLETED,
                    action_results=iteration_action_results,
                    iteration=iteration,
                )
        else:
            # No until condition — complete after first full iteration
            return StepResult(
                step_name=step.name,
                step_type=step.step_type,
                status=ExecutionStatus.COMPLETED,
                action_results=iteration_action_results,
                iteration=iteration,
            )

    # Max iterations exhausted
    return _loop_exhaust_result(
        step=step,
        on_exhaust=loop_config.on_exhaust,
        action_results=iteration_action_results,
        max_iter=loop_config.max,
    )


async def _execute_each_step(
    *,
    step: Any,
    resolved_config: dict[str, object],
    step_index: int,
    merged_params: dict[str, object],
    prior_outputs: dict[str, ActionResult],
    step_outputs: dict[str, ActionResult] | None = None,
    pipeline_name: str,
    run_id: str,
    cwd: str,
    resolver: Any,
    cf_client: Any,
    sdk_session: SDKExecutionSession | None = None,
    get_step_type_fn: Any,
    get_action_fn: Any,
    runs_dir: Path | None = None,
) -> StepResult:
    """Execute an `each` collection step."""
    source_str = str(resolved_config.get("source", ""))
    as_name = str(resolved_config.get("as", ""))
    inner_steps_raw = resolved_config.get("steps", [])

    # Resolve placeholders in source string
    source_resolved = _resolve_str(source_str, merged_params)

    namespace, function, args = _parse_source(source_resolved)
    source_fn = _SOURCE_REGISTRY[(namespace, function)]

    items = await source_fn(args, cf_client, merged_params)

    from typing import cast

    if isinstance(inner_steps_raw, list):
        raw_list: list[dict[str, object]] = [
            cast(dict[str, object], s)
            for s in inner_steps_raw  # type: ignore[union-attr]
            if isinstance(s, dict)
        ]
    else:
        raw_list = []
    inner_steps = unpack_inner_steps(raw_list)
    all_action_results: list[ActionResult] = []

    for item in items:
        # Bind iteration variable
        item_params = {**merged_params, as_name: item}

        for inner_step in inner_steps:
            inner_resolved = resolve_placeholders(inner_step.config, item_params)
            inner_result = await _execute_step_once(
                step=inner_step,
                resolved_config=inner_resolved,
                step_index=step_index,
                merged_params=item_params,
                prior_outputs=prior_outputs,
                step_outputs=step_outputs,
                pipeline_name=pipeline_name,
                run_id=run_id,
                cwd=cwd,
                resolver=resolver,
                cf_client=cf_client,
                sdk_session=sdk_session,
                get_step_type_fn=get_step_type_fn,
                get_action_fn=get_action_fn,
                runs_dir=runs_dir,
            )
            all_action_results.extend(inner_result.action_results)

            if inner_result.status in (ExecutionStatus.FAILED, ExecutionStatus.PAUSED):
                return StepResult(
                    step_name=step.name,
                    step_type=step.step_type,
                    status=inner_result.status,
                    action_results=all_action_results,
                )

    return StepResult(
        step_name=step.name,
        step_type=step.step_type,
        status=ExecutionStatus.COMPLETED,
        action_results=all_action_results,
    )


# ---------------------------------------------------------------------------
# Fan-out step executor
# ---------------------------------------------------------------------------

_POOL_PREFIX = "pool:"


async def _execute_fan_out_step(
    *,
    step: Any,
    resolved_config: dict[str, object],
    step_index: int,
    merged_params: dict[str, object],
    prior_outputs: dict[str, ActionResult],
    step_outputs: dict[str, ActionResult] | None = None,
    pipeline_name: str,
    run_id: str,
    cwd: str,
    resolver: Any,
    cf_client: Any,
    sdk_session: SDKExecutionSession | None = None,
    get_step_type_fn: Any,
    get_action_fn: Any,
    runs_dir: Path | None = None,
) -> StepResult:
    """Execute a ``fan_out`` step: dispatch N branches concurrently, then reduce.

    Guard: raises an explicit FAILED result when sdk_session is active, because
    concurrent branches would interleave messages on the stateful CLI process.
    """
    import asyncio

    from squadron.pipeline.intelligence.fan_in.reducers import get_reducer

    models_raw = resolved_config["models"]
    fan_in_name = str(resolved_config.get("fan_in", "collect"))
    inner_raw = resolved_config["inner"]

    # 1. Build model list — call resolver.resolve() once per branch, keep profile.
    try:
        if isinstance(models_raw, str) and models_raw.startswith(_POOL_PREFIX):
            n = int(resolved_config.get("n", 1))  # type: ignore[arg-type]
            pool_ref = models_raw  # e.g. "pool:review"
            branch_models: list[tuple[str, str | None]] = [resolver.resolve(pool_ref) for _ in range(n)]
        else:
            branch_models = [resolver.resolve(str(m)) for m in models_raw]  # type: ignore[union-attr]
    except Exception as exc:
        # Broad by design: an invalid branch-model spec (bad alias, unknown
        # pool) must become a reported FAILED step rather than crash the
        # run, and the raisable set from resolver.resolve() is open-ended
        # across ModelResolutionError / ModelPoolNotImplemented /
        # PoolNotFoundError. logger.exception preserves the traceback so a
        # genuine programming error inside this block is still diagnosable.
        _logger.exception("fan_out step '%s': branch model resolution failed", step.name)
        return StepResult(
            step_name=step.name,
            step_type=step.step_type,
            status=ExecutionStatus.FAILED,
            action_results=[],
            error=str(exc),
        )

    # 2. Parse inner step (single-key dict format).
    from typing import cast

    inner_list: list[dict[str, object]] = [cast(dict[str, object], inner_raw)]
    inner_steps = unpack_inner_steps(inner_list)
    if not inner_steps:
        raise ValueError(f"fan_out step '{step.name}': invalid inner step")
    inner_step = inner_steps[0]

    # 3. Build branch coroutines.
    async def _run_branch(idx: int, model_id: str, profile: str | None) -> StepResult:
        branch_params: dict[str, object] = {
            **merged_params,
            "_fan_out_branch_index": idx,
            "_fan_out_model": model_id,
            "model": model_id,
        }
        if profile is not None:
            branch_params["profile"] = profile
        inner_resolved = resolve_placeholders(inner_step.config, branch_params)
        return await _execute_step_once(
            step=inner_step,
            resolved_config=inner_resolved,
            step_index=step_index,
            merged_params=branch_params,
            prior_outputs=prior_outputs,
            step_outputs=step_outputs,
            pipeline_name=pipeline_name,
            run_id=run_id,
            cwd=cwd,
            resolver=resolver,
            cf_client=cf_client,
            sdk_session=None,  # never propagate session into branches
            get_step_type_fn=get_step_type_fn,
            get_action_fn=get_action_fn,
            runs_dir=runs_dir,
        )

    # 4. Gather branches — return_exceptions=False for fast-fail on exception.
    try:
        branch_results: list[StepResult] = list(
            await asyncio.gather(*(_run_branch(i, m, p) for i, (m, p) in enumerate(branch_models)))
        )
    except Exception as exc:  # noqa: BLE001
        # Broad by design: each branch runs a full step execution (dispatch,
        # actions, etc.), so the raisable set here is whatever any branch's
        # step execution can raise — open-ended. A branch failure must
        # become a reported FAILED step, not crash the whole run. Logged so
        # a genuine programming error surfaced this way is still diagnosable.
        _logger.exception("fan_out step '%s': a branch raised during gather", step.name)
        return StepResult(
            step_name=step.name,
            step_type=step.step_type,
            status=ExecutionStatus.FAILED,
            action_results=[],
            error=str(exc),
        )

    # 5. Fail fast if any branch returned FAILED.
    failed = [r for r in branch_results if r.status == ExecutionStatus.FAILED]
    if failed:
        error_msgs = "; ".join(r.error or "branch failed" for r in failed)
        return StepResult(
            step_name=step.name,
            step_type=step.step_type,
            status=ExecutionStatus.FAILED,
            action_results=[],
            error=error_msgs,
        )

    # 6. Reduce.
    reducer = get_reducer(fan_in_name)
    action_result = reducer.reduce(branch_results, resolved_config)

    return StepResult(
        step_name=step.name,
        step_type=step.step_type,
        status=ExecutionStatus.COMPLETED,
        action_results=[action_result],
    )
