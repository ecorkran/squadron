"""Capability probe: reports what squadron's brownfield path can use here.

Built to ``project-documents/user/reference/capability-probe-contract.md``.
"""

from pathlib import Path

from squadron import __version__
from squadron.probe.graph import probe_graph, project_root
from squadron.probe.report import BaselineReport, ProbeReport, SurfaceReport
from squadron.probe.surfaces import SURFACES

PROBE_VERSION = 1


def build_probe(cwd: Path) -> ProbeReport:
    """Probe the project containing ``cwd``; fields the probe cannot determine are None."""
    root = project_root(cwd)
    surfaces = {
        spec.key: SurfaceReport(
            analysis_skill_installed=spec.analysis_skill_installed(root),
            entry=spec.entry,
            concept=spec.concept,
            understand_plugin_installed=spec.understand_plugin_installed(root),
            graph_build=spec.graph_build,
        )
        for spec in SURFACES.values()
    }
    return ProbeReport(
        probe_version=PROBE_VERSION,
        sq_version=__version__,
        surfaces=surfaces,
        graph=probe_graph(root),
        # False until initiative 400 ships its adoption baseline.
        baseline=BaselineReport(available=False),
    )
