"""Summary action — generates a conversation summary and emits it to destinations."""

from __future__ import annotations

from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.emit import parse_emit_list
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError


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


register_action(ActionType.SUMMARY, SummaryAction())
