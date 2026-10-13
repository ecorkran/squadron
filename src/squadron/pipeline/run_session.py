"""Classify a definition and own its SDK session for one run.

Shared by ``sq run`` and ``sq review --max`` so both decide, open and tear down
the persistent Claude session the same way (slice 941).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from squadron.pipeline.classification import (
    PipelineClassification,
    PoolClassificationPolicy,
    classify_pipeline,
    has_profile_param,
)
from squadron.pipeline.intelligence.pools.backend import DefaultPoolBackend
from squadron.pipeline.models import PipelineDefinition
from squadron.pipeline.resolver import ModelResolver
from squadron.pipeline.sdk_session import SDKExecutionSession, open_pipeline_session


def classify_for_run(
    definition: PipelineDefinition,
    *,
    model_override: str | None,
    params: dict[str, object],
    strict: bool,
) -> PipelineClassification:
    """Classify *definition* the one way every run path does.

    Owns the policy (YAML ``auth_policy`` < ``--strict``), the classification
    pool backend and resolver, and the ``classify_pipeline`` call, so a run,
    ``--explain`` and ``--dry-run`` cannot disagree. Raises ``ClassificationError``;
    each caller words its own message.
    """
    policy = PoolClassificationPolicy.LAZY
    if definition.auth_policy == PoolClassificationPolicy.STRICT or strict:
        policy = PoolClassificationPolicy.STRICT

    pool_backend = DefaultPoolBackend()
    resolver = ModelResolver(
        cli_override=model_override,
        pipeline_model=definition.model,
        pool_backend=pool_backend,
        profile_source=has_profile_param(params),
    )
    return classify_pipeline(definition, resolver, pool_backend, policy=policy, params=params)


@asynccontextmanager
async def pipeline_session(
    classification: PipelineClassification,
) -> AsyncIterator[SDKExecutionSession | None]:
    """Yield a connected SDK session when *classification* needs one, else ``None``.

    The session is disconnected on exit, whether the body succeeds, fails,
    pauses or is interrupted. A failed connect propagates before the body runs.
    """
    session = await open_pipeline_session() if classification.needs_persistent_session else None
    try:
        yield session
    finally:
        if session is not None:
            await session.disconnect()
