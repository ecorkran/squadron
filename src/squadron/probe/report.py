"""Shape of the capability probe report.

The source of truth is ``project-documents/user/reference/capability-probe-contract.md``
(``probe_version`` 1). Field names are frozen; a null value means the probe could not
determine the field.
"""

from __future__ import annotations

from typing import TypedDict


class SurfaceReport(TypedDict):
    analysis_skill_installed: bool | None
    entry: str
    concept: str
    understand_plugin_installed: bool | None
    graph_build: str


class GraphReport(TypedDict):
    present: bool
    path: str | None
    commit: str | None
    commits_behind: int | None


class BaselineReport(TypedDict):
    available: bool


class ProbeReport(TypedDict):
    probe_version: int
    sq_version: str
    surfaces: dict[str, SurfaceReport]
    graph: GraphReport
    baseline: BaselineReport
