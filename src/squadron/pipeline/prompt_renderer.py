"""Prompt-only pipeline renderer — generates step instructions without execution.

Converts pipeline step configs into structured instruction objects that can be
serialized as JSON and consumed by external callers (e.g. the /sq:run slash
command). This is the core of the --prompt-only mode.
"""

from __future__ import annotations

import json
import logging
import shlex
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, cast

from squadron.pipeline.actions import ActionType
from squadron.pipeline.compaction_templates import (
    load_compaction_template,
    render_instructions,
)
from squadron.pipeline.executor import resolve_placeholders
from squadron.pipeline.steps import get_step_type
from squadron.pipeline.summary_oneshot import is_sdk_profile

if TYPE_CHECKING:
    from squadron.pipeline.models import StepConfig
    from squadron.pipeline.resolver import ModelResolver

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ActionInstruction:
    """A single action's instructions for prompt-only output."""

    action_type: str
    instruction: str
    command: str | None = None
    model: str | None = None
    model_switch: str | None = None
    template: str | None = None
    trigger: str | None = None
    resolved_instructions: str | None = None
    emit: list[str] | None = None


@dataclass
class StepInstructions:
    """Complete instructions for one pipeline step."""

    run_id: str
    step_name: str
    step_type: str
    step_index: int
    total_steps: int
    actions: list[ActionInstruction]

    def to_json(self) -> str:
        """Serialize to indented JSON string."""
        return json.dumps(asdict(self), indent=2)


@dataclass
class CompletionResult:
    """Returned when no more steps remain in the pipeline."""

    status: str
    message: str
    run_id: str

    def to_json(self) -> str:
        """Serialize to indented JSON string."""
        return json.dumps(asdict(self), indent=2)


# ---------------------------------------------------------------------------
# Action instruction builders
# ---------------------------------------------------------------------------


def _render_cf_op(
    config: dict[str, object], params: dict[str, object]
) -> ActionInstruction:
    """Build instruction for a cf-op action (set_phase or build_context)."""
    operation = str(config.get("operation", ""))
    if operation == "set_phase":
        phase = config.get("phase", "")
        return ActionInstruction(
            action_type=ActionType.CF_OP,
            instruction=f"Set phase to {phase}",
            command=f"cf set phase {phase}",
        )
    if operation == "set_slice":
        slice_id = config.get("slice", "")
        return ActionInstruction(
            action_type=ActionType.CF_OP,
            instruction=f"Set slice to {slice_id}",
            command=f"cf set slice {slice_id}",
        )
    if operation == "build_context":
        return ActionInstruction(
            action_type=ActionType.CF_OP,
            instruction="Build context",
            command="cf build",
        )
    if operation == "summarize":
        return ActionInstruction(
            action_type=ActionType.CF_OP,
            instruction="Summarize context",
            command="cf summarize",
        )
    return ActionInstruction(
        action_type=ActionType.CF_OP,
        instruction=f"CF operation: {operation}",
        command=f"cf {operation}",
    )


def _render_dispatch(
    config: dict[str, object],
    params: dict[str, object],
    resolver: ModelResolver,
) -> ActionInstruction:
    """Build instruction for a dispatch action (in-session work)."""
    action_model = str(config["model"]) if config.get("model") else None
    model_id: str | None = None
    model_switch: str | None = None

    if action_model is not None:
        try:
            model_id, _ = resolver.resolve(action_model)
        except Exception:
            model_id = action_model
        model_switch = f"/model {action_model}"

    return ActionInstruction(
        action_type=ActionType.DISPATCH,
        instruction="Execute the work using the assembled context",
        model=model_id or action_model,
        model_switch=model_switch,
    )


def _render_review(
    config: dict[str, object],
    params: dict[str, object],
    resolver: ModelResolver,
) -> ActionInstruction:
    """Build instruction for a review action."""
    template_name = str(config.get("template", ""))
    review_model_alias = config.get("model")
    review_model_id: str | None = None

    # Keep the raw alias for the CLI command; resolve for the model field
    alias_str: str | None = None
    if review_model_alias is not None:
        alias_str = str(review_model_alias)
        try:
            review_model_id, _ = resolver.resolve(alias_str)
        except Exception:
            review_model_id = alias_str

    # Build the CLI command — template is the subcommand, not a flag
    target = str(params.get("slice", ""))
    cmd_parts = ["sq", "review", template_name]
    if target:
        cmd_parts.append(target)
    if alias_str:
        cmd_parts.extend(["--model", alias_str])
    cmd_parts.append("-v")

    return ActionInstruction(
        action_type=ActionType.REVIEW,
        instruction=f"Review using template '{template_name}'",
        command=" ".join(cmd_parts),
        model=review_model_id,
        template=template_name,
    )


def _render_checkpoint(
    config: dict[str, object],
    params: dict[str, object],
) -> ActionInstruction:
    """Build instruction for a checkpoint action."""
    trigger = str(config.get("trigger", "on-concerns"))
    run_id = str(params.get("run_id", "{run_id}"))

    _OPTIONS = (
        "  [a] Accept   — proceed; review findings become instructions"
        " for next dispatch\n"
        "  [o] Override — enter custom instructions; proceed with those\n"
        f"  [e] Exit     — stop pipeline; resume with: sq run --resume {run_id}\n"
        "Note: in prompt-only mode, you are the executor."
        " Choose an option and act accordingly."
    )

    if trigger == "never":
        instruction = "Skip checkpoint (never pause)"
    elif trigger == "always":
        instruction = f"Always pause for user decision.\n{_OPTIONS}"
    elif trigger == "on-fail":
        instruction = f"If review verdict is FAIL:\n{_OPTIONS}"
    else:
        # on-concerns (default) and any unknown trigger
        instruction = f"If review verdict is CONCERNS or FAIL:\n{_OPTIONS}"

    return ActionInstruction(
        action_type=ActionType.CHECKPOINT,
        instruction=instruction,
        trigger=trigger,
    )


