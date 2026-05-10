"""Pipeline classification pre-scan — planning-time step classifier.

Walks a ``PipelineDefinition`` and classifies each model-dispatching step
as ``SDK_REQUIRED``, ``NON_SDK``, or ``POOL_UNCERTAIN`` without invoking
any pool-selection side effects.

Side-effect-freeness contract (slice 243 §8):
- ``resolve_model_alias`` is a pure dict lookup; no mutation.
- ``ModelResolver.cascade_candidates`` is a pure read of resolver config
  plus the two per-call inputs; no alias resolution, no pool selection.
- ``ModelPool.models`` is static data on a frozen dataclass.
- ``pool_backend.get_pool()`` returns the static pool definition; it does
  NOT call ``select()``.

Any future change that introduces a side effect on these paths will be
caught by ``test_classification_is_idempotent_and_side_effect_free``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, cast

from squadron.models.aliases import resolve_model_alias
from squadron.providers.profiles import is_sdk_profile

if TYPE_CHECKING:
    from squadron.pipeline.intelligence.pools.backend import PoolBackend
    from squadron.pipeline.models import PipelineDefinition, StepConfig
    from squadron.pipeline.resolver import ModelResolver

# Action types that dispatch to a model and must be classified. Step types
# (e.g. ``design``/``tasks``/``implement``) expand into one or more of these
# action types via ``StepType.expand()`` — the classifier walks the expansion
# rather than matching step-type names directly so that phase steps and other
# composite step types are covered.
_MODEL_DISPATCHING_ACTION_TYPES = frozenset({"dispatch", "review", "summary", "compact"})

# Action types whose classification contributes to ``needs_persistent_session``.
# Reviews route through the one-shot ClaudeSDKAgent, not the persistent session.
PERSISTENT_SESSION_STEP_TYPES = frozenset({"dispatch", "summary", "compact"})

# Action types whose classification contributes to ``needs_one_shot_claude``.
_ONE_SHOT_STEP_TYPES = frozenset({"review"})


class StepClass(StrEnum):
    """Classification of a single model-dispatching step."""

    SDK_REQUIRED = "sdk_required"
    NON_SDK = "non_sdk"
    POOL_UNCERTAIN = "pool_uncertain"


class PipelineShape(StrEnum):
    """Aggregate shape of a pipeline's Claude-auth requirements."""

    CLAUDE_REQUIRED_PERSISTENT = "claude_required_persistent"
    CLAUDE_REQUIRED_ONE_SHOT = "claude_required_one_shot"
    CLAUDE_FREE = "claude_free"


class PoolClassificationPolicy(StrEnum):
    """Controls how POOL_UNCERTAIN steps factor into needs_persistent_session.

    LAZY (default): pool-uncertain steps do NOT force session construction at
    startup.  The mid-run hook in execute_pipeline will connect lazily if a
    step resolves to an SDK alias at runtime.

    STRICT: pool-uncertain steps are treated conservatively as SDK-required,
    matching the pre-245 behaviour.  A persistent session is always constructed
    before the pipeline starts.
    """

    LAZY = "lazy"
    STRICT = "strict"


class ClassificationError(Exception):
    """Raised when a step cannot be classified at planning time.

    Conditions:
    - All cascade levels are None (misconfigured step).
    - A pool candidate is encountered but no pool backend is configured.
    """


@dataclass(frozen=True)
class StepClassification:
    """Classification result for a single model-dispatching step."""

    step_name: str
    step_index: int
    action_type: str
    resolved_alias: str | None  # None for pool steps
    resolved_model_id: str | None  # None for POOL_UNCERTAIN
    profile: str | None  # None for POOL_UNCERTAIN or unset profile
    classification: StepClass
    rationale: str
    pool_name: str | None = None  # set iff classification == POOL_UNCERTAIN
    container_path: str | None = None  # inner step label; None for top-level rows


