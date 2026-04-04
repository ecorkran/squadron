"""CF-op action — delegates to the ContextForge CLI."""

from __future__ import annotations

from enum import StrEnum

from squadron.integrations.context_forge import ContextForgeClient, ContextForgeError
from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError


class CfOperation(StrEnum):
    """Supported ContextForge operations."""

    SET_PHASE = "set_phase"
    SET_SLICE = "set_slice"
    BUILD_CONTEXT = "build_context"
    SUMMARIZE = "summarize"


class CfOpAction:
    """Pipeline action that delegates to the ContextForge CLI."""

    @property
    def action_type(self) -> str:
        return ActionType.CF_OP

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        errors: list[ValidationError] = []

        operation = config.get("operation")
        if operation is None:
            errors.append(
                ValidationError(
                    field="operation",
                    message="'operation' is required",
                    action_type=self.action_type,
                )
            )
            return errors

        if operation not in CfOperation.__members__.values():
            errors.append(
                ValidationError(
                    field="operation",
                    message=f"'{operation}' is not a valid CfOperation",
                    action_type=self.action_type,
                )
            )
            return errors

        if operation == CfOperation.SET_PHASE and "phase" not in config:
            errors.append(
                ValidationError(
                    field="phase",
                    message="'phase' is required for SET_PHASE operation",
                    action_type=self.action_type,
                )
            )

        if operation == CfOperation.SET_SLICE and "slice" not in config:
            errors.append(
                ValidationError(
                    field="slice",
                    message="'slice' is required for SET_SLICE operation",
                    action_type=self.action_type,
                )
            )

        return errors

    async def execute(self, context: ActionContext) -> ActionResult:
        operation_raw = context.params.get("operation")
        if operation_raw is None:
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error="'operation' missing from params",
            )

        operation = CfOperation(str(operation_raw))
        cf_client: ContextForgeClient = context.cf_client  # type: ignore[assignment]

        try:
            match operation:
                case CfOperation.SET_PHASE:
                    phase = context.params["phase"]
                    stdout = cf_client._run(["set", "phase", str(phase)])  # pyright: ignore[reportPrivateUsage]
                case CfOperation.SET_SLICE:
                    slice_id = context.params["slice"]
                    stdout = cf_client._run(["set", "slice", str(slice_id)])  # pyright: ignore[reportPrivateUsage]
                case CfOperation.BUILD_CONTEXT:
                    data = cf_client._run_json(["build", "--json"])  # pyright: ignore[reportPrivateUsage]
                    stdout = data.get("context", "") if isinstance(data, dict) else ""
                case CfOperation.SUMMARIZE:
                    stdout = cf_client._run(["summarize"])  # pyright: ignore[reportPrivateUsage]
        except ContextForgeError as exc:
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=str(exc),
            )

        return ActionResult(
            success=True,
            action_type=self.action_type,
            outputs={"stdout": stdout, "operation": operation.value},
        )


register_action(ActionType.CF_OP, CfOpAction())
