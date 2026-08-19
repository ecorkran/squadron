"""Tests for pipeline classification pre-scan (slice 243).

Covers:
  - ModelResolver.cascade_candidates() (T3)
  - PipelineClassification property logic (T5)
  - classify_pipeline() non-pool path (T7)
  - classify_pipeline() pool path (T9)
  - Side-effect-freeness regression (T10)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from squadron.pipeline.classification import (
    ClassificationError,
    PipelineClassification,
    PipelineShape,
    PoolClassificationPolicy,
    StepClass,
    StepClassification,
    classify_pipeline,
)
from squadron.pipeline.intelligence.pools.models import (
    ModelPool,
    PoolNotFoundError,
    SelectionContext,
)
from squadron.pipeline.models import PipelineDefinition, StepConfig
from squadron.pipeline.resolver import ModelResolver
from squadron.pipeline.steps.collection import EachStepType

# ---------------------------------------------------------------------------
# T1 — SpyPoolBackend and definition builders
# ---------------------------------------------------------------------------


class SpyPoolBackend:
    """PoolBackend that records select() calls and delegates get_pool/list/reset
    to an in-memory pool registry.

    ``select_call_count`` is the primary spy assertion target: the classifier
    must never increment it.
    """

    def __init__(self, pools: dict[str, ModelPool] | None = None) -> None:
        self._pools: dict[str, ModelPool] = pools or {}
        self.select_call_count: int = 0

    def select(self, pool_name: str, context: SelectionContext) -> str:  # noqa: ARG002
        self.select_call_count += 1
        if pool_name not in self._pools:
            raise PoolNotFoundError(f"No pool: {pool_name!r}")
        return self._pools[pool_name].models[0]

    def get_pool(self, pool_name: str) -> ModelPool:
        if pool_name not in self._pools:
            raise PoolNotFoundError(f"No pool: {pool_name!r}")
        return self._pools[pool_name]

    def list_pools(self) -> dict[str, ModelPool]:
        return dict(self._pools)

    def reset_pool_state(self, pool_name: str) -> None:  # noqa: ARG002
        pass


def make_step(
    step_type: str,
    name: str,
    config: dict[str, object] | None = None,
) -> StepConfig:
    """Build a StepConfig without loading YAML."""
    return StepConfig(step_type=step_type, name=name, config=config or {})


def make_pipeline(
    steps: list[StepConfig],
    name: str = "test-pipeline",
    model: str | None = None,
) -> PipelineDefinition:
    """Wrap a step list in a PipelineDefinition."""
    return PipelineDefinition(
        name=name,
        description="test pipeline",
        params={},
        steps=steps,
        model=model,
    )


def make_resolver(
    cli_override: str | None = None,
    pipeline_model: str | None = None,
    config_default: str | None = None,
    pool_backend: SpyPoolBackend | None = None,
) -> ModelResolver:
    """Build a ModelResolver for tests."""
    return ModelResolver(
        cli_override=cli_override,
        pipeline_model=pipeline_model,
        config_default=config_default,
        pool_backend=pool_backend,
    )


# ---------------------------------------------------------------------------
# T1 success verification
# ---------------------------------------------------------------------------


def test_spy_pool_backend_initial_count() -> None:
    spy = SpyPoolBackend()
    assert spy.select_call_count == 0


def test_spy_pool_backend_select_increments() -> None:
    pool = ModelPool(name="p", description="", models=["minimax"], strategy="random")
    spy = SpyPoolBackend({"p": pool})
    spy.select("p", SelectionContext(pool_name="p", action_type="dispatch"))
    assert spy.select_call_count == 1


def test_spy_pool_backend_get_pool_returns_pool() -> None:
    pool = ModelPool(name="p", description="d", models=["sonnet"], strategy="random")
    spy = SpyPoolBackend({"p": pool})
    result = spy.get_pool("p")
    assert result.name == "p"
    assert result.models == ["sonnet"]


# ---------------------------------------------------------------------------
# T3 — cascade_candidates tests
# ---------------------------------------------------------------------------


def test_cascade_candidates_returns_ordered_inputs() -> None:
    resolver = ModelResolver(
        cli_override="a",
        pipeline_model="d",
        config_default="e",
    )
    result = resolver.cascade_candidates(action_model="b", step_model="c")
    assert result == ("a", "b", "c", "d", "e")


def test_cascade_candidates_nones_for_unspecified() -> None:
    resolver = ModelResolver(pipeline_model="d")
    result = resolver.cascade_candidates()
    assert result == (None, None, None, "d", None)


def test_resolve_consumes_cascade_candidates() -> None:
    """Patch cascade_candidates; assert resolve() iterates the patched output."""
    resolver = make_resolver()
    fixed = (None, "sonnet", None, None, None)
    with patch.object(type(resolver), "cascade_candidates", return_value=fixed):
        model_id, _ = resolver.resolve()
    assert "sonnet" in model_id.lower()


# ---------------------------------------------------------------------------
# T5 — PipelineClassification property unit tests
# ---------------------------------------------------------------------------


def _make_step_cls(
    action_type: str,
    classification: StepClass,
    index: int = 0,
) -> StepClassification:
    return StepClassification(
        step_name=f"step-{index}",
        step_index=index,
        action_type=action_type,
        resolved_alias="sonnet",
        resolved_model_id="claude-sonnet-4-6",
        profile="sdk" if classification == StepClass.SDK_REQUIRED else None,
        classification=classification,
        rationale="test",
    )


def test_needs_persistent_session_true_for_sdk_dispatch() -> None:
    pc = PipelineClassification(
        pipeline_name="p",
        steps=(_make_step_cls("dispatch", StepClass.SDK_REQUIRED),),
    )
    assert pc.needs_persistent_session is True


def test_needs_persistent_session_false_for_sdk_review_only() -> None:
    pc = PipelineClassification(
        pipeline_name="p",
        steps=(_make_step_cls("review", StepClass.SDK_REQUIRED),),
    )
    assert pc.needs_persistent_session is False


def test_needs_one_shot_claude_true_for_sdk_review() -> None:
    pc = PipelineClassification(
        pipeline_name="p",
        steps=(_make_step_cls("review", StepClass.SDK_REQUIRED),),
    )
    assert pc.needs_one_shot_claude is True


def test_needs_one_shot_claude_false_for_sdk_dispatch_only() -> None:
    """F002 regression guard: dispatch SDK does not contribute to one-shot."""
    pc = PipelineClassification(
        pipeline_name="p",
        steps=(_make_step_cls("dispatch", StepClass.SDK_REQUIRED),),
    )
    assert pc.needs_one_shot_claude is False


def test_shape_persistent() -> None:
    pc = PipelineClassification(
        pipeline_name="p",
        steps=(
            _make_step_cls("dispatch", StepClass.SDK_REQUIRED, 0),
            _make_step_cls("review", StepClass.SDK_REQUIRED, 1),
        ),
    )
    assert pc.shape == PipelineShape.CLAUDE_REQUIRED_PERSISTENT


def test_shape_one_shot() -> None:
    pc = PipelineClassification(
        pipeline_name="p",
        steps=(_make_step_cls("review", StepClass.SDK_REQUIRED),),
    )
    assert pc.shape == PipelineShape.CLAUDE_REQUIRED_ONE_SHOT


def test_shape_free() -> None:
    pc = PipelineClassification(
        pipeline_name="p",
        steps=(_make_step_cls("dispatch", StepClass.NON_SDK),),
    )
    assert pc.shape == PipelineShape.CLAUDE_FREE


# ---------------------------------------------------------------------------
# T7 — classify_pipeline non-pool path
# ---------------------------------------------------------------------------


def test_classifies_all_claude_pipeline_as_persistent() -> None:
    steps = [
        make_step("dispatch", "step-a"),
        make_step("dispatch", "step-b"),
        make_step("dispatch", "step-c"),
    ]
    pipeline = make_pipeline(steps)
    resolver = make_resolver(config_default="sonnet")
    result = classify_pipeline(pipeline, resolver)

    assert all(s.classification == StepClass.SDK_REQUIRED for s in result.steps)
    assert result.needs_persistent_session is True
    assert result.shape == PipelineShape.CLAUDE_REQUIRED_PERSISTENT


def test_classifies_all_minimax_pipeline_as_claude_free() -> None:
    steps = [
        make_step("dispatch", "step-a", {"model": "minimax"}),
        make_step("dispatch", "step-b", {"model": "minimax"}),
        make_step("dispatch", "step-c", {"model": "minimax"}),
    ]
    pipeline = make_pipeline(steps)
    resolver = make_resolver()
    result = classify_pipeline(pipeline, resolver)

    assert all(s.classification == StepClass.NON_SDK for s in result.steps)
    assert result.needs_persistent_session is False
    assert result.needs_one_shot_claude is False
    assert result.shape == PipelineShape.CLAUDE_FREE


def test_classifies_review_only_sdk_as_one_shot() -> None:
    steps = [make_step("review", "review-step", {"template": "slice", "model": "sonnet"})]
    pipeline = make_pipeline(steps)
    resolver = make_resolver()
    result = classify_pipeline(pipeline, resolver)

    assert result.steps[0].classification == StepClass.SDK_REQUIRED
    assert result.needs_persistent_session is False
    assert result.needs_one_shot_claude is True
    assert result.shape == PipelineShape.CLAUDE_REQUIRED_ONE_SHOT


def test_classifies_mixed_pipeline_per_step() -> None:
    steps = [
        make_step("dispatch", "claude-dispatch", {"model": "sonnet"}),
        make_step("dispatch", "minimax-dispatch", {"model": "minimax"}),
        make_step("review", "sonnet-review", {"template": "slice", "model": "sonnet"}),
    ]
    pipeline = make_pipeline(steps)
    resolver = make_resolver()
    result = classify_pipeline(pipeline, resolver)

    assert result.steps[0].classification == StepClass.SDK_REQUIRED
    assert result.steps[1].classification == StepClass.NON_SDK
    assert result.steps[2].classification == StepClass.SDK_REQUIRED
    assert result.needs_persistent_session is True
    assert result.needs_one_shot_claude is True
    assert result.shape == PipelineShape.CLAUDE_REQUIRED_PERSISTENT


def test_cli_override_honored() -> None:
    steps = [
        make_step("dispatch", "step-a"),
        make_step("dispatch", "step-b"),
    ]
    pipeline = make_pipeline(steps, model="sonnet")
    resolver = make_resolver(cli_override="minimax")
    result = classify_pipeline(pipeline, resolver)

    assert all(s.classification == StepClass.NON_SDK for s in result.steps)
    assert result.shape == PipelineShape.CLAUDE_FREE


def test_non_model_steps_skipped() -> None:
    steps = [
        make_step("dispatch", "dispatch-step"),
        make_step("cf-op", "cf-step"),
        make_step("checkpoint", "check-step"),
    ]
    pipeline = make_pipeline(steps)
    resolver = make_resolver(config_default="sonnet")
    result = classify_pipeline(pipeline, resolver)

    assert len(result.steps) == 1
    assert result.steps[0].step_name == "dispatch-step"


def test_misconfigured_step_raises() -> None:
    steps = [make_step("dispatch", "bad-step")]
    pipeline = make_pipeline(steps)
    resolver = make_resolver()  # no model at any level
    with pytest.raises(ClassificationError, match="bad-step"):
        classify_pipeline(pipeline, resolver)


def test_step_index_matches_definition_order() -> None:
    """SC1: step_index carries original pipeline position; skipped steps leave gaps."""
    steps = [
        make_step("dispatch", "first", {"model": "sonnet"}),
        make_step("cf-op", "middle"),
        make_step("dispatch", "third", {"model": "sonnet"}),
    ]
    pipeline = make_pipeline(steps)
    resolver = make_resolver()
    result = classify_pipeline(pipeline, resolver)

    assert len(result.steps) == 2
    assert result.steps[0].step_index == 0
    assert result.steps[1].step_index == 2


def test_one_shot_excludes_non_sdk_review() -> None:
    """SC4 third sub-case: non-SDK review does not contribute to one-shot."""
    steps = [
        make_step("dispatch", "claude-dispatch", {"model": "sonnet"}),
        make_step("review", "minimax-review", {"template": "slice", "model": "minimax"}),
    ]
    pipeline = make_pipeline(steps)
    resolver = make_resolver()
    result = classify_pipeline(pipeline, resolver)

    assert result.needs_one_shot_claude is False
    assert result.needs_persistent_session is True


# ---------------------------------------------------------------------------
# T9 — pool path tests
# ---------------------------------------------------------------------------

_SDK_POOL = ModelPool(
    name="sdk-pool",
    description="all SDK",
    models=["sonnet", "opus"],
    strategy="round-robin",
)

_NON_SDK_POOL = ModelPool(
    name="non-sdk-pool",
    description="all non-SDK",
    models=["minimax", "glm52"],
    strategy="round-robin",
)

_MIXED_POOL = ModelPool(
    name="mixed-pool",
    description="mixed SDK/non-SDK",
    models=["sonnet", "minimax"],
    strategy="round-robin",
)


def test_pool_all_sdk_collapses_to_sdk_required() -> None:
    spy = SpyPoolBackend({"sdk-pool": _SDK_POOL})
    steps = [make_step("dispatch", "pool-step", {"model": "pool:sdk-pool"})]
    pipeline = make_pipeline(steps)
    resolver = make_resolver(pool_backend=spy)
    result = classify_pipeline(pipeline, resolver, pool_backend=spy)

    assert result.steps[0].classification == StepClass.SDK_REQUIRED
    assert spy.select_call_count == 0


def test_pool_all_non_sdk_collapses_to_non_sdk() -> None:
    spy = SpyPoolBackend({"non-sdk-pool": _NON_SDK_POOL})
    steps = [make_step("dispatch", "pool-step", {"model": "pool:non-sdk-pool"})]
    pipeline = make_pipeline(steps)
    resolver = make_resolver(pool_backend=spy)
    result = classify_pipeline(pipeline, resolver, pool_backend=spy)

    assert result.steps[0].classification == StepClass.NON_SDK
    assert spy.select_call_count == 0


def test_pool_mixed_classifies_as_pool_uncertain() -> None:
    spy = SpyPoolBackend({"mixed-pool": _MIXED_POOL})
    steps = [make_step("dispatch", "pool-step", {"model": "pool:mixed-pool"})]
    pipeline = make_pipeline(steps)
    resolver = make_resolver(pool_backend=spy)
    result = classify_pipeline(pipeline, resolver, pool_backend=spy)

    assert result.steps[0].classification == StepClass.POOL_UNCERTAIN
    assert result.steps[0].pool_name == "mixed-pool"
    assert spy.select_call_count == 0


def test_pool_uncertain_strict_treats_as_persistent() -> None:
    """Under STRICT policy, POOL_UNCERTAIN conservatively forces session construction."""
    spy = SpyPoolBackend({"mixed-pool": _MIXED_POOL})
    steps = [make_step("dispatch", "pool-step", {"model": "pool:mixed-pool"})]
    pipeline = make_pipeline(steps)
    resolver = make_resolver(pool_backend=spy)
    result = classify_pipeline(
        pipeline, resolver, pool_backend=spy, policy=PoolClassificationPolicy.STRICT
    )

    assert result.needs_persistent_session is True


def test_pool_uncertain_lazy_does_not_need_persistent() -> None:
    """Under LAZY policy (default), POOL_UNCERTAIN does not force session construction."""
    spy = SpyPoolBackend({"mixed-pool": _MIXED_POOL})
    steps = [make_step("dispatch", "pool-step", {"model": "pool:mixed-pool"})]
    pipeline = make_pipeline(steps)
    resolver = make_resolver(pool_backend=spy)
    result = classify_pipeline(pipeline, resolver, pool_backend=spy)

    assert result.needs_persistent_session is False


def test_pool_without_backend_raises() -> None:
    steps = [make_step("dispatch", "pool-step", {"model": "pool:some-pool"})]
    pipeline = make_pipeline(steps)
    resolver = make_resolver()
    with pytest.raises(ClassificationError, match="pool backend"):
        classify_pipeline(pipeline, resolver, pool_backend=None)


# ---------------------------------------------------------------------------
# T10 — side-effect-freeness regression
# ---------------------------------------------------------------------------


def test_classification_is_idempotent_and_side_effect_free() -> None:
    """Classifying twice with the same instances must yield equal results
    and zero pool select() calls."""
    sdk_and_pool = ModelPool(
        name="sdk-pool",
        description="all SDK",
        models=["sonnet"],
        strategy="round-robin",
    )
    spy = SpyPoolBackend({"sdk-pool": sdk_and_pool})
    steps = [
        make_step("dispatch", "direct-claude", {"model": "sonnet"}),
        make_step("dispatch", "pooled", {"model": "pool:sdk-pool"}),
        make_step("review", "review-sonnet", {"template": "slice", "model": "sonnet"}),
    ]
    pipeline = make_pipeline(steps)
    resolver = make_resolver(pool_backend=spy)

    result_a = classify_pipeline(pipeline, resolver, pool_backend=spy)
    result_b = classify_pipeline(pipeline, resolver, pool_backend=spy)

    # Structural equality (frozen dataclass comparison)
    assert result_a == result_b
    # Zero pool selections across both runs
    assert spy.select_call_count == 0


# ---------------------------------------------------------------------------
# T2 — PoolClassificationPolicy enum
# ---------------------------------------------------------------------------


class TestPoolClassificationPolicy:
    def test_lazy_value(self) -> None:
        assert PoolClassificationPolicy.LAZY == "lazy"

    def test_strict_value(self) -> None:
        assert PoolClassificationPolicy.STRICT == "strict"


# ---------------------------------------------------------------------------
# T4 — needs_persistent_session under both policies
# ---------------------------------------------------------------------------


def _make_step_cls_uncertain(index: int = 0) -> StepClassification:
    return StepClassification(
        step_name=f"pool-step-{index}",
        step_index=index,
        action_type="dispatch",
        resolved_alias=None,
        resolved_model_id=None,
        profile=None,
        classification=StepClass.POOL_UNCERTAIN,
        rationale="pool mixes SDK and non-SDK",
        pool_name="mixed-pool",
    )


def test_lazy_pool_uncertain_not_needs_persistent() -> None:
    pc = PipelineClassification(
        pipeline_name="p",
        steps=(_make_step_cls_uncertain(),),
        policy=PoolClassificationPolicy.LAZY,
    )
    assert pc.needs_persistent_session is False


def test_strict_pool_uncertain_needs_persistent() -> None:
    pc = PipelineClassification(
        pipeline_name="p",
        steps=(_make_step_cls_uncertain(),),
        policy=PoolClassificationPolicy.STRICT,
    )
    assert pc.needs_persistent_session is True


def test_lazy_sdk_required_still_needs_persistent() -> None:
    pc = PipelineClassification(
        pipeline_name="p",
        steps=(_make_step_cls("dispatch", StepClass.SDK_REQUIRED),),
        policy=PoolClassificationPolicy.LAZY,
    )
    assert pc.needs_persistent_session is True


def test_lazy_mixed_sdk_and_pool_uncertain() -> None:
    pc = PipelineClassification(
        pipeline_name="p",
        steps=(
            _make_step_cls("dispatch", StepClass.SDK_REQUIRED, 0),
            _make_step_cls_uncertain(1),
        ),
        policy=PoolClassificationPolicy.LAZY,
    )
    assert pc.needs_persistent_session is True


# ---------------------------------------------------------------------------
# T6 — classify_pipeline policy parameter
# ---------------------------------------------------------------------------


def test_classify_default_policy_is_lazy() -> None:
    steps = [make_step("dispatch", "step-a", {"model": "sonnet"})]
    pipeline = make_pipeline(steps)
    resolver = make_resolver()
    result = classify_pipeline(pipeline, resolver)
    assert result.policy == PoolClassificationPolicy.LAZY


def test_classify_explicit_strict_policy() -> None:
    steps = [make_step("dispatch", "step-a", {"model": "sonnet"})]
    pipeline = make_pipeline(steps)
    resolver = make_resolver()
    result = classify_pipeline(pipeline, resolver, policy=PoolClassificationPolicy.STRICT)
    assert result.policy == PoolClassificationPolicy.STRICT


# ---------------------------------------------------------------------------
# Container classification (T8)
# ---------------------------------------------------------------------------


def _make_each_step(inner_model: str, name: str = "each-0") -> StepConfig:
    return make_step(
        "each",
        name,
        {
            "source": "items.list()",
            "as": "item",
            "steps": [{"dispatch": {"model": inner_model}}],
        },
    )


def _make_loop_step(inner_model: str, name: str = "loop-0") -> StepConfig:
    return make_step(
        "loop",
        name,
        {
            "max": 3,
            "steps": [{"dispatch": {"model": inner_model}}],
        },
    )


def _make_fan_out_step(models: object, name: str = "fan-0") -> StepConfig:
    return make_step("fan_out", name, {"models": models, "inner": {"dispatch": {}}})


def test_each_sdk_inner_classifies_as_persistent() -> None:
    pipeline = make_pipeline([_make_each_step("sonnet", "each-0")])
    resolver = make_resolver()
    result = classify_pipeline(pipeline, resolver)

    assert len(result.steps) == 1
    row = result.steps[0]
    assert row.classification == StepClass.SDK_REQUIRED
    assert row.step_name == "each-0"
    assert row.container_path == "dispatch-0"
    assert result.needs_persistent_session is True


def test_each_non_sdk_inner_classifies_as_claude_free() -> None:
    pipeline = make_pipeline([_make_each_step("minimax", "each-0")])
    resolver = make_resolver()
    result = classify_pipeline(pipeline, resolver)

    assert len(result.steps) == 1
    assert result.steps[0].classification == StepClass.NON_SDK
    assert result.shape == PipelineShape.CLAUDE_FREE


def test_loop_sdk_inner_classifies_as_persistent() -> None:
    pipeline = make_pipeline([_make_loop_step("sonnet", "loop-0")])
    resolver = make_resolver()
    result = classify_pipeline(pipeline, resolver)

    assert len(result.steps) == 1
    assert result.steps[0].classification == StepClass.SDK_REQUIRED
    assert result.needs_persistent_session is True


def test_fan_out_all_sdk_literal_list() -> None:
    pipeline = make_pipeline([_make_fan_out_step(["sonnet", "sonnet"])])
    resolver = make_resolver()
    result = classify_pipeline(pipeline, resolver)

    assert len(result.steps) == 1
    assert result.steps[0].classification == StepClass.SDK_REQUIRED
    assert result.steps[0].action_type == "dispatch"


def test_fan_out_all_non_sdk_literal_list() -> None:
    pipeline = make_pipeline([_make_fan_out_step(["minimax", "minimax"])])
    resolver = make_resolver()
    result = classify_pipeline(pipeline, resolver)

    assert len(result.steps) == 1
    assert result.steps[0].classification == StepClass.NON_SDK


def test_fan_out_mixed_literal_list_is_pool_uncertain() -> None:
    pipeline = make_pipeline([_make_fan_out_step(["sonnet", "minimax"])])
    resolver = make_resolver()
    result = classify_pipeline(pipeline, resolver)

    assert len(result.steps) == 1
    assert result.steps[0].classification == StepClass.POOL_UNCERTAIN


def test_fan_out_pool_ref_delegates_to_pool_classify() -> None:
    spy = SpyPoolBackend({"review": _MIXED_POOL})
    pipeline = make_pipeline([_make_fan_out_step("pool:review")])
    resolver = make_resolver(pool_backend=spy)
    result = classify_pipeline(pipeline, resolver, pool_backend=spy)

    assert len(result.steps) == 1
    assert result.steps[0].classification == StepClass.POOL_UNCERTAIN
    assert result.steps[0].pool_name == "review"
    assert spy.select_call_count == 0


def test_container_with_unregistered_inner_step_type_returns_no_rows() -> None:
    """Unregistered inner step type is skipped gracefully (mirrors top-level behaviour)."""
    from squadron.pipeline.models import StepConfig as SC

    sentinel = SC(step_type="unknown_type", name="unknown-0", config={})

    with patch.object(EachStepType, "inner_steps", return_value=[sentinel]):
        pipeline = make_pipeline([_make_each_step("sonnet")])
        resolver = make_resolver()
        result = classify_pipeline(pipeline, resolver)

    assert len(result.steps) == 0


def test_top_level_steps_still_classified_alongside_containers() -> None:
    steps = [
        _make_each_step("sonnet", "each-0"),
        make_step("dispatch", "summary-0", {"model": "minimax"}),
    ]
    pipeline = make_pipeline(steps)
    resolver = make_resolver()
    result = classify_pipeline(pipeline, resolver)

    assert len(result.steps) == 2
    container_row = next(r for r in result.steps if r.step_name == "each-0")
    top_row = next(r for r in result.steps if r.step_name == "summary-0")
    assert container_row.classification == StepClass.SDK_REQUIRED
    assert top_row.classification == StepClass.NON_SDK


# ---------------------------------------------------------------------------
# Slice 303 F002 — template.model fallback must be visible to classification
# ---------------------------------------------------------------------------


def _make_template(model: str | None) -> object:
    from squadron.review.templates import ReviewTemplate

    return ReviewTemplate(
        name="judge.slice-vs-arch",
        description="Test judge template",
        system_prompt="Review.",
        allowed_tools=["Read"],
        permission_mode="bypassPermissions",
        setting_sources=None,
        required_inputs=[],
        optional_inputs=[],
        model=model,
        prompt_template="Review all.",
    )


def test_review_step_with_no_cascade_model_falls_back_to_template_model() -> None:
    """A review step with no CLI/action/step/pipeline/config model must not
    raise ClassificationError when the template declares its own default
    model — mirrors the runtime fallback in ReviewAction._review."""
    steps = [make_step("review", "review-0", {"template": "judge.slice-vs-arch"})]
    pipeline = make_pipeline(steps)
    resolver = make_resolver()

    with patch(
        "squadron.review.templates.get_template",
        return_value=_make_template(model="minimax"),
    ):
        result = classify_pipeline(pipeline, resolver)

    assert len(result.steps) == 1
    assert result.steps[0].classification == StepClass.NON_SDK


def test_review_step_with_no_cascade_and_no_template_model_still_raises() -> None:
    """When the template itself has no default model either, classification
    must still raise — the fallback only extends the cascade, it doesn't
    make an unconfigured pipeline classifiable."""
    steps = [make_step("review", "review-0", {"template": "judge.slice-vs-arch"})]
    pipeline = make_pipeline(steps)
    resolver = make_resolver()

    with (
        patch(
            "squadron.review.templates.get_template",
            return_value=_make_template(model=None),
        ),
        pytest.raises(ClassificationError, match="no model at any cascade level"),
    ):
        classify_pipeline(pipeline, resolver)


def test_loop_container_review_inner_falls_back_to_template_model() -> None:
    """The judge-gated loop shape (loop > review, no step-level model):
    the container-inner classification path must also see template.model."""
    loop_step = make_step(
        "loop",
        "loop-0",
        {
            "max": 3,
            "steps": [{"review": {"template": "judge.slice-vs-arch"}}],
        },
    )
    pipeline = make_pipeline([loop_step])
    resolver = make_resolver()

    with patch(
        "squadron.review.templates.get_template",
        return_value=_make_template(model="minimax"),
    ):
        result = classify_pipeline(pipeline, resolver)

    assert len(result.steps) == 1
    assert result.steps[0].classification == StepClass.NON_SDK