@dataclass(frozen=True)
class PipelineClassification:
    """Classification result for an entire pipeline."""

    pipeline_name: str
    steps: tuple[StepClassification, ...]
    policy: PoolClassificationPolicy = PoolClassificationPolicy.LAZY

    @property
    def needs_persistent_session(self) -> bool:
        """True iff at least one dispatch/summary/compact step requires a persistent session.

        Under LAZY (default): only SDK_REQUIRED steps count.  POOL_UNCERTAIN steps
        do not force session construction — the mid-run hook in execute_pipeline
        handles lazy connection when a step resolves to an SDK alias at runtime.

        Under STRICT: POOL_UNCERTAIN steps are treated as SDK-required, matching the
        pre-245 conservative behaviour.

        Reviews are intentionally excluded — they route through the provider registry's
        one-shot ClaudeSDKAgent, not the persistent session.  Arch §Envisioned State
        point 2.
        """
        if self.policy == PoolClassificationPolicy.STRICT:
            counted = (StepClass.SDK_REQUIRED, StepClass.POOL_UNCERTAIN)
        else:
            counted = (StepClass.SDK_REQUIRED,)
        return any(
            s.classification in counted
            for s in self.steps
            if s.action_type in PERSISTENT_SESSION_STEP_TYPES
        )

    @property
    def needs_one_shot_claude(self) -> bool:
        """True iff at least one review step routes through the one-shot
        ClaudeSDKAgent path with an SDK (or POOL_UNCERTAIN) profile.

        Per arch §Envisioned State point 2, the one-shot path is used by
        review steps.  Dispatch/summary/compact steps that resolve to SDK
        drive ``needs_persistent_session``, not this property.

        Dispatch-via-agent with SDK profile is empty post-slice-242 but
        included in the filter for arch-correctness.
        """
        return any(
            s.classification in (StepClass.SDK_REQUIRED, StepClass.POOL_UNCERTAIN)
            for s in self.steps
            if s.action_type in _ONE_SHOT_STEP_TYPES
        )

    @property
    def shape(self) -> PipelineShape:
        """Derive the aggregate pipeline shape from the two boolean properties."""
        if self.needs_persistent_session:
            return PipelineShape.CLAUDE_REQUIRED_PERSISTENT
        if self.needs_one_shot_claude:
            return PipelineShape.CLAUDE_REQUIRED_ONE_SHOT
        return PipelineShape.CLAUDE_FREE


def _classify_alias_set(
    aliases: list[str],
    step: StepConfig,
    step_index: int,
    action_type: str,
    rationale_label: str,
) -> StepClassification:
    """Classify a set of aliases as NON_SDK, SDK_REQUIRED, or POOL_UNCERTAIN.

    Used by both pool-based and fan_out literal-list classification paths.
    """
    member_profiles = [resolve_model_alias(alias)[1] for alias in aliases]
    all_non_sdk = all(not is_sdk_profile(p) for p in member_profiles)
    all_sdk = all(is_sdk_profile(p) for p in member_profiles)
    if all_non_sdk:
        classification, rationale = StepClass.NON_SDK, f"{rationale_label}: all non-SDK"
    elif all_sdk:
        classification, rationale = StepClass.SDK_REQUIRED, f"{rationale_label}: all SDK"
    else:
        classification, rationale = (
            StepClass.POOL_UNCERTAIN,
            f"{rationale_label}: mixed SDK and non-SDK",
        )
    return StepClassification(
        step_name=step.name,
        step_index=step_index,
        action_type=action_type,
        resolved_alias=None,
        resolved_model_id=None,
        profile=None,
        classification=classification,
        rationale=rationale,
    )


def _classify_pool_step(
    step: StepConfig,
    step_index: int,
    action_type: str,
    pool_name: str,
    pool_backend: PoolBackend,
) -> StepClassification:
    """Classify an action whose resolved candidate is a pool reference.

    Walks ``pool.models`` statically — never calls ``pool_backend.select()``.
    """
    pool = pool_backend.get_pool(pool_name)
    result = _classify_alias_set(pool.models, step, step_index, action_type, "pool members")
    # Preserve pool_name on the result (frozen dataclass — replace via copy).
    return StepClassification(
        step_name=result.step_name,
        step_index=result.step_index,
        action_type=result.action_type,
        resolved_alias=result.resolved_alias,
        resolved_model_id=result.resolved_model_id,
        profile=result.profile,
        classification=result.classification,
        rationale=result.rationale,
        pool_name=pool_name,
    )


