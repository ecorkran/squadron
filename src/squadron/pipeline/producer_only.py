"""Producer-only runs: the ``ProducerStep`` capability and the definition transform (slice 424).

``sq run --producer-only`` runs a pipeline's single producer step with its embedded
review stripped, then stops. Each step type owns its own review key through
``producer_only_config``, so neither the executor nor the CLI names one.
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Protocol, runtime_checkable

from squadron.pipeline.models import PipelineDefinition, StepConfig
from squadron.pipeline.steps import bootstrap_step_types, get_step_type

_logger = logging.getLogger(__name__)


@runtime_checkable
class ProducerStep(Protocol):
    """Capability of a step type that produces work and may embed a review of it.

    The method returns a new config with whatever review the step embeds removed;
    the step type's expansion then yields the same prompt, dispatch and commit
    without a review verdict.
    """

    def producer_only_config(self, config: StepConfig) -> StepConfig:
        """Return *config* without the step's embedded review (input not mutated)."""
        ...


def config_without_keys(config: StepConfig, keys: Iterable[str]) -> StepConfig:
    """A deep copy of *config* with *keys* removed from its ``config`` mapping.

    The step type and name are kept; the input is not mutated.
    """
    removed = frozenset(keys)
    kept = {key: value for key, value in config.config.items() if key not in removed}
    return StepConfig(step_type=config.step_type, name=config.name, config=copy.deepcopy(kept))


class ProducerOnlyError(ValueError):
    """The pipeline has no single producer step, so ``--producer-only`` cannot apply."""


@dataclass(frozen=True)
class ProducerOnlySelection:
    """A pipeline narrowed to its producer step.

    ``skipped`` holds the names of every other top-level step, in definition order.
    """

    definition: PipelineDefinition
    step_name: str
    skipped: tuple[str, ...]


def _producer_candidates(definition: PipelineDefinition) -> list[StepConfig]:
    """Top-level steps whose registered step type is a ``ProducerStep``."""
    bootstrap_step_types()
    return [
        step for step in definition.steps if isinstance(get_step_type(step.step_type), ProducerStep)
    ]


def select_producer_step(definition: PipelineDefinition) -> StepConfig:
    """The pipeline's single top-level producer step, unchanged.

    Steps nested inside ``loop`` or ``each`` are not candidates.

    Raises:
        ProducerOnlyError: when no step, or more than one, is a producer step.
    """
    candidates = _producer_candidates(definition)
    if len(candidates) == 1:
        return candidates[0]
    names = ", ".join(step.name for step in candidates)
    if not candidates:
        steps = ", ".join(step.name for step in definition.steps)
        message = (
            f"pipeline '{definition.name}' has no producer step; "
            f"no step type among its steps ({steps}) is a producer"
        )
    else:
        message = f"pipeline '{definition.name}' has more than one producer step: {names}"
    _logger.warning("producer-only refused: %s", message)
    raise ProducerOnlyError(message)


def producer_only_definition(definition: PipelineDefinition) -> ProducerOnlySelection:
    """A copy of *definition* holding only its producer step, with its review stripped.

    The input is not mutated; params, model and ``max_cost_usd`` carry over.
    """
    producer = select_producer_step(definition)
    producer_type = get_step_type(producer.step_type)
    assert isinstance(producer_type, ProducerStep)  # select_producer_step guarantees it
    stripped = producer_type.producer_only_config(producer)
    skipped = tuple(step.name for step in definition.steps if step is not producer)
    narrowed = replace(definition, steps=[stripped])
    return ProducerOnlySelection(definition=narrowed, step_name=producer.name, skipped=skipped)
