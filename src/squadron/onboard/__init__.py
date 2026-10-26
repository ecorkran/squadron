"""``sq onboard``: brownfield adoption state and the next step (slice 440).

``build_onboard_report`` gathers the facts read-only (cf's detection, whether
cf has the project registered, the knowledge graph, the comprehension doc, the
agent surfaces) and ``decide_step`` names the next step. It calls no cf write.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from squadron.integrations.cf_adoption import AdoptionClient, AdoptionOutcome
from squadron.onboard.comprehension import newest_comprehension
from squadron.onboard.graph import GRAPH_DIR_NAME, GRAPH_FILE_NAME, GraphReport, probe_graph
from squadron.onboard.steps import NextStep, decide_step
from squadron.onboard.surfaces import SURFACES


@dataclass(frozen=True)
class SurfaceState:
    """Install state for one agent surface; ``None`` means it could not be determined."""

    analysis_skill_installed: bool | None
    understand_plugin_installed: bool | None


@dataclass(frozen=True)
class OnboardReport:
    """Everything ``sq onboard`` reports; paths other than ``root`` are relative to it."""

    root: Path
    outcome: AdoptionOutcome
    registered: bool
    graph: GraphReport
    comprehension: Path | None
    comprehension_older_than_graph: bool | None
    concept: str | None
    surfaces: dict[str, SurfaceState]
    notices: tuple[str, ...]
    next: NextStep

    def to_json(self) -> dict[str, object]:
        """The API Contracts shape (slice 440); the ``--json`` output."""
        graph_path = self.graph["path"]
        return {
            "root": str(self.root),
            "outcome": self.outcome.value,
            "registered": self.registered,
            "graph": {
                **self.graph,
                "path": None if graph_path is None else _relative(Path(graph_path), self.root),
            },
            "comprehension": (
                None if self.comprehension is None else _relative(self.comprehension, self.root)
            ),
            "comprehension_older_than_graph": self.comprehension_older_than_graph,
            "concept": self.concept,
            "surfaces": {
                key: {
                    "analysis_skill_installed": state.analysis_skill_installed,
                    "understand_plugin_installed": state.understand_plugin_installed,
                }
                for key, state in self.surfaces.items()
            },
            "notices": list(self.notices),
            "next": {
                "step": self.next.step.value,
                "reason": self.next.reason,
                "handoff": None if self.next.handoff is None else self.next.handoff.value,
            },
        }


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _doc_older_than_graph(root: Path, comprehension: Path | None) -> bool | None:
    """Doc mtime earlier than the graph file's; ``None`` when either file is absent."""
    graph_file = root / GRAPH_DIR_NAME / GRAPH_FILE_NAME
    if comprehension is None or not graph_file.is_file():
        return None
    return comprehension.stat().st_mtime < graph_file.stat().st_mtime


def build_onboard_report(root: Path, cf: AdoptionClient) -> OnboardReport:
    """Gather the facts under *root* and decide the next step. Read-only."""
    detection = cf.detect(root)
    registered = cf.is_registered(root)
    graph = probe_graph(root)
    comprehension = newest_comprehension(root)
    concept = detection.artifacts.concept
    return OnboardReport(
        root=root,
        outcome=detection.outcome,
        registered=registered,
        graph=graph,
        comprehension=comprehension,
        comprehension_older_than_graph=_doc_older_than_graph(root, comprehension),
        concept=concept,
        surfaces={
            spec.key: SurfaceState(
                analysis_skill_installed=spec.analysis_skill_installed(root),
                understand_plugin_installed=spec.understand_plugin_installed(root),
            )
            for spec in SURFACES.values()
        },
        notices=detection.notices,
        next=decide_step(detection.outcome, registered, graph, comprehension, concept),
    )
