"""Tests for the onboard step decision (slice 440 D1, D2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.integrations.cf_adoption import AdoptionOutcome
from squadron.onboard.graph import GraphReport
from squadron.onboard.steps import Handoff, OnboardStep, decide_step

ABSENT = GraphReport(present=False, path=None, commit=None, commits_behind=None)
CURRENT = GraphReport(present=True, path="g.json", commit="abc", commits_behind=0)
BEHIND = GraphReport(present=True, path="g.json", commit="abc", commits_behind=3)
UNKNOWN = GraphReport(present=True, path="g.json", commit=None, commits_behind=None)
DOC = Path("project-documents/user/analysis/940-analysis.codebase-comprehension.md")
CONCEPT = "project-documents/user/concept.md"
Outcome = AdoptionOutcome


@pytest.mark.parametrize(
    ("outcome", "registered", "graph", "doc", "concept", "step", "handoff"),
    [
        (Outcome.GREENFIELD, False, ABSENT, None, None, OnboardStep.HANDOFF, Handoff.CF_ONBOARD),
        (Outcome.OPTED_OUT, True, CURRENT, DOC, CONCEPT, OnboardStep.HANDOFF, Handoff.CF_ONBOARD),
        (Outcome.ALREADY_PLANNED, True, CURRENT, DOC, CONCEPT, OnboardStep.HANDOFF, Handoff.CF_NEXT),
        (Outcome.BROWNFIELD, False, CURRENT, DOC, CONCEPT, OnboardStep.ASK_ADOPT, None),
        (Outcome.ADOPTION_INCOMPLETE, False, ABSENT, None, None, OnboardStep.ASK_ADOPT, None),
        (Outcome.BROWNFIELD, True, ABSENT, None, None, OnboardStep.BUILD_GRAPH, None),
        (Outcome.BROWNFIELD, True, BEHIND, None, None, OnboardStep.BUILD_GRAPH, None),
        (Outcome.BROWNFIELD, True, UNKNOWN, None, None, OnboardStep.BUILD_GRAPH, None),
        (Outcome.BROWNFIELD, True, CURRENT, None, None, OnboardStep.COMPREHENSION, None),
        (Outcome.BROWNFIELD, True, BEHIND, DOC, None, OnboardStep.CONCEPT, None),
        (Outcome.BROWNFIELD, True, ABSENT, DOC, None, OnboardStep.CONCEPT, None),
        (Outcome.BROWNFIELD, True, CURRENT, DOC, CONCEPT, OnboardStep.ADOPT, None),
        (Outcome.ADOPTION_INCOMPLETE, True, BEHIND, DOC, CONCEPT, OnboardStep.ADOPT, None),
    ],
    ids=[
        "greenfield-handoff",
        "opted-out-handoff",
        "already-planned-handoff",
        "brownfield-unregistered",
        "incomplete-unregistered",
        "graph-absent",
        "graph-behind",
        "graph-unknown",
        "graph-current-no-doc",
        "doc-with-stale-graph-ignores-graph",
        "doc-with-absent-graph-ignores-graph",
        "resumed-run-adopts",
        "incomplete-with-doc-and-concept-adopts",
    ],
)
def test_decide_step_table(
    outcome: AdoptionOutcome,
    registered: bool,
    graph: GraphReport,
    doc: Path | None,
    concept: str | None,
    step: OnboardStep,
    handoff: Handoff | None,
) -> None:
    decided = decide_step(outcome, registered, graph, doc, concept)
    assert decided.step is step
    assert decided.handoff is handoff
    assert decided.reason


def test_handoff_is_set_only_for_handoff_steps() -> None:
    for outcome in AdoptionOutcome:
        decided = decide_step(outcome, True, CURRENT, DOC, CONCEPT)
        assert (decided.handoff is not None) == (decided.step is OnboardStep.HANDOFF)
