"""Unit tests for squadron.pipeline.loader — pipeline loading and discovery."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from squadron.pipeline.loader import discover_pipelines, load_pipeline
from squadron.pipeline.models import PipelineDefinition


def _write_pipeline_yaml(directory: Path, name: str, *, steps: int = 1) -> Path:
    """Write a minimal valid pipeline YAML to *directory*."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.yaml"
    data = {
        "name": name,
        "description": f"test pipeline {name}",
        "steps": [{"design": {"phase": i}} for i in range(steps)],
    }
    path.write_text(yaml.dump(data))
    return path


class TestLoadPipelineBuiltIn:
    """Loading built-in pipelines by name."""

    def test_load_slice_lifecycle(self) -> None:
        defn = load_pipeline(
            "slice-lifecycle",
            project_dir=Path("/nonexistent"),
            user_dir=Path("/nonexistent"),
        )
        assert isinstance(defn, PipelineDefinition)
        assert defn.name == "slice-lifecycle"
        assert len(defn.steps) == 5

    def test_unknown_name_raises(self) -> None:
        with pytest.raises(FileNotFoundError, match="no-such-pipeline"):
            load_pipeline(
                "no-such-pipeline",
                project_dir=Path("/nonexistent"),
                user_dir=Path("/nonexistent"),
            )


class TestLoadPipelineFromPath:
    """Loading a pipeline from an explicit file path."""

    def test_load_from_path(self, tmp_path: Path) -> None:
        yaml_path = _write_pipeline_yaml(tmp_path, "custom")
        defn = load_pipeline(str(yaml_path))
        assert defn.name == "custom"
        assert len(defn.steps) == 1


class TestLoadPipelinePrecedence:
    """Project dir overrides user dir overrides built-in."""

    def test_project_overrides_builtin(self, tmp_path: Path) -> None:
        proj = tmp_path / "project"
        _write_pipeline_yaml(proj, "slice-lifecycle", steps=2)
        defn = load_pipeline(
            "slice-lifecycle",
            project_dir=proj,
            user_dir=Path("/nonexistent"),
        )
        # Project version has 2 steps, built-in has 5
        assert len(defn.steps) == 2

    def test_user_overrides_builtin(self, tmp_path: Path) -> None:
        user = tmp_path / "user"
        _write_pipeline_yaml(user, "slice-lifecycle", steps=3)
        defn = load_pipeline(
            "slice-lifecycle",
            project_dir=Path("/nonexistent"),
            user_dir=user,
        )
        assert len(defn.steps) == 3

    def test_project_overrides_user(self, tmp_path: Path) -> None:
        proj = tmp_path / "project"
        user = tmp_path / "user"
        _write_pipeline_yaml(proj, "test-pipe", steps=2)
        _write_pipeline_yaml(user, "test-pipe", steps=3)
        defn = load_pipeline(
            "test-pipe",
            project_dir=proj,
            user_dir=user,
        )
        assert len(defn.steps) == 2


class TestDiscoverPipelines:
    """discover_pipelines() finds and merges pipelines from all sources."""

    def test_discovers_builtin_pipelines(self) -> None:
        pipelines = discover_pipelines(
            project_dir=Path("/nonexistent"),
            user_dir=Path("/nonexistent"),
        )
        names = [p.name for p in pipelines]
        assert "slice-lifecycle" in names
        assert "review-only" in names
        assert "implementation-only" in names
        assert "design-batch" in names
        assert len(pipelines) >= 4

    def test_builtin_source_label(self) -> None:
        pipelines = discover_pipelines(
            project_dir=Path("/nonexistent"),
            user_dir=Path("/nonexistent"),
        )
        for p in pipelines:
            assert p.source == "built-in"

    def test_project_overrides_builtin(self, tmp_path: Path) -> None:
        proj = tmp_path / "project"
        _write_pipeline_yaml(proj, "slice-lifecycle", steps=2)
        pipelines = discover_pipelines(
            project_dir=proj,
            user_dir=Path("/nonexistent"),
        )
        by_name = {p.name: p for p in pipelines}
        assert by_name["slice-lifecycle"].source == "project"

    def test_nonexistent_dirs_no_error(self) -> None:
        pipelines = discover_pipelines(
            project_dir=Path("/nonexistent/proj"),
            user_dir=Path("/nonexistent/user"),
        )
        assert len(pipelines) >= 4

    def test_malformed_yaml_skipped(self, tmp_path: Path) -> None:
        proj = tmp_path / "project"
        proj.mkdir()
        bad = proj / "broken.yaml"
        bad.write_text(": : invalid yaml [[[")
        pipelines = discover_pipelines(
            project_dir=proj,
            user_dir=Path("/nonexistent"),
        )
        names = [p.name for p in pipelines]
        assert "broken" not in names
        assert "slice-lifecycle" in names
