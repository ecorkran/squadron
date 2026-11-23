"""The ``recipe_review`` record: built from the runner's stages, written through a sink (434 D8).

``RecipeRecordSink.write`` is synchronous: normal paths call it through
``asyncio.to_thread``; the cancellation path calls it directly, because an awaited call
would be cancelled with the task.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from squadron.metrology.content_sidecars import ContentSidecars, SidecarKind
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.models import RECORD_TYPE_RECIPE_REVIEW, MetrologyRecord
from squadron.metrology.project_id import ProjectId
from squadron.metrology.recall_run_models import StageConfig
from squadron.metrology.recipe_review_models import RecipeReview, RecipeStage
from squadron.metrology.store import MetrologyStore, resolve_store_dir
from squadron.recipes.recipe import Recipe, rules_sha256
from squadron.recipes.recipe_outcome import RecipeStageResult
from squadron.review.models import Verdict

_SCHEMA_VERSION = 1


class RecipeRecordSink(Protocol):
    """Where a recipe review's record and raw stage outputs go."""

    def write(self, record: RecipeReview, raw_outputs: dict[str, str]) -> None:
        """Persist *record*; *raw_outputs* maps each ``raw_ref`` to the document it hashes."""
        ...


class MetrologyStoreRecipeSink:
    """Writes raw outputs to the ``REVIEWS`` sidecar, then the record to the store.

    The store is opened on each write, so a store that cannot be created surfaces as a
    write failure (D8: logged, the review still returns) rather than at run start.
    """

    def __init__(self, open_store: Callable[[], MetrologyStore]) -> None:
        self._open_store = open_store

    def write(self, record: RecipeReview, raw_outputs: dict[str, str]) -> None:
        store = self._open_store()
        sidecar = ContentSidecars(store.store_dir, SidecarKind.REVIEWS)
        for raw_ref, document in raw_outputs.items():
            stored = sidecar.put(document.encode("utf-8"))
            if stored != raw_ref:
                raise MetrologyStoreError(f"sidecar key {stored} does not match raw_ref {raw_ref}")
        envelope = MetrologyRecord.model_validate(
            {
                "schema_version": _SCHEMA_VERSION,
                "record_type": RECORD_TYPE_RECIPE_REVIEW,
                "recipe_review": record,
            }
        )
        store.write_record(record.record_id, envelope)


def metrology_recipe_sink(cwd: str) -> MetrologyStoreRecipeSink:
    """The production sink: the metrology store configured for *cwd*."""
    return MetrologyStoreRecipeSink(lambda: MetrologyStore(resolve_store_dir(cwd)))


@dataclass(frozen=True)
class RecipeRecordContext:
    """Who and where: the project, the pipeline linkage (``None`` from ``sq review``), a clock.

    ``project_id`` is resolved when the record is built, so a project with no stable
    identity fails the record write (D8), never the review.
    """

    project_id: Callable[[], ProjectId]
    clock: Callable[[], datetime]
    run_id: str | None = None
    step_name: str | None = None
    iteration: int | None = None


@dataclass(frozen=True)
class RecipeRecordFacts:
    """What one recipe review produced, as the record states it."""

    record_id: str
    recipe: Recipe
    template_name: str
    template_hash: str
    planned: Sequence[StageConfig]
    stages: Sequence[RecipeStageResult]
    verdict: Verdict
    complete: bool
    review_file: str | None = None
    aborted: str | None = None


def recipe_hash(recipe: Recipe) -> str:
    """sha256 of the recipe's canonical content."""
    # Explicit keys: a field added to ``Recipe`` must not change every recipe's hash (437 D1).
    # The 437 keys appear only when set, so a recipe without them hashes as before; the
    # loader-set ``rules_path`` and ``rules_content`` never do.
    content = recipe.model_dump(mode="json", include={"name", "reviewers", "pool", "combs"})
    if recipe.reviewer_options:
        content["reviewer_options"] = {
            alias: {
                "tools": options.tools,
                "rules": options.rules,
                "rules_sha256": rules_sha256(options),
            }
            for alias, options in recipe.reviewer_options.items()
        }
    if recipe.keep_categories is not None:
        # Sorted: the filter is a set, so its order must not change the hash.
        content["keep_categories"] = sorted({str(category) for category in recipe.keep_categories})
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _raw_document(stage: RecipeStageResult) -> str | None:
    if stage.result is None:
        return None
    return json.dumps({"label": stage.label, "raw_output": stage.raw_output}, indent=2)


def _record_stage(stage: RecipeStageResult, raw_ref: str | None) -> RecipeStage:
    return RecipeStage(
        kind=stage.kind,
        reviewer=stage.reviewer,
        alias=stage.alias,
        config=stage.config,
        effort_sent=stage.effort_sent,
        findings=list(stage.findings),
        decisions=dict(stage.decisions),
        duplicate_decisions=stage.duplicate_decisions,
        unknown_ids=stage.unknown_ids,
        usage=stage.usage,
        outcome=stage.outcome,
        outcome_reason=stage.reason,
        raw_ref=raw_ref,
    )


def build_recipe_record(
    facts: RecipeRecordFacts, context: RecipeRecordContext
) -> tuple[RecipeReview, dict[str, str]]:
    """The record and the raw documents its stages' ``raw_ref`` keys name."""
    raw_outputs: dict[str, str] = {}
    stages: list[RecipeStage] = []
    for stage in facts.stages:
        document = _raw_document(stage)
        raw_ref = None
        if document is not None:
            raw_ref = hashlib.sha256(document.encode("utf-8")).hexdigest()
            raw_outputs[raw_ref] = document
        stages.append(_record_stage(stage, raw_ref))
    record = RecipeReview(
        record_id=facts.record_id,
        project_id=context.project_id(),
        recipe=facts.recipe.name,
        recipe_hash=recipe_hash(facts.recipe),
        template=facts.template_name,
        template_hash=facts.template_hash,
        run_id=context.run_id,
        step_name=context.step_name,
        iteration=context.iteration,
        review_file=facts.review_file,
        planned=list(facts.planned),
        stages=stages,
        verdict=facts.verdict,
        complete=facts.complete,
        aborted=facts.aborted,
        keep_categories=facts.recipe.keep_categories,
        created=context.clock(),
    )
    return record, raw_outputs