def _classify_container_inner(
    inner: StepConfig,
    parent_step: StepConfig,
    step_index: int,
    resolver: ModelResolver,
    pool_backend: PoolBackend | None,
    classify_params: dict[str, object],
) -> list[StepClassification]:
    """Classify a single inner step returned by a container step's inner_steps().

    Handles the ``_fan_out_aggregate`` sentinel specially; for all other inner
    step types, expands actions and classifies each dispatching action.
    """
    from squadron.pipeline.executor import resolve_placeholders
    from squadron.pipeline.steps import get_step_type

    if inner.step_type == "_fan_out_aggregate":
        models_val = inner.config.get("models")
        if isinstance(models_val, str) and models_val.startswith("pool:"):
            pool_name = models_val.removeprefix("pool:")
            if pool_backend is None:
                raise ClassificationError(
                    f"fan_out step {parent_step.name!r} (index {step_index}) "
                    f"references pool {pool_name!r} but no pool backend is configured."
                )
            result = _classify_pool_step(parent_step, step_index, "dispatch", pool_name, pool_backend)
            return [
                StepClassification(
                    step_name=result.step_name,
                    step_index=result.step_index,
                    action_type=result.action_type,
                    resolved_alias=result.resolved_alias,
                    resolved_model_id=result.resolved_model_id,
                    profile=result.profile,
                    classification=result.classification,
                    rationale=result.rationale,
                    pool_name=result.pool_name,
                    container_path="dispatch",
                )
            ]
        if isinstance(models_val, list):
            aliases = [str(a) for a in cast(list[object], models_val)]
            result = _classify_alias_set(
                aliases, parent_step, step_index, "dispatch", "fan_out literal list"
            )
            return [
                StepClassification(
                    step_name=result.step_name,
                    step_index=result.step_index,
                    action_type=result.action_type,
                    resolved_alias=result.resolved_alias,
                    resolved_model_id=result.resolved_model_id,
                    profile=result.profile,
                    classification=result.classification,
                    rationale=result.rationale,
                    container_path="dispatch",
                )
            ]
        return []

    assert inner.step_type != "_fan_out_aggregate"

    try:
        inner_impl = get_step_type(inner.step_type)
    except KeyError:
        return []

    actions = inner_impl.expand(inner)
    row_results: list[StepClassification] = []
    for action_type, action_cfg in actions:
        if action_type not in _MODEL_DISPATCHING_ACTION_TYPES:
            continue
        resolved_cfg = resolve_placeholders(action_cfg, classify_params)
        action_model_raw = resolved_cfg.get("model")
        action_model = action_model_raw if isinstance(action_model_raw, str) else None

        candidates = resolver.cascade_candidates(action_model=action_model, step_model=None)
        candidate = next((c for c in candidates if c is not None), None)

        if candidate is None:
            raise ClassificationError(
                f"Container step {parent_step.name!r} inner step {inner.name!r} "
                f"action {action_type!r} has no model at any cascade level."
            )

        if candidate.startswith("pool:"):
            pool_name = candidate.removeprefix("pool:")
            if pool_backend is None:
                raise ClassificationError(
                    f"Container step {parent_step.name!r} inner step {inner.name!r} "
                    f"resolves to pool {pool_name!r} but no pool backend is configured."
                )
            base = _classify_pool_step(parent_step, step_index, action_type, pool_name, pool_backend)
            row_results.append(
                StepClassification(
                    step_name=base.step_name,
                    step_index=base.step_index,
                    action_type=base.action_type,
                    resolved_alias=base.resolved_alias,
                    resolved_model_id=base.resolved_model_id,
                    profile=base.profile,
                    classification=base.classification,
                    rationale=base.rationale,
                    pool_name=base.pool_name,
                    container_path=inner.name,
                )
            )
            continue

        model_id, profile = resolve_model_alias(candidate)
        classification = StepClass.SDK_REQUIRED if is_sdk_profile(profile) else StepClass.NON_SDK
        rationale = (
            f"alias {candidate!r} resolves to profile {profile!r} (SDK)"
            if is_sdk_profile(profile)
            else f"alias {candidate!r} resolves to profile {profile!r} (non-SDK)"
        )
        row_results.append(
            StepClassification(
                step_name=parent_step.name,
                step_index=step_index,
                action_type=action_type,
                resolved_alias=candidate,
                resolved_model_id=model_id,
                profile=profile,
                classification=classification,
                rationale=rationale,
                container_path=inner.name,
            )
        )

    return row_results


