"""Tests for build_onboard_report (slice 440 Data Flow, API Contracts)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import pytest

from squadron.integrations.cf_adoption import AdoptionClient
from squadron.onboard import build_onboard_report
from squadron.onboard.comprehension import ANALYSIS_DIR, COMPREHENSION_SUFFIX
from squadron.onboard.graph import GRAPH_DIR_NAME, GRAPH_FILE_NAME
from squadron.onboard.steps import OnboardStep
from tests.onboard.fakes import FakeAdoptionClient

DOC_NAME = f"940{COMPREHENSION_SUFFIX}"


def _write_doc(root: Path, mtime: float | None = None) -> Path:
    doc = root / ANALYSIS_DIR / DOC_NAME
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("doc")
    if mtime is not None:
        os.utime(doc, (mtime, mtime))
    return doc


def _write_graph(root: Path, mtime: float | None = None) -> Path:
    graph = root / GRAPH_DIR_NAME / GRAPH_FILE_NAME
    graph.parent.mkdir(parents=True, exist_ok=True)
    graph.write_text("{}")
    if mtime is not None:
        os.utime(graph, (mtime, mtime))
    return graph


def _client(fake: FakeAdoptionClient) -> AdoptionClient:
    return fake


def test_json_matches_the_api_contract(tmp_path: Path) -> None:
    _write_graph(tmp_path)
    _write_doc(tmp_path)
    fake = FakeAdoptionClient("detect-brownfield", registered=True)

    data = build_onboard_report(tmp_path, _client(fake)).to_json()

    assert list(data) == [
        "root",
        "outcome",
        "registered",
        "graph",
        "comprehension",
        "comprehension_older_than_graph",
        "concept",
        "surfaces",
        "notices",
        "next",
    ]
    assert data["root"] == str(tmp_path)
    assert data["outcome"] == "brownfield"
    assert data["registered"] is True
    graph = cast("dict[str, object]", data["graph"])
    assert graph["present"] is True
    assert graph["path"] == f"{GRAPH_DIR_NAME}/{GRAPH_FILE_NAME}"
    assert data["comprehension"] == f"{ANALYSIS_DIR}/{DOC_NAME}"
    assert data["concept"] is None
    surfaces = cast("dict[str, dict[str, object]]", data["surfaces"])
    assert set(surfaces) == {"claude-code", "codex"}
    assert set(surfaces["codex"]) == {"analysis_skill_installed", "understand_plugin_installed"}
    assert data["notices"] == ["fixture notice: brownfield"]
    assert data["next"] == {
        "step": "concept",
        "reason": "cf reports no concept",
        "handoff": None,
    }


@pytest.mark.parametrize(
    ("doc_mtime", "graph_mtime", "expected"),
    [(100.0, 200.0, True), (300.0, 200.0, False), (None, 200.0, None), (100.0, None, None)],
    ids=["doc-older", "doc-newer", "doc-absent", "graph-absent"],
)
def test_comprehension_older_than_graph(
    tmp_path: Path, doc_mtime: float | None, graph_mtime: float | None, expected: bool | None
) -> None:
    if doc_mtime is not None:
        _write_doc(tmp_path, doc_mtime)
    if graph_mtime is not None:
        _write_graph(tmp_path, graph_mtime)
    fake = FakeAdoptionClient("detect-brownfield", registered=True)

    report = build_onboard_report(tmp_path, _client(fake))

    assert report.comprehension_older_than_graph is expected


def test_report_only_reads_from_cf(tmp_path: Path) -> None:
    fake = FakeAdoptionClient("detect-brownfield", registered=False)
    build_onboard_report(tmp_path, _client(fake))
    assert fake.call_names == ["detect", "is_registered"]


def test_a_resumed_run_with_doc_and_concept_goes_to_adopt(tmp_path: Path) -> None:
    _write_doc(tmp_path)
    fake = FakeAdoptionClient("detect-adoption-incomplete", registered=True)

    report = build_onboard_report(tmp_path, _client(fake))

    assert report.next.step is OnboardStep.ADOPT
    assert report.to_json()["concept"] == "project-documents/user/concept.md"
