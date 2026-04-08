"""Summary action — generates a conversation summary and emits it to destinations."""

from __future__ import annotations

import logging

from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.emit import EmitDestination, EmitKind, get_emit, parse_emit_list
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError

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
        raise NotImplementedError(
            "SummaryAction.execute() is wired to _execute_summary() in T9"
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
    """
    if context.sdk_session is None:
        return ActionResult(
            success=False,
            action_type=action_type,
            outputs={},
            error="summary action requires SDK execution mode",
        )

    # Resolve model alias if provided.
    model_id: str | None = None
    if summary_model_alias:
        model_id, _ = context.resolver.resolve(
            action_model=summary_model_alias, step_model=None
        )

    restore_model = context.sdk_session.current_model

    try:
        summary = await context.sdk_session.capture_summary(
            instructions=instructions,
            summary_model=model_id,
            restore_model=restore_model,
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