def classify_pipeline(
    definition: PipelineDefinition,
    resolver: ModelResolver,
    pool_backend: PoolBackend | None = None,
    policy: PoolClassificationPolicy = PoolClassificationPolicy.LAZY,
) -> PipelineClassification:
    """Classify each model-dispatching action in *definition*.

    For each step, the function calls ``StepType.expand()`` and classifies
    every resulting ``dispatch``/``review``/``summary``/``compact`` action.
    Composite step types (``design``/``tasks``/``implement``) expand into
    multiple actions — each is classified independently. Non-model actions
    (``cf-op``, ``commit``, ``checkpoint``, ``devlog``) are skipped, and
    container step types whose ``expand()`` returns ``[]`` (``each``,
    ``loop``, ``fan_out``) contribute no rows.

    The returned ``StepClassification`` rows carry ``action_type`` (the
    expanded action, e.g. ``dispatch``) and ``step_name`` (the parent step,
    e.g. ``design-0``). Action-config templates like ``{model}`` are
    resolved against ``definition.params`` (excluding ``required`` markers)
    before cascade resolution.

    Side-effect-freeness: this function never calls ``pool_backend.select()``.
    Pool steps are classified by inspecting ``pool.models`` statically.

    Args:
        definition: The pipeline to classify.
        resolver: The same ``ModelResolver`` instance the executor will use.
                  Its ``cascade_candidates()`` method is the single source
                  of cascade ordering.
        pool_backend: Required only when any step resolves to a ``pool:``
                      candidate.  If ``None`` and a pool candidate is
                      encountered, raises ``ClassificationError``.
        policy: Controls how POOL_UNCERTAIN steps affect
                ``needs_persistent_session``.  Defaults to ``LAZY`` (no
                upfront session for uncertain steps).  Pass ``STRICT`` to
                use the pre-245 conservative behaviour.

    Raises:
        ClassificationError: If a step's entire cascade is None, or if a
            pool candidate is encountered but ``pool_backend`` is None.
        PoolNotFoundError: Propagated from ``pool_backend.get_pool()``.
    """
    # Local imports to avoid circular imports at module load: the steps
    # registry and executor both import from pipeline.models which is also
    # imported here.
    from squadron.pipeline.executor import resolve_placeholders
    from squadron.pipeline.steps import bootstrap_step_types, get_step_type

    bootstrap_step_types()

    # Pipeline-default params (e.g. ``model: sonnet``) used to resolve template
    # placeholders like ``{model}`` in expanded action configs. ``required`` markers
    # are excluded since they have no concrete value.
    classify_params: dict[str, object] = {k: v for k, v in definition.params.items() if v != "required"}

    results: list[StepClassification] = []

    for step_index, step in enumerate(definition.steps):
        try:
            step_impl = get_step_type(step.step_type)
        except KeyError:
            # Unregistered step type — let the validator catch it; skip here.
            continue

        # expand() returns a list of (action_type, action_config). Composite
        # step types (design/tasks/implement) expand into multiple actions;
        # leaf step types (dispatch/review/summary/compact) expand into one
        # matching action; container step types (each/loop/fan_out) return
        # an empty list and are handled by the executor directly. Expansion
        # errors (e.g. missing required keys) propagate — call validate_pipeline
        # before classify_pipeline if you need a clean error path.
        actions = step_impl.expand(step)

        if not actions:
            _inner_steps_fn = getattr(step_impl, "inner_steps", None)
            container_inners: list[StepConfig] = (
                _inner_steps_fn(step) if _inner_steps_fn is not None else []
            )
            for inner in container_inners:
                results.extend(
                    _classify_container_inner(
                        inner, step, step_index, resolver, pool_backend, classify_params
                    )
                )
            continue

        step_model_raw = step.config.get("step_model")
        step_model = step_model_raw if isinstance(step_model_raw, str) else None
        if step_model is not None:
            step_model = resolve_placeholders({"v": step_model}, classify_params)["v"]
            step_model = step_model if isinstance(step_model, str) else None

        for action_type, action_cfg in actions:
            if action_type not in _MODEL_DISPATCHING_ACTION_TYPES:
                continue

            # Resolve {model}-style placeholders in the action config against
            # pipeline-default params so the cascade sees the actual alias
            # (e.g. ``sonnet``) rather than the literal template string.
            resolved_cfg = resolve_placeholders(action_cfg, classify_params)
            action_model_raw = resolved_cfg.get("model")
            action_model = action_model_raw if isinstance(action_model_raw, str) else None

            candidates = resolver.cascade_candidates(
                action_model=action_model,
                step_model=step_model,
            )
            candidate = next((c for c in candidates if c is not None), None)

            if candidate is None:
                raise ClassificationError(
                    f"Step {step.name!r} (index {step_index}) action "
                    f"{action_type!r} has no model at any cascade level. "
                    "Set a pipeline model, step model, or config default."
                )

            if candidate.startswith("pool:"):
                pool_name = candidate.removeprefix("pool:")
                if pool_backend is None:
                    raise ClassificationError(
                        f"Step {step.name!r} (index {step_index}) action "
                        f"{action_type!r} resolves to pool {pool_name!r} "
                        "but no pool backend is configured."
                    )
                results.append(
                    _classify_pool_step(step, step_index, action_type, pool_name, pool_backend)
                )
                continue

            model_id, profile = resolve_model_alias(candidate)
            classification = StepClass.SDK_REQUIRED if is_sdk_profile(profile) else StepClass.NON_SDK
            rationale = (
                f"alias {candidate!r} resolves to profile {profile!r} (SDK)"
                if is_sdk_profile(profile)
                else f"alias {candidate!r} resolves to profile {profile!r} (non-SDK)"
            )
            results.append(
                StepClassification(
                    step_name=step.name,
                    step_index=step_index,
                    action_type=action_type,
                    resolved_alias=candidate,
                    resolved_model_id=model_id,
                    profile=profile,
                    classification=classification,
                    rationale=rationale,
                )
            )

    return PipelineClassification(
        pipeline_name=definition.name,
        steps=tuple(results),
        policy=policy,
    )