def _render_commit(
    config: dict[str, object],
    params: dict[str, object],
) -> ActionInstruction:
    """Build instruction for a commit action."""
    prefix = str(config.get("message_prefix", ""))
    message = f"{prefix}: pipeline step" if prefix else "chore: pipeline step"

    return ActionInstruction(
        action_type=ActionType.COMMIT,
        instruction="Commit the artifacts",
        command=f"git add -A && git commit -m '{message}'",
    )


def _render_summary(
    config: dict[str, object],
    params: dict[str, object],
    resolver: ModelResolver,
) -> ActionInstruction:
    """Build instruction for a summary action.

    SDK profiles (or no model alias) emit a ``model_switch`` directive.
    Non-SDK profiles emit a ``command`` with a runnable ``sq _summary-run …``
    invocation.  No path emits both.
    """
    template_name = str(config.get("template", "default"))
    model_raw = config.get("model")
    emit_raw = config.get("emit")

    model_id: str | None = None
    profile: str | None = None
    model_switch: str | None = None
    command: str | None = None

    if model_raw is not None:
        alias = str(model_raw)
        try:
            model_id, profile = resolver.resolve(alias)
        except Exception:
            model_id = alias
            profile = None

        if is_sdk_profile(profile):
            model_switch = f"/model {alias}"
        else:
            # Non-SDK: build a runnable sq _summary-run command.
            cmd_parts = [
                "sq",
                "_summary-run",
                "--template",
                template_name,
                "--profile",
                profile or "",
                "--model",
                model_id or alias,
            ]
            for key, value in params.items():
                cmd_parts.extend(["--param", f"{key}={shlex.quote(str(value))}"])
            command = " ".join(cmd_parts)

    try:
        template = load_compaction_template(template_name)
        resolved = render_instructions(template, pipeline_params=params)
    except FileNotFoundError:
        resolved = f"(template '{template_name}' not found)"

    emit_destinations: list[str] | None = None
    if isinstance(emit_raw, list):
        emit_list = cast(list[object], emit_raw)
        emit_destinations = [str(e) for e in emit_list] or None

    return ActionInstruction(
        action_type=ActionType.SUMMARY,
        instruction="Generate a session summary following the resolved instructions",
        command=command,
        model=model_id,
        model_switch=model_switch,
        template=template_name,
        resolved_instructions=resolved,
        emit=emit_destinations,
    )


def _render_devlog(
    config: dict[str, object],
    params: dict[str, object],
) -> ActionInstruction:
    """Build instruction for a devlog action."""
    mode = str(config.get("mode", "auto"))
    return ActionInstruction(
        action_type=ActionType.DEVLOG,
        instruction=f"Write DEVLOG entry (mode: {mode})",
    )


# Map action type -> builder function signature
_BUILDERS: dict[str, object] = {
    ActionType.CF_OP: _render_cf_op,
    ActionType.DISPATCH: _render_dispatch,
    ActionType.REVIEW: _render_review,
    ActionType.CHECKPOINT: _render_checkpoint,
    ActionType.COMMIT: _render_commit,
    ActionType.SUMMARY: _render_summary,
    ActionType.DEVLOG: _render_devlog,
}


def _build_action_instruction(
    action_type: str,
    config: dict[str, object],
    params: dict[str, object],
    resolver: ModelResolver,
) -> ActionInstruction:
    """Dispatch to the appropriate builder for an action type."""
    builder = _BUILDERS.get(action_type)
    if builder is None:
        return ActionInstruction(
            action_type=action_type,
            instruction=f"Execute {action_type} action",
        )

    # Builders that need the resolver
    if action_type in (ActionType.DISPATCH, ActionType.REVIEW, ActionType.SUMMARY):
        return builder(config, params, resolver)  # type: ignore[operator]

    return builder(config, params)  # type: ignore[operator]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def render_step_instructions(
    step: StepConfig,
    *,
    step_index: int,
    total_steps: int,
    params: dict[str, object],
    resolver: ModelResolver,
    run_id: str,
) -> StepInstructions:
    """Expand a step into executable instruction objects.

    Uses existing step type ``expand()`` to get the action sequence,
    then generates an ``ActionInstruction`` for each action.
    """
    # Ensure step types are registered
    import squadron.pipeline.steps.compact as _s_compact  # noqa: F401
    import squadron.pipeline.steps.devlog as _s_devlog  # noqa: F401
    import squadron.pipeline.steps.dispatch as _s_dispatch  # noqa: F401
    import squadron.pipeline.steps.phase as _s_phase  # noqa: F401
    import squadron.pipeline.steps.review as _s_review  # noqa: F401
    import squadron.pipeline.steps.summary as _s_summary  # noqa: F401

    _ = (_s_compact, _s_devlog, _s_dispatch, _s_phase, _s_review, _s_summary)

    step_type_impl = get_step_type(step.step_type)
    actions = step_type_impl.expand(step)

    # Inject run_id into params so renderers (e.g. checkpoint) can reference it.
    render_params = {**params, "run_id": run_id}

    instructions: list[ActionInstruction] = []
    for action_type, action_config in actions:
        resolved_config = resolve_placeholders(action_config, render_params)
        instruction = _build_action_instruction(
            action_type, resolved_config, render_params, resolver
        )
        instructions.append(instruction)

    return StepInstructions(
        run_id=run_id,
        step_name=step.name,
        step_type=step.step_type,
        step_index=step_index,
        total_steps=total_steps,
        actions=instructions,
    )
