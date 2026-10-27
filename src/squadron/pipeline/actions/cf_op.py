"""CF-op action — delegates to the ContextForge CLI."""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path
from typing import cast

from squadron.integrations.context_forge import (
    GUIDE_VERSION_FILE,
    ContextForgeClient,
    ContextForgeError,
)
from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.intelligence.pools.models import PoolNotFoundError
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError
from squadron.pipeline.resolver import ModelPoolNotImplemented, ModelResolutionError
from squadron.providers.profiles import is_sdk_profile

_logger = logging.getLogger(__name__)

#: Why SET_SLICE refuses a retroactive plan entry (440 D11).
RETROACTIVE_REFUSAL = (
    "slice {index} is a retroactive entry (recorded history, not planned work); "
    "phase steps do not run on it"
)


class CfOperation(StrEnum):
    """Supported ContextForge operations."""

    SET_ARCH = "set_arch"
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

        if operation == CfOperation.SET_ARCH and "plan" not in config:
            errors.append(
                ValidationError(
                    field="plan",
                    message="'plan' is required for SET_ARCH operation",
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
        extra_outputs: dict[str, object] = {}

        try:
            match operation:
                case CfOperation.SET_ARCH:
                    # cf resolves the index (arch doc, else initiative-plan entry)
                    # and switches the initiative and its slice plan together.
                    plan = str(context.params["plan"])
                    stdout = cf_client.run(["set", "arch", plan])
                case CfOperation.SET_PHASE:
                    phase = context.params["phase"]
                    stdout = cf_client.run(["set", "phase", str(phase)])
                case CfOperation.SET_SLICE:
                    slice_id = str(context.params["slice"])
                    _refuse_retroactive(cf_client, slice_id)
                    stdout = cf_client.set_slice(slice_id)
                case CfOperation.BUILD_CONTEXT:
                    build_args = ["build", "--json"]
                    # Use --embed when the step model can't read files natively,
                    # so the context prompt is self-contained for non-SDK dispatch.
                    action_model = str(context.params["model"]) if "model" in context.params else None
                    step_model = (
                        str(context.params["step_model"]) if "step_model" in context.params else None
                    )
                    try:
                        _, alias_profile = context.resolver.resolve(action_model, step_model)
                        if not is_sdk_profile(alias_profile):
                            build_args.append("--embed")
                    except (ModelResolutionError, ModelPoolNotImplemented, PoolNotFoundError):
                        # Narrowed to the resolver's actual raisable set (issue #49).
                        # A resolution failure here means we can't tell whether the
                        # step model can read files, so --embed is skipped and the
                        # prompt may reference files a non-SDK model can't open.
                        # Logged so that degradation is auditable rather than silent.
                        _logger.exception(
                            "cf_op build_context: model resolution failed; --embed skipped "
                            "(prompt may reference files unreadable by the eventual model)"
                        )
                    raw = cf_client.run_json(build_args)
                    data_dict = cast(dict[str, object], raw) if isinstance(raw, dict) else {}
                    stdout = str(data_dict.get("context", ""))
                    extra_outputs = {
                        "cf_version": _best_effort_cf_version(cf_client),
                        "guide_version": _read_guide_version(Path(context.cwd)),
                    }
                case CfOperation.SUMMARIZE:
                    stdout = cf_client.run(["summarize"])
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
            outputs={"stdout": stdout, "operation": operation.value, **extra_outputs},
        )


def _refuse_retroactive(cf_client: ContextForgeClient, slice_id: str) -> None:
    """Raise ``ContextForgeError`` when *slice_id* is a retroactive plan entry.

    An index absent from the plan is left for ``cf set slice`` to judge.
    """
    for entry in cf_client.list_slices():
        if str(entry.index) == slice_id and entry.retroactive:
            raise ContextForgeError(RETROACTIVE_REFUSAL.format(index=entry.index))


def _best_effort_cf_version(cf_client: ContextForgeClient) -> str | None:
    """cf's version for prompt provenance; None (logged) when it cannot be read.

    Provenance only feeds metadata, so a failure here must not block building
    the production prompt.
    """
    try:
        return cf_client.cf_version()
    except ContextForgeError:
        # Swallowed on purpose: metadata-only fact, logged at ERROR with traceback.
        _logger.exception("cf_op build_context: cf version unreadable; recording none")
        return None


def _read_guide_version(project_dir: Path) -> str | None:
    """The installed guide's version, or None when absent, empty or unreadable."""
    version_file = project_dir / GUIDE_VERSION_FILE
    if not version_file.is_file():
        return None
    try:
        version = version_file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        # Swallowed on purpose: metadata-only fact, logged at ERROR with traceback.
        _logger.exception("cf_op build_context: guide version file unreadable: %s", version_file)
        return None
    return version or None


register_action(ActionType.CF_OP, CfOpAction())
