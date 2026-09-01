"""Dispatch action — send assembled context to a model via agent registry."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, cast

from squadron.core.agent_registry import get_registry
from squadron.core.models import SDK_RESULT_TYPE, AgentConfig, Message, MessageType
from squadron.metrology.preemption import read_fragment_body, read_fragment_header
from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError
from squadron.pipeline.resolver import ModelPoolNotImplemented, ModelResolutionError
from squadron.providers.base import ProfileName, ProviderType
from squadron.providers.loader import ensure_provider_loaded
from squadron.providers.profiles import get_profile, is_sdk_profile

if TYPE_CHECKING:
    from squadron.pipeline.sdk_session import SDKExecutionSession

_logger = logging.getLogger(__name__)

# The Claude CLI surfaces API-level errors as assistant text with this prefix.
# e.g. "API Error: 500 {"type":"error","error":{...}}"
_CLI_ERROR_PREFIX = "API Error:"


def _check_cli_error(response_text: str) -> ActionResult | None:
    """Return a failed ActionResult if response_text is a CLI-formatted error."""
    if response_text.startswith(_CLI_ERROR_PREFIX):
        return ActionResult(
            success=False,
            action_type=ActionType.DISPATCH,
            outputs={"response": response_text},
            error=response_text,
        )
    return None


async def one_shot_dispatch(
    *,
    prompt: str,
    model_id: str,
    profile_name: str,
    system_prompt: str = "",
    step_name: str = "dispatch",
    run_id: str = "cli",
    branch_idx: object = None,
    allowed_tools: list[str] | None = None,
    cwd: str | None = None,
) -> str:
    """Spawn a one-shot agent and return the concatenated response text."""
    profile = get_profile(profile_name)
    # Registry tool names are not the SDK's vocabulary (Read/Write/Bash), so an
    # SDK-backed profile would silently receive names it cannot resolve and run
    # tool-less. Fail instead — a silent drop is the exact no-op-with-prose
    # failure this path exists to prevent. Slice 265 owns the SDK mapping.
    if allowed_tools and profile.provider == ProviderType.SDK:
        raise ValueError(
            f"Step '{step_name}' declares allowed_tools {allowed_tools!r} but profile "
            f"'{profile_name}' routes to the Claude Code SDK, whose tool vocabulary differs "
            "from the squadron tool registry. Use a non-SDK model, or remove 'allowed_tools'."
        )
    ensure_provider_loaded(profile.provider)

    branch_suffix = f"-b{branch_idx}" if branch_idx is not None else ""
    config = AgentConfig(
        name=f"dispatch-{step_name}{branch_suffix}-{run_id[:8]}",
        agent_type=profile.provider,
        provider=profile.provider,
        model=model_id,
        instructions=system_prompt,
        base_url=profile.base_url,
        # The SDK provider forwards a non-None cwd into ClaudeAgentOptions and
        # previously never received the key; only the non-SDK agent needs it (it
        # is the jail root for registry tools). Gate on the resolved provider so
        # this slice does not change SDK one-shot behavior.
        cwd=None if profile.provider == ProviderType.SDK else cwd,
        allowed_tools=allowed_tools,
        credentials={
            "api_key_env": profile.api_key_env,
            "default_headers": profile.default_headers,
        },
    )

    registry = get_registry()
    agent = await registry.spawn(config)
    try:
        message = Message(
            sender="pipeline",
            recipients=[config.name],
            content=prompt,
            message_type=MessageType.chat,
        )
        response_parts: list[str] = []
        async for response in agent.handle_message(message):
            if response.metadata.get("sdk_type") == SDK_RESULT_TYPE:
                continue
            response_parts.append(response.content)
    finally:
        await registry.shutdown_agent(config.name)

    return "".join(response_parts)


class DispatchAction:
    """Pipeline action that dispatches a prompt to a language model.

    Routes to one of two dispatch paths based on ActionContext:
    - Session path: uses a persistent SDKExecutionSession (SDK executor mode).
    - Agent path: spawns a one-shot agent via the registry (existing path).
    """

    @property
    def action_type(self) -> str:
        return ActionType.DISPATCH

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        # prompt is resolved at runtime: explicit param or prior build_context
        # output.  No static validation needed here.
        return []

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute dispatch, returning ActionResult(success=False) on error.

        Pipeline executor relies on ActionResult.success for flow control,
        so dispatch catches all errors. Unexpected exceptions are logged
        at ERROR level so they surface in diagnostics.
        """
        try:
            return await self._dispatch(context)
        except (ModelResolutionError, ModelPoolNotImplemented, KeyError) as exc:
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=str(exc),
            )
        except Exception as exc:
            _logger.exception("dispatch: unexpected error in step %s", context.step_name)
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=str(exc),
            )

    async def _dispatch(self, context: ActionContext) -> ActionResult:
        """Route to session or agent dispatch path based on resolved profile.

        When no session is available (lazy default or non-SDK pipeline):
        - Explicit 'sdk' profile → guard: FAILED with --strict hint.
        - Any other profile (including None) → agent path.

        When a session is available:
        - Non-SDK profile → agent path.
        - SDK profile (explicit 'sdk' or None) → session path.

        The guard fires when a pool selected an SDK alias at runtime but no
        persistent session was constructed under the lazy default.  The None
        alias_profile case (no profile specified in the alias) routes safely
        through the one-shot agent; only an explicit 'sdk' profile requires a
        persistent session and is therefore blocked without one.
        """
        if context.sdk_session is None:
            _, alias_profile = self._resolve_model(context)
            # Guard: pool selected an explicitly SDK-profiled alias at runtime,
            # but no persistent session is available.
            if alias_profile == ProfileName.SDK:
                step_name = context.step_name
                return ActionResult(
                    success=False,
                    action_type=self.action_type,
                    outputs={},
                    error=(
                        f"Step '{step_name}' resolved to an SDK profile at runtime but no persistent "
                        "session is available. Re-run with --strict to connect at startup, or ensure "
                        "this pool's runtime selection does not yield an SDK alias."
                    ),
                )
            return await self._dispatch_via_agent(context)

        _, alias_profile = self._resolve_model(context)
        if not is_sdk_profile(alias_profile):
            return await self._dispatch_via_agent(context)

        return await self._dispatch_via_session(context, context.sdk_session)

    async def _dispatch_via_session(
        self,
        context: ActionContext,
        session: SDKExecutionSession,
    ) -> ActionResult:
        """Dispatch via a persistent SDKExecutionSession.

        Resolves the model via the cascade chain, switches the session model
        if needed, sends the prompt, and captures the response.

        When no explicit ``prompt`` param is provided, the dispatch action
        looks for a prior ``build_context`` cf-op output and uses its
        ``stdout`` as the prompt.  This is the normal flow for phase steps:
        cf-op(build_context) produces the context text, dispatch sends it.
        """
        # The SDK session path does not carry allowed_tools (slice 265 owns that
        # wiring). Failing here is deliberate: running the step tool-less would
        # return success with the model describing a file it never wrote — the
        # exact silent no-op this slice exists to prevent. Load-time validation
        # cannot catch it, because the routing decision is made at runtime.
        if self._resolve_allowed_tools(context):
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=(
                    f"Step '{context.step_name}' declares 'allowed_tools' but resolved to the "
                    "SDK session path, which does not yet support them. Use a non-SDK model "
                    "for this step, or remove 'allowed_tools'."
                ),
            )

        action_model = str(context.params["model"]) if "model" in context.params else None
        step_model = str(context.params["step_model"]) if "step_model" in context.params else None
        model_id, _ = context.resolver.resolve(action_model, step_model)

        await session.set_model(model_id)

        prompt = self._resolve_prompt(context)
        response_text = await session.dispatch(prompt)

        if error_result := _check_cli_error(response_text):
            return error_result

        return ActionResult(
            success=True,
            action_type=self.action_type,
            outputs={"response": response_text},
            metadata={"model": model_id, "profile": "sdk-session"},
        )

    def _resolve_prompt(self, context: ActionContext) -> str:
        """Return the prompt text for this dispatch.

        Checks ``context.params["prompt"]`` first.  If absent, scans
        ``prior_outputs`` for the most recent ``build_context`` cf-op
        result and uses its ``stdout``.  This is the normal phase-step
        flow where cf-op(build_context) precedes dispatch.

        If neither is present, falls back to the most recent ``review``
        action's findings (the judge-gated fix/review loop flow —
        slice 303 F001): the fix step needs to see what the prior judge
        review actually flagged, not a generic instruction repeated every
        iteration.

        If ``context.params["override_instructions"]`` is set (injected by
        the interactive checkpoint handler), prepends a delimited block to
        the resolved prompt so the model treats it as a directive.
        """
        explicit = context.params.get("prompt")
        if explicit is not None:
            prompt = str(explicit)
        else:
            # Search prior outputs for a build_context cf-op result (reverse
            # order so the most recent one wins).
            prompt = None
            for key in reversed(list(context.prior_outputs)):
                result = context.prior_outputs[key]
                if (
                    result.action_type == ActionType.CF_OP
                    and result.outputs.get("operation") == "build_context"
                    and result.outputs.get("stdout") is not None
                ):
                    _logger.debug("dispatch: using build_context output as prompt")
                    prompt = str(result.outputs["stdout"])
                    break

            if prompt is None:
                prompt = self._resolve_prompt_from_prior_review(context)

            if prompt is None:
                msg = (
                    "No 'prompt' param and no prior build_context or review "
                    "output found. Dispatch requires a prompt — either pass "
                    "one explicitly, include a cf-op(build_context) action, "
                    "or precede this step with a review action."
                )
                raise KeyError(msg)

        return self._apply_pre_emption_fragment(context, self._apply_override(context, prompt))

    @staticmethod
    def _resolve_prompt_from_prior_review(context: ActionContext) -> str | None:
        """Build a fix prompt from the most recent prior ``review`` action.

        Returns None if no prior review action result is present, or if it
        has no findings (e.g. a clean PASS with nothing to act on — in that
        case an initial improvement pass reads better than an empty list).
        """
        for key in reversed(list(context.prior_outputs)):
            result = context.prior_outputs[key]
            if result.action_type != ActionType.REVIEW:
                continue

            findings: list[dict[str, object]] = [
                cast(dict[str, object], f) for f in result.findings if isinstance(f, dict)
            ]
            if not findings:
                return (
                    "The prior review found no actionable findings. Perform "
                    "an initial improvement pass on the artifact."
                )

            lines = [
                f"Address the following findings from the prior review (verdict: {result.verdict}):",
                "",
            ]
            for finding in findings:
                severity = finding.get("severity", "NOTE")
                summary = finding.get("summary", "")
                location = finding.get("location")
                loc_suffix = f" ({location})" if location else ""
                lines.append(f"- [{severity}] {summary}{loc_suffix}")
            return "\n".join(lines)

        return None

    @staticmethod
    def _apply_override(context: ActionContext, prompt: str) -> str:
        """Prepend checkpoint-injected override instructions, if present."""
        override = str(context.params.get("override_instructions", "")).strip()
        if override:
            prefix = (
                f"--- Instructions from checkpoint resolution ---\n"
                f"{override}\n"
                f"--- End instructions ---\n\n"
            )
            return prefix + prompt
        return prompt

    @staticmethod
    def _apply_pre_emption_fragment(context: ActionContext, prompt: str) -> str:
        """Prepend a project's pre-emption fragment, if one is configured.

        Applied *after* ``_apply_override`` so a checkpoint override stays
        the innermost, most urgent instruction: the fragment is standing
        background guidance and must not push a just-injected human
        correction further from the task.

        A fragment problem is never a dispatch failure. All three failure
        modes (missing path, unreadable file, malformed/empty content)
        degrade to a skipped prepend plus a WARNING. This is deliberately
        asymmetric with the audit harness's own failure handling, which
        must persist nothing on failure: a missing fragment has no
        measurement to poison, so proceeding without it costs only the
        guidance, not the integrity of a stored number.
        """
        raw_path = str(context.params.get("pre_emption_fragment", "")).strip()
        if not raw_path:
            return prompt

        path = Path(raw_path).expanduser()
        if not path.is_file():
            _logger.warning(
                "dispatch: pre-emption fragment not found at %s — dispatching without it (step %s)",
                path,
                context.step_name,
            )
            return prompt

        # read_fragment_body returns None for an unreadable file and for one
        # whose header is malformed or whose body is empty; distinguish the
        # two so the warning names a fixable condition.
        if read_fragment_header(path) is None:
            _logger.warning(
                "dispatch: pre-emption fragment at %s is unreadable or has a "
                "malformed header — dispatching without it (step %s)",
                path,
                context.step_name,
            )
            return prompt

        body = read_fragment_body(path)
        if body is None:
            _logger.warning(
                "dispatch: pre-emption fragment at %s has an empty body — "
                "dispatching without it (step %s)",
                path,
                context.step_name,
            )
            return prompt

        prefix = (
            f"--- Pre-emption: known issue classes for this project ---\n"
            f"{body}\n"
            f"--- End pre-emption ---\n\n"
        )
        return prefix + prompt

    def _resolve_model(self, context: ActionContext) -> tuple[str, str | None]:
        """Return (model_id, alias_profile) from the context param cascade."""
        action_model = str(context.params["model"]) if "model" in context.params else None
        step_model = str(context.params["step_model"]) if "step_model" in context.params else None
        return context.resolver.resolve(action_model, step_model)

    @staticmethod
    def _resolve_allowed_tools(context: ActionContext) -> list[str] | None:
        """Narrow ``context.params["allowed_tools"]`` to a list of tool names.

        Names are not re-checked against the tool registry here: load-time
        validation is the single authority (design D3). A malformed value is a
        defect that validation should have caught, so it raises rather than
        silently dropping tools — a silent drop reproduces exactly the
        no-op-with-prose failure this slice exists to prevent.
        """
        raw = context.params.get("allowed_tools")
        if raw is None:
            return None
        if not isinstance(raw, list) or not all(isinstance(name, str) for name in raw):  # pyright: ignore[reportUnknownVariableType]
            raise ValueError(f"dispatch: 'allowed_tools' must be a list of tool names, got {raw!r}")
        return cast(list[str], raw)

    async def _dispatch_via_agent(self, context: ActionContext) -> ActionResult:
        """Dispatch via a one-shot agent from the registry (existing path)."""
        action_model = str(context.params["model"]) if "model" in context.params else None
        step_model = str(context.params["step_model"]) if "step_model" in context.params else None
        model_id, alias_profile = context.resolver.resolve(action_model, step_model)

        profile_name = (
            str(context.params["profile"])
            if "profile" in context.params
            else alias_profile or ProfileName.SDK
        )

        allowed_tools = self._resolve_allowed_tools(context)

        response_text = await one_shot_dispatch(
            prompt=self._resolve_prompt(context),
            model_id=model_id,
            profile_name=profile_name,
            system_prompt=str(context.params.get("system_prompt", "")),
            step_name=context.step_name,
            run_id=context.run_id,
            branch_idx=context.params.get("_fan_out_branch_index"),
            allowed_tools=allowed_tools,
            # Threaded unconditionally for the non-SDK agent (design D2), where
            # AgentConfig.cwd is inert without tools and passing it always removes
            # the latent ProviderError path where tools arrive without a cwd. Not
            # sent to the SDK provider, which forwards a non-None cwd into
            # ClaudeAgentOptions and previously never received the key — threading
            # it there would change one-shot SDK behavior beyond this slice.
            cwd=context.cwd,
        )

        if error_result := _check_cli_error(response_text):
            return error_result

        return ActionResult(
            success=True,
            action_type=self.action_type,
            outputs={"response": response_text},
            metadata={
                "model": model_id,
                "profile": profile_name,
            },
        )


register_action(ActionType.DISPATCH, DispatchAction())
