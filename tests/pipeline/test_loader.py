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
            "slice",
            project_dir=Path("/nonexistent"),
            user_dir=Path("/nonexistent"),
        )
        assert isinstance(defn, PipelineDefinition)
        assert defn.name == "slice"
        assert len(defn.steps) == 10

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
        _write_pipeline_yaml(proj, "slice", steps=2)
        defn = load_pipeline(
            "slice",
            project_dir=proj,
            user_dir=Path("/nonexistent"),
        )
        # Project version has 2 steps, built-in has 5
        assert len(defn.steps) == 2

    def test_user_overrides_builtin(self, tmp_path: Path) -> None:
        user = tmp_path / "user"
        _write_pipeline_yaml(user, "slice", steps=3)
        defn = load_pipeline(
            "slice",
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
        assert "slice" in names
        assert "review" in names
        assert "implement" in names
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
        _write_pipeline_yaml(proj, "slice", steps=2)
        pipelines = discover_pipelines(
            project_dir=proj,
            user_dir=Path("/nonexistent"),
        )
        by_name = {p.name: p for p in pipelines}
        assert by_name["slice"].source == "project"

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
        assert "slice" in names


# ---------------------------------------------------------------------------
# T9: load_pipeline case-insensitive name lookup
# ---------------------------------------------------------------------------


class TestLoadPipelineCaseNormalisation:
    def test_mixed_case_name_finds_lowercase_file(self, tmp_path: Path) -> None:
        """load_pipeline("Test-Pipeline") finds test-pipeline.yaml."""
        proj = tmp_path / "project"
        _write_pipeline_yaml(proj, "test-pipeline")
        defn = load_pipeline(
            "Test-Pipeline",
            project_dir=proj,
            user_dir=Path("/nonexistent"),
        )
        assert defn.name == "test-pipeline"

    def test_uppercase_name_finds_lowercase_file(self, tmp_path: Path) -> None:
        """load_pipeline("TEST-PIPELINE") also finds test-pipeline.yaml."""
        proj = tmp_path / "project"
        _write_pipeline_yaml(proj, "test-pipeline")
        defn = load_pipeline(
            "TEST-PIPELINE",
            project_dir=proj,
            user_dir=Path("/nonexistent"),
        )
        assert defn.name == "test-pipeline"

    def test_direct_file_path_not_normalised(self, tmp_path: Path) -> None:
        """load_pipeline("/path/to/My-Pipeline.yaml") loads the exact path."""
        # Write a file with a mixed-case filename; it should be loaded as-is
        mixed_path = _write_pipeline_yaml(tmp_path, "My-Pipeline")
        defn = load_pipeline(str(mixed_path))
        # The name inside the YAML is "My-Pipeline" (as written by the helper)
        assert defn.name == "My-Pipeline"


# ---------------------------------------------------------------------------
# T10: discover_pipelines lowercase normalisation
# ---------------------------------------------------------------------------


class TestDiscoverPipelinesNormalisation:
    def _write_yaml_with_name(self, directory: Path, filename: str, name: str) -> None:
        """Write a pipeline YAML where the 'name' field may differ from filename."""
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        data = {
            "name": name,
            "description": f"test pipeline {name}",
            "steps": [],
        }
        path.write_text(__import__("yaml").dump(data))

    def test_discover_returns_lowercase_name(self, tmp_path: Path) -> None:
        """discover_pipelines normalises names to lowercase."""
        import yaml

        proj = tmp_path / "project"
        proj.mkdir()
        # Write a valid pipeline YAML with a mixed-case 'name' field
        data = {
            "name": "MyPipeline",
            "description": "test",
            "steps": [{"design": {"phase": 0}}],
        }
        (proj / "mypipeline.yaml").write_text(yaml.dump(data))
        pipelines = discover_pipelines(
            project_dir=proj,
            user_dir=Path("/nonexistent"),
        )
        names = [p.name for p in pipelines]
        assert "mypipeline" in names
        assert "MyPipeline" not in names


# ---------------------------------------------------------------------------
# T13 — validate_pipeline catches bad emit entries in summary steps
# ---------------------------------------------------------------------------


class TestValidatePipelineSummaryStep:
    """validate_pipeline() propagates SummaryStepType.validate() errors."""

    def _make_pipeline(self, step_cfg: dict[str, object]) -> PipelineDefinition:
        from squadron.pipeline.models import PipelineDefinition, StepConfig

        return PipelineDefinition(
            name="test",
            description="test",
            params={},
            steps=[
                StepConfig(step_type="summary", name="summary-step", config=step_cfg)
            ],
        )

    def test_unknown_emit_produces_validation_error(self) -> None:
        from squadron.pipeline.loader import validate_pipeline

        defn = self._make_pipeline({"template": "minimal-sdk", "emit": ["banana"]})
        errors = validate_pipeline(defn)
        fields = [e.field for e in errors]
        assert "emit" in fields

    def test_valid_summary_step_no_errors(self) -> None:
        from squadron.pipeline.loader import validate_pipeline

        defn = self._make_pipeline({"template": "minimal-sdk"})
        errors = validate_pipeline(defn)
        assert errors == []

    def test_rotate_emit_validates_clean(self) -> None:
        from squadron.pipeline.loader import validate_pipeline

        defn = self._make_pipeline({"template": "minimal-sdk", "emit": ["rotate"]})
        errors = validate_pipeline(defn)
        assert errors == []
