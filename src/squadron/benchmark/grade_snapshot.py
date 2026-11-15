"""The production snapshot measurer for a graded tree (slice 425 D12).

Measures the tracked files of the sandbox tree as ``take_snapshot_at`` would an exported
commit, but writes no ``code_snapshot`` record: a sandbox commit is not in the project's
history, and a record keyed on it would appear in 400's project rollups.
"""

from __future__ import annotations

from pathlib import Path

from squadron.benchmark.grade_deps import SnapshotMeasurer
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.snapshot.contract import AdapterRegistry, ToolRunner
from squadron.metrology.snapshot.files import effective_exclusions, resolve_files
from squadron.metrology.snapshot.preflight import read_snapshot_config
from squadron.metrology.snapshot.take import measure_snapshot
from squadron.metrology.snapshot_models import CodeSnapshot


def make_snapshot_measurer(registry: AdapterRegistry, runner: ToolRunner) -> SnapshotMeasurer:
    """A measurer over *registry* and *runner*; the tree is both root and environment root."""

    def measure(tree: Path, case: BenchmarkCase, head_sha: str) -> CodeSnapshot:
        config = read_snapshot_config(tree)
        exclusions = effective_exclusions(config.project_exclusions, registry.values())
        files = resolve_files(tree, exclusions)
        return measure_snapshot(tree, tree, config, registry, runner, case.project_id, head_sha, files)

    return measure
