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
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from squadron.pipeline.models import ActionContext, ActionResult, PipelineDefinition

if TYPE_CHECKING:
    from squadron.integrations.context_forge import ContextForgeClient
    from squadron.pipeline.resolver import ModelResolver

_logger = logging.getLogger(__name__)

__all__ = [
    "ExecutionStatus",
    "StepResult",
    "PipelineResult",
    "LoopCondition",
    "ExhaustBehavior",
    "LoopConfig",
    "resolve_placeholders",
    "evaluate_condition",
    "execute_pipeline",
]

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


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

_PLACEHOLDER_RE = re.compile(r"\{([\w.]+)\}")


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
            raise ValueError(
                f"Invalid loop.until value {until_raw!r}. Valid: {valid}"
            ) from None

    on_exhaust_raw = loop_dict.get("on_exhaust", ExhaustBehavior.FAIL.value)
    try:
        on_exhaust = ExhaustBehavior(on_exhaust_raw)
    except ValueError:
        valid_ex = [b.value for b in ExhaustBehavior]
        raise ValueError(
            f"Invalid on_exhaust value {on_exhaust_raw!r}. Valid: {valid_ex}"
        ) from None

    strategy = loop_dict.get("strategy")

    return LoopConfig(
        max=max_iter,
        until=until,
        on_exhaust=on_exhaust,
        strategy=strategy if isinstance(strategy, str) else None,
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
            f"Invalid source string {source_str!r}. "
            "Expected format: namespace.function(args)"
        )
    namespace = match.group(1)
    function = match.group(2)
    args_raw = match.group(3).strip()
    args = (
        [a.strip().strip("\"'") for a in args_raw.split(",") if a.strip()]
        if args_raw
        else []
    )

    key = (namespace, function)
    if key not in _SOURCE_REGISTRY:
        raise ValueError(
            f"Unknown source '{namespace}.{function}'. "
            f"Registered sources: {list(_SOURCE_REGISTRY)}"
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
    on_step_complete: Callable[[StepResult], None] | None = None,
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
    on_step_complete:
        Optional observer called after each step completes (any status).
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
    import squadron.pipeline.steps.collection as _s_collection  # noqa: F401
    import squadron.pipeline.steps.compact as _s_compact  # noqa: F401
    import squadron.pipeline.steps.devlog as _s_devlog  # noqa: F401
    import squadron.pipeline.steps.phase as _s_phase  # noqa: F401
    import squadron.pipeline.steps.review as _s_review  # noqa: F401

    _ = (
        _a_cf_op,
        _a_ckpt,
        _a_commit,
        _a_compact,
        _a_devlog,
        _a_dispatch,
        _a_review,
        _s_collection,
        _s_compact,
        _s_devlog,
        _s_phase,
        _s_review,
    )

    from squadron.pipeline.actions import get_action
    from squadron.pipeline.steps import get_step_type

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

    skipping = start_from is not None

    for step_index, step in enumerate(definition.steps):
        # Handle start_from skip logic
        if skipping:
            if step.name == start_from:
                skipping = False
            else:
                continue

        resolved_config = resolve_placeholders(step.config, merged_params)

        # Detect each step type
        if step.step_type == "each":
            step_result = await _execute_each_step(
                step=step,
                resolved_config=resolved_config,
                step_index=step_index,
                merged_params=merged_params,
                prior_outputs=prior_outputs,
                pipeline_name=definition.name,
                run_id=effective_run_id,
                cwd=effective_cwd,
                resolver=resolver,
                cf_client=cf_client,
                get_step_type_fn=get_step_type,
                get_action_fn=_action_registry.__getitem__
                if _action_registry
                else get_action,
            )
        else:
            # Check for loop config
            loop_raw = resolved_config.get("loop")
            if loop_raw is not None and isinstance(loop_raw, dict):
                typed_loop: dict[str, object] = loop_raw  # type: ignore[assignment]
                loop_config = _parse_loop_config(typed_loop)
                # Remove loop key from config before passing to step type
                action_config = {
                    k: v for k, v in resolved_config.items() if k != "loop"
                }
                step_result = await _execute_loop_step(
                    step=step,
                    action_config=action_config,
                    loop_config=loop_config,
                    step_index=step_index,
                    merged_params=merged_params,
                    prior_outputs=prior_outputs,
                    pipeline_name=definition.name,
                    run_id=effective_run_id,
                    cwd=effective_cwd,
                    resolver=resolver,
                    cf_client=cf_client,
                    get_step_type_fn=get_step_type,
                    get_action_fn=_action_registry.__getitem__
                    if _action_registry
                    else get_action,
                )
            else:
                step_result = await _execute_step_once(
                    step=step,
                    resolved_config=resolved_config,
                    step_index=step_index,
                    merged_params=merged_params,
                    prior_outputs=prior_outputs,
                    pipeline_name=definition.name,
                    run_id=effective_run_id,
                    cwd=effective_cwd,
                    resolver=resolver,
                    cf_client=cf_client,
                    get_step_type_fn=get_step_type,
                    get_action_fn=_action_registry.__getitem__
                    if _action_registry
                    else get_action,
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

    return PipelineResult(
        pipeline_name=definition.name,
        status=ExecutionStatus.COMPLETED,
        step_results=step_results,
    )


async def _execute_step_once(
    *,
    step: Any,
    resolved_config: dict[str, object],
    step_index: int,
    merged_params: dict[str, object],
    prior_outputs: dict[str, ActionResult],
    pipeline_name: str,
    run_id: str,
    cwd: str,
    resolver: Any,
    cf_client: Any,
    get_step_type_fn: Any,
    get_action_fn: Any,
    iteration: int = 0,
) -> StepResult:
    """Execute a single step's action sequence once. Returns a StepResult."""
    step_type_impl = get_step_type_fn(step.step_type)
    actions = step_type_impl.expand(step)

    action_results: list[ActionResult] = []
    step_prior = dict(prior_outputs)  # snapshot; updated within step

    for action_index, (action_type, action_config) in enumerate(actions):
        resolved_action_config = resolve_placeholders(action_config, merged_params)
        merged_action_params = {**merged_params, **resolved_action_config}
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
        )

        action_impl = get_action_fn(action_type)
        result: ActionResult = await action_impl.execute(ctx)
        action_results.append(result)

        # Update step_prior for next action in same step
        key = f"{action_type}-{action_index}"
        step_prior[key] = result

        # Checkpoint pause
        if result.outputs.get("checkpoint") == "paused":
            return StepResult(
                step_name=step.name,
                step_type=step.step_type,
                status=ExecutionStatus.PAUSED,
                action_results=action_results,
                iteration=iteration,
            )

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


async def _execute_loop_step(
    *,
    step: Any,
    action_config: dict[str, object],
    loop_config: LoopConfig,
    step_index: int,
    merged_params: dict[str, object],
    prior_outputs: dict[str, ActionResult],
    pipeline_name: str,
    run_id: str,
    cwd: str,
    resolver: Any,
    cf_client: Any,
    get_step_type_fn: Any,
    get_action_fn: Any,
) -> StepResult:
    """Execute a step with loop configuration."""
    if loop_config.strategy is not None:
        _logger.warning(
            "Loop strategy '%s' not implemented, "
            "falling back to basic max-iteration loop",
            loop_config.strategy,
        )

    # Build a synthetic StepConfig with the loop key removed
    from squadron.pipeline.models import StepConfig

    stripped_step = StepConfig(
        step_type=step.step_type,
        name=step.name,
        config=action_config,
    )

    last_result: StepResult | None = None

    for iteration in range(1, loop_config.max + 1):
        result = await _execute_step_once(
            step=stripped_step,
            resolved_config=action_config,
            step_index=step_index,
            merged_params=merged_params,
            prior_outputs=prior_outputs,
            pipeline_name=pipeline_name,
            run_id=run_id,
            cwd=cwd,
            resolver=resolver,
            cf_client=cf_client,
            get_step_type_fn=get_step_type_fn,
            get_action_fn=get_action_fn,
            iteration=iteration,
        )
        last_result = result

        # Checkpoint pause always stops the loop
        if result.status == ExecutionStatus.PAUSED:
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
    match loop_config.on_exhaust:
        case ExhaustBehavior.FAIL:
            return StepResult(
                step_name=step.name,
                step_type=step.step_type,
                status=ExecutionStatus.FAILED,
                action_results=final_results,
                iteration=loop_config.max,
            )
        case ExhaustBehavior.CHECKPOINT:
            return StepResult(
                step_name=step.name,
                step_type=step.step_type,
                status=ExecutionStatus.PAUSED,
                action_results=final_results,
                iteration=loop_config.max,
            )
        case ExhaustBehavior.SKIP:
            return StepResult(
                step_name=step.name,
                step_type=step.step_type,
                status=ExecutionStatus.SKIPPED,
                action_results=final_results,
                iteration=loop_config.max,
            )


def _unpack_inner_steps(raw_steps: list[dict[str, object]]) -> list[Any]:
    """Convert raw YAML step list to StepConfig objects.

    Each element is a single-key dict: {step_type: config_or_scalar}.
    """
    from squadron.pipeline.models import StepConfig

    result: list[StepConfig] = []
    for index, raw_step in enumerate(raw_steps):
        if len(raw_step) != 1:
            continue
        step_type = str(next(iter(raw_step)))
        raw_config = raw_step[step_type]
        if isinstance(raw_config, dict):
            config: dict[str, object] = {str(k): v for k, v in raw_config.items()}  # type: ignore[union-attr]
        elif raw_config is None:
            config = {}
        else:
            config = {"mode": raw_config}
        name = str(config.pop("name", f"{step_type}-{index}"))
        result.append(StepConfig(step_type=step_type, name=name, config=config))
    return result


async def _execute_each_step(
    *,
    step: Any,
    resolved_config: dict[str, object],
    step_index: int,
    merged_params: dict[str, object],
    prior_outputs: dict[str, ActionResult],
    pipeline_name: str,
    run_id: str,
    cwd: str,
    resolver: Any,
    cf_client: Any,
    get_step_type_fn: Any,
    get_action_fn: Any,
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
    inner_steps = _unpack_inner_steps(raw_list)
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
                pipeline_name=pipeline_name,
                run_id=run_id,
                cwd=cwd,
                resolver=resolver,
                cf_client=cf_client,
                get_step_type_fn=get_step_type_fn,
                get_action_fn=get_action_fn,
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
