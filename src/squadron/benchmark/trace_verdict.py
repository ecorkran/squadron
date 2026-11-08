"""The fairness verdict for one traced hidden test (slice 422 D6, D7).

Pure: the facts the trace plugin recorded and the packaging boundary in, one
``FairnessVerdict`` out. Precedence when several apply: ``patches_project_code``, then
``reaches_past_boundary``, then ``boundary_undecidable``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from squadron.benchmark.fairness import AllowedBoundary, FairnessVerdict
from squadron.metrology.benchmark_models import TestRejection

REFERENCE_MODULE = "module"
CROSSING_CONSTRUCTOR = "constructor"
CROSSING_METHOD = "method"
PROJECT_OWNER_KINDS = frozenset({"project_module", "project_class", "project_instance"})
UNRESOLVED_OWNER_KIND = "unresolved"

#: Project patch targets that only isolate the environment (the checkout's .env must not
#: reach tests) and change none of the behavior under test. They are not
#: ``patches_project_code``. squadron's autouse conftest fixture patches this in every test.
ENVIRONMENT_ISOLATION_PATCH_TARGETS = frozenset({"squadron.cli.app._load_env_file"})


@dataclass(frozen=True)
class Reference:
    kind: str
    module: str
    qualname: str


@dataclass(frozen=True)
class Crossing:
    module: str
    qualname: str
    kind: str


@dataclass(frozen=True)
class PatchFact:
    api: str
    owner_kind: str
    owner_module: str
    target: str


@dataclass(frozen=True)
class TraceFacts:
    references: tuple[Reference, ...]
    crossings: tuple[Crossing, ...]
    patches: tuple[PatchFact, ...]
    has_co_qualname: bool

    @classmethod
    def from_plugin(cls, node: Mapping[str, Any], *, has_co_qualname: bool) -> TraceFacts:
        """Build from one node's record in the plugin's trace output."""
        return cls(
            references=tuple(Reference(*entry) for entry in node["references"]),
            crossings=tuple(Crossing(*entry) for entry in node["crossings"]),
            patches=tuple(PatchFact(*entry) for entry in node["patches"]),
            has_co_qualname=has_co_qualname,
        )


def _class_of_constructor(qualname: str) -> str:
    """``Widget.__init__`` is a crossing into the class ``Widget``."""
    return qualname.rsplit(".", 1)[0]


def _patching(facts: TraceFacts) -> str | None:
    targets = sorted(
        patch.target
        for patch in facts.patches
        if patch.owner_kind in PROJECT_OWNER_KINDS
        and patch.target not in ENVIRONMENT_ISOLATION_PATCH_TARGETS
    )
    return targets[0] if targets else None


def _past_boundary(facts: TraceFacts, allowed: AllowedBoundary) -> str | None:
    symbols: set[str] = set()
    for reference in facts.references:
        if reference.kind != REFERENCE_MODULE and not allowed.allows(
            reference.module, reference.qualname
        ):
            symbols.add(f"{reference.module}.{reference.qualname}")
    for crossing in facts.crossings:
        if crossing.kind == CROSSING_METHOD:
            continue
        qualname = (
            _class_of_constructor(crossing.qualname)
            if crossing.kind == CROSSING_CONSTRUCTOR
            else crossing.qualname
        )
        if not allowed.allows(crossing.module, qualname):
            symbols.add(f"{crossing.module}.{qualname}")
    return sorted(symbols)[0] if symbols else None


def _undecidable(facts: TraceFacts) -> str | None:
    if not facts.has_co_qualname:
        return "this interpreter has no co_qualname, so crossings cannot be named"
    modules = sorted(r.module for r in facts.references if r.kind == REFERENCE_MODULE)
    if modules:
        return f"the test reads project module {modules[0]} as an object"
    unresolved = sorted(p.target for p in facts.patches if p.owner_kind == UNRESOLVED_OWNER_KIND)
    if unresolved:
        return f"a patch target does not resolve: {unresolved[0]}"
    return None


def judge_trace(facts: TraceFacts, allowed: AllowedBoundary) -> FairnessVerdict:
    """``rejection`` is ``None`` when the test touches only the packaging boundary."""
    patched = _patching(facts)
    if patched is not None:
        return FairnessVerdict(TestRejection.PATCHES_PROJECT_CODE, patched)
    past = _past_boundary(facts, allowed)
    if past is not None:
        return FairnessVerdict(TestRejection.REACHES_PAST_BOUNDARY, past)
    unsure = _undecidable(facts)
    if unsure is not None:
        return FairnessVerdict(TestRejection.BOUNDARY_UNDECIDABLE, unsure)
    return FairnessVerdict(None)
