"""Summary action — generates a conversation summary and emits it to destinations."""

from __future__ import annotations

import logging

from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.emit import EmitDestination, EmitKind, get_emit, parse_emit_list
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError
from squadron.pipeline.summary_oneshot import (
    capture_summary_via_profile,
    is_sdk_profile,
)

_logger = logging.getLogger(__name__)

__all__ = ["SummaryAction", "_execute_summary"]


class SummaryAction:
    """Pipeline action that captures a session summary and emits it."""

    @property
    def action_type(self) -> str:
        return ActionType.SUMMARY

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        errors: list[ValidationError] = []

        template = config.get("template")
        if template is not None and not isinstance(template, str):
            errors.append(
                ValidationError(
                    field="template",
                    message="'template' must be a string",
                    action_type=self.action_type,
                )
            )

        model = config.get("model")
        if model is not None and not isinstance(model, str):
            errors.append(
                ValidationError(
                    field="model",
                    message="'model' must be a string",
                    action_type=self.action_type,
                )
            )

        emit_raw = config.get("emit")
        if emit_raw is not None:
            try:
                parse_emit_list(emit_raw)
            except ValueError as exc:
                errors.append(
                    ValidationError(
                        field="emit",
                        message=str(exc),
                        action_type=self.action_type,
                    )
                )

        return errors

    async def execute(self, context: ActionContext) -> ActionResult:
        from squadron.pipeline.compaction_templates import (
            load_compaction_template,
            render_instructions,
        )

        template_name = str(context.params.get("template", "default"))
        try:
            template = load_compaction_template(template_name)
        except FileNotFoundError as exc:
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=str(exc),
            )

        instructions = render_instructions(
            template,
            keep=None,
            summarize=False,
            pipeline_params=context.params,
        )

        emit_raw = context.params.get("emit")
        try:
            emit_destinations = parse_emit_list(emit_raw)
        except ValueError as exc:
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=str(exc),
            )

        model_raw = context.params.get("model")
        summary_model_alias = model_raw if isinstance(model_raw, str) else None

        return await _execute_summary(
            context=context,
            instructions=instructions,
            summary_model_alias=summary_model_alias,
            emit_destinations=emit_destinations,
            action_type=self.action_type,
        )


async def _execute_summary(
    *,
    context: ActionContext,
    instructions: str,
    summary_model_alias: str | None,
    emit_destinations: list[EmitDestination],
    action_type: str,
) -> ActionResult:
    """Shared helper: capture summary once, dispatch to all emit destinations.

    Non-rotate emit failures log a warning but do not fail the action.
    A rotate emit failure halts the action with success=False.

    Branches on profile:
    - SDK profile (or None): uses sdk_session.capture_summary()
    - Non-SDK profile: uses capture_summary_via_profile() via the provider registry
    """
    # Resolve model alias and profile.
    model_id: str | None = None
    profile: str | None = None
    if summary_model_alias:
        model_id, profile = context.resolver.resolve(
            action_model=summary_model_alias, step_model=None
        )

    # Validate: rotate emit is incompatible with non-SDK profiles.
    has_rotate = any(d.kind is EmitKind.ROTATE for d in emit_destinations)
    if has_rotate and not is_sdk_profile(profile):
        return ActionResult(
            success=False,
            action_type=action_type,
            outputs={},
            error=(
                f"rotate emit is incompatible with non-SDK summary profile {profile!r}"
            ),
        )

    # Guard: SDK profile requires an active SDK session.
    if is_sdk_profile(profile) and context.sdk_session is None:
        return ActionResult(
            success=False,
            action_type=action_type,
            outputs={},
            error="summary action requires SDK execution mode for SDK-profile models",
        )

    # Guard: rotate emit also requires an SDK session (belt-and-suspenders —
    # already blocked above for non-SDK, but also catches SDK + missing session).
    if has_rotate and context.sdk_session is None:
        return ActionResult(
            success=False,
            action_type=action_type,
            outputs={},
            error="rotate emit requires an SDK session",
        )

    try:
        if is_sdk_profile(profile):
            assert context.sdk_session is not None  # narrowed above
            restore_model = context.sdk_session.current_model
            summary = await context.sdk_session.capture_summary(
                instructions=instructions,
                summary_model=model_id,
                restore_model=restore_model,
            )
        else:
            assert profile is not None  # narrowed by is_sdk_profile False
            from squadron.pipeline.summary_context import assemble_dispatch_context

            context_block = assemble_dispatch_context(context.prior_outputs)
            augmented_instructions = (
                f"{context_block}\n\n{instructions}" if context_block else instructions
            )
            summary = await capture_summary_via_profile(
                instructions=augmented_instructions,
                model_id=model_id,
                profile=profile,
            )
    except Exception as exc:
        return ActionResult(
            success=False,
            action_type=action_type,
            outputs={},
            error=str(exc),
        )

    from squadron.pipeline.emit import EmitResult

    emit_results: list[EmitResult] = []
    for dest in emit_destinations:
        emit_fn = get_emit(dest.kind)
        result = await emit_fn(summary, dest, context)
        emit_results.append(result)
        if not result.ok and dest.kind is not EmitKind.ROTATE:
            _logger.warning(
                "emit to %s failed (non-fatal): %s", dest.display(), result.detail
            )

    # Check for rotate failures — these fail the action.
    for dest, res in zip(emit_destinations, emit_results):
        if dest.kind is EmitKind.ROTATE and not res.ok:
            return ActionResult(
                success=False,
                action_type=action_type,
                outputs={
                    "emit_results": [
                        {"destination": r.destination, "ok": r.ok, "detail": r.detail}
                        for r in emit_results
                    ]
                },
                error=res.detail,
            )

    return ActionResult(
        success=True,
        action_type=action_type,
        outputs={
            "summary": summary,
            "instructions": instructions,
            "emit_results": [
                {"destination": r.destination, "ok": r.ok, "detail": r.detail}
                for r in emit_results
            ],
            "source_step_index": context.step_index,
            "source_step_name": context.step_name,
            "summary_model": model_id,
        },
        metadata={"summary_model": model_id or ""},
    )


register_action(ActionType.SUMMARY, SummaryAction())
