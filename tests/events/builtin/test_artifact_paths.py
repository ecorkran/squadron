"""dispatch_artifact_paths: the one slice-or-plan resolution shared by dispatch-artifact
and usage-stamp (slice 178 D3)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from squadron.events.builtin.artifact_paths import dispatch_artifact_paths
from squadron.integrations.context_forge import ContextForgeError
from squadron.pipeline.steps.phase import ArtifactKind
from squadron.review.persistence import ARCHITECTURE_DIR, TASKS_DIR


def _cf_client() -> MagicMock:
    cf_client = MagicMock()
    cf_client.list_slices.return_value = [
        SimpleNamespace(index=178, name="Artifact Usage", design_file="slices/178-slice.a.md")
    ]
    cf_client.list_tasks.return_value = [
        SimpleNamespace(index=178, files=["178-tasks.a.md"]),
    ]
    cf_client.get_project.return_value = SimpleNamespace(
        arch_file="architecture/140-arch.x.md", name="squadron"
    )
    return cf_client


def test_slice_design_returns_design_file() -> None:
    paths = dispatch_artifact_paths(ArtifactKind.DESIGN, "178", None, _cf_client(), ".")
    assert paths == ["slices/178-slice.a.md"]


def test_slice_tasks_returns_task_files_under_tasks_dir() -> None:
    paths = dispatch_artifact_paths(ArtifactKind.TASKS, 178, None, _cf_client(), ".")
    assert paths == [str(TASKS_DIR / "178-tasks.a.md")]


def test_plan_without_slice_returns_arch_doc(tmp_path: Path) -> None:
    arch_dir = tmp_path / ARCHITECTURE_DIR
    arch_dir.mkdir(parents=True)
    (arch_dir / "140-arch.pipeline.md").write_text("---\n---\n")
    paths = dispatch_artifact_paths(ArtifactKind.DESIGN, None, "140", MagicMock(), str(tmp_path))
    assert paths == [str(Path(ARCHITECTURE_DIR) / "140-arch.pipeline.md")]


def test_slice_wins_over_plan() -> None:
    paths = dispatch_artifact_paths(ArtifactKind.DESIGN, "178", "140", _cf_client(), ".")
    assert paths == ["slices/178-slice.a.md"]


def test_resolver_errors_propagate(tmp_path: Path) -> None:
    failing = MagicMock()
    failing.list_slices.side_effect = ContextForgeError("cf down")
    with pytest.raises(ContextForgeError):
        dispatch_artifact_paths(ArtifactKind.DESIGN, "178", None, failing, ".")
    with pytest.raises(FileNotFoundError):
        dispatch_artifact_paths(ArtifactKind.DESIGN, None, "140", MagicMock(), str(tmp_path))
    with pytest.raises(ValueError, match="not a numeric index"):
        dispatch_artifact_paths(ArtifactKind.DESIGN, "abc", None, _cf_client(), ".")
    with pytest.raises(ValueError, match="no 'slice' param"):
        dispatch_artifact_paths(ArtifactKind.DESIGN, None, None, _cf_client(), ".")
