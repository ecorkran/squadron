"""The ``sq onboard`` step decision (slice 440 D1, D2).

``decide_step`` is the only place a step is chosen; the command files carry the
instructions for each step and nothing that decides one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from squadron.integrations.cf_adoption import AdoptionOutcome
from squadron.onboard.graph import GraphReport


class OnboardStep(StrEnum):
    """What the agent does next; each value is a ``### Step:`` heading in the command files."""

    HANDOFF = "handoff"
    ASK_ADOPT = "ask-adopt"
    BUILD_GRAPH = "build-graph"
    COMPREHENSION = "comprehension"
    CONCEPT = "concept"
    ADOPT = "adopt"


class Handoff(StrEnum):
    """Where a ``handoff`` step sends the user."""

    CF_ONBOARD = "cf-onboard"
    CF_NEXT = "cf-next"


@dataclass(frozen=True)
class NextStep:
    """The decided step; ``handoff`` is set only for ``OnboardStep.HANDOFF``."""

    step: OnboardStep
    reason: str
    handoff: Handoff | None = None


REASON_NEW_PROJECT = "cf treats this project as new"
REASON_ALREADY_PLANNED = "the project already has a plan"
REASON_NOT_REGISTERED = "existing code is not registered with cf"
REASON_GRAPH_GATES = "no comprehension doc yet and the knowledge graph is absent or not current"
REASON_NEEDS_COMPREHENSION = "no comprehension doc yet"
REASON_NEEDS_CONCEPT = "cf reports no concept"
REASON_READY_TO_ADOPT = "comprehension doc and concept exist"

_NEW_PROJECT_OUTCOMES = frozenset({AdoptionOutcome.GREENFIELD, AdoptionOutcome.OPTED_OUT})
_UNREGISTERED_OUTCOMES = frozenset({AdoptionOutcome.BROWNFIELD, AdoptionOutcome.ADOPTION_INCOMPLETE})


def _graph_gates(graph: GraphReport) -> bool:
    """Absent, behind HEAD, or of unknown staleness (D2): the PM is asked."""
    if not graph["present"]:
        return True
    behind = graph["commits_behind"]
    return behind is None or behind > 0


def decide_step(
    outcome: AdoptionOutcome,
    registered: bool,
    graph: GraphReport,
    comprehension: Path | None,
    concept: str | None,
) -> NextStep:
    """D1: the first matching row wins."""
    if outcome in _NEW_PROJECT_OUTCOMES:
        return NextStep(OnboardStep.HANDOFF, REASON_NEW_PROJECT, Handoff.CF_ONBOARD)
    if outcome is AdoptionOutcome.ALREADY_PLANNED:
        return NextStep(OnboardStep.HANDOFF, REASON_ALREADY_PLANNED, Handoff.CF_NEXT)
    if outcome in _UNREGISTERED_OUTCOMES and not registered:
        return NextStep(OnboardStep.ASK_ADOPT, REASON_NOT_REGISTERED)
    if comprehension is None and _graph_gates(graph):
        return NextStep(OnboardStep.BUILD_GRAPH, REASON_GRAPH_GATES)
    if comprehension is None:
        return NextStep(OnboardStep.COMPREHENSION, REASON_NEEDS_COMPREHENSION)
    if concept is None:
        return NextStep(OnboardStep.CONCEPT, REASON_NEEDS_CONCEPT)
    return NextStep(OnboardStep.ADOPT, REASON_READY_TO_ADOPT)
