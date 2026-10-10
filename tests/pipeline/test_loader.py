"""Unit tests for squadron.pipeline.loader — pipeline loading and discovery."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from squadron.data import data_dir
from squadron.pipeline.loader import (
    LISTING_ORDER,
    PipelineScope,
    PipelineSource,
    discover_pipelines,
    load_pipeline,
    pipeline_identity,
    pipeline_target_dir,
    resolve_pipeline,
)
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
            "P456",
            project_dir=Path("/nonexistent"),
            user_dir=Path("/nonexistent"),
        )
        assert isinstance(defn, PipelineDefinition)
        assert defn.name == "p456"
        assert len(defn.steps) == 12

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
        # Every shipped file is listed under its file name; no hand-kept list (#147).
        shipped = {pipeline_identity(p) for p in (data_dir() / "pipelines").glob("*.yaml")}
        assert {p.name for p in pipelines} == shipped

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

    def test_sources_are_tagged_with_the_enum(self, tmp_path: Path) -> None:
        _write_pipeline_yaml(tmp_path / "project", "proj-only")
        _write_pipeline_yaml(tmp_path / "user", "user-only")
        _write_pipeline_yaml(tmp_path / "project", "p4")  # shadows the built-in p4

        by_name = {
            p.name: p
            for p in discover_pipelines(project_dir=tmp_path / "project", user_dir=tmp_path / "user")
        }

        assert by_name["proj-only"].source is PipelineSource.PROJECT
        assert by_name["user-only"].source is PipelineSource.USER
        assert by_name["p456"].source is PipelineSource.BUILT_IN
        assert by_name["p4"].source is PipelineSource.PROJECT

    def test_shadowed_builtin_appears_once(self, tmp_path: Path) -> None:
        _write_pipeline_yaml(tmp_path, "p4")

        pipelines = discover_pipelines(project_dir=tmp_path, user_dir=Path("/nonexistent"))

        assert [p.source for p in pipelines if p.name == "p4"] == [PipelineSource.PROJECT]

    def test_listing_order(self) -> None:
        assert LISTING_ORDER == (
            PipelineSource.BUILT_IN,
            PipelineSource.PROJECT,
            PipelineSource.USER,
        )

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
        assert "p456" in names


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
        # The path is used as given; the identity is its lowercased stem (#147).
        mixed_path = _write_pipeline_yaml(tmp_path, "My-Pipeline")
        defn = load_pipeline(str(mixed_path))
        assert defn.name == "my-pipeline"


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


class TestIdentityIsFileName:
    """A name: field that disagrees with the file name is ignored (#147)."""

    def _write(self, directory: Path, stem: str, name_field: str) -> Path:
        import yaml

        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{stem}.yaml"
        data = {"name": name_field, "steps": [{"design": {"phase": 4}}]}
        path.write_text(yaml.dump(data))
        return path

    def test_load_by_name_uses_file_name(self, tmp_path: Path) -> None:
        self._write(tmp_path, "p4", "slice-design")
        defn = load_pipeline("p4", project_dir=tmp_path, user_dir=Path("/nonexistent"))
        assert defn.name == "p4"

    def test_mixed_case_file_found_by_lowercase_name(self, tmp_path: Path) -> None:
        # P4.yaml ships in the package; on a case-sensitive filesystem a lookup that
        # builds "p4.yaml" misses it. Only CI on Linux can fail this.
        self._write(tmp_path, "P4", "anything")
        defn = load_pipeline("P4", project_dir=tmp_path, user_dir=Path("/nonexistent"))
        assert defn.name == "p4"

    def test_discover_lists_file_name(self, tmp_path: Path) -> None:
        self._write(tmp_path, "p4", "slice-design")
        self._write(tmp_path, "test-p4", "p4")
        names = [
            p.name
            for p in discover_pipelines(project_dir=tmp_path, user_dir=Path("/nonexistent"))
            if p.source == "project"
        ]
        assert sorted(names) == ["p4", "test-p4"]


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
            steps=[StepConfig(step_type="summary", name="summary-step", config=step_cfg)],
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


# ---------------------------------------------------------------------------
# Slice 263 — validate_pipeline surfaces allowed_tools errors
# ---------------------------------------------------------------------------


class TestValidatePipelineAllowedTools:
    """The registry check is reachable from the real entry point, not just in isolation."""

    def _make_pipeline(self, step_cfg: dict[str, object]) -> PipelineDefinition:
        from squadron.pipeline.models import PipelineDefinition, StepConfig

        return PipelineDefinition(
            name="test",
            description="test",
            params={},
            steps=[StepConfig(step_type="dispatch", name="dispatch-step", config=step_cfg)],
        )

    def test_unknown_tool_produces_validation_error(self) -> None:
        from squadron.pipeline.loader import validate_pipeline

        defn = self._make_pipeline({"prompt": "hi", "allowed_tools": ["read_fil"]})
        errors = validate_pipeline(defn)
        assert errors
        assert any(e.field == "allowed_tools" and "read_fil" in e.message for e in errors)

    def test_known_tools_validate_clean(self) -> None:
        from squadron.pipeline.loader import validate_pipeline

        defn = self._make_pipeline({"prompt": "hi", "allowed_tools": ["read_file"]})
        assert validate_pipeline(defn) == []


class TestPipelineInfoParams:
    """PipelineInfo.params keeps declaration order and defaults (slice 174)."""

    def test_params_in_declaration_order_with_defaults(self, tmp_path: Path) -> None:
        proj = tmp_path / "project"
        proj.mkdir()
        (proj / "ordered.yaml").write_text(
            "name: ordered\n"
            "description: d\n"
            "params:\n"
            "  slice: required\n"
            "  model: sonnet\n"
            "  max-revisions: '2'\n"
            "steps:\n"
            "  - design: { phase: 4 }\n"
        )

        info = {p.name: p for p in discover_pipelines(project_dir=proj, user_dir=tmp_path / "u")}

        assert list(info["ordered"].params.items()) == [
            ("slice", "required"),
            ("model", "sonnet"),
            ("max-revisions", "2"),
        ]

    def test_pipeline_without_params_has_none(self, tmp_path: Path) -> None:
        proj = tmp_path / "project"
        _write_pipeline_yaml(proj, "bare")

        info = {p.name: p for p in discover_pipelines(project_dir=proj, user_dir=tmp_path / "u")}

        assert info["bare"].params == {}


class TestPipelineTargetDir:
    """The copy target of each scope is the directory the search reads for that source."""

    @pytest.mark.parametrize(
        ("scope", "source"),
        [(PipelineScope.USER, PipelineSource.USER), (PipelineScope.PROJECT, PipelineSource.PROJECT)],
    )
    def test_a_file_written_to_the_target_is_found_under_that_source(
        self,
        scope: PipelineScope,
        source: PipelineSource,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.chdir(tmp_path)
        _write_pipeline_yaml(pipeline_target_dir(scope), "copied-pipe")

        location = resolve_pipeline("copied-pipe")

        assert location.source is source
        assert location.path.parent == pipeline_target_dir(scope)

    def test_project_target_is_the_project_documents_pipelines_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        target = pipeline_target_dir(PipelineScope.PROJECT)

        assert target.resolve() == (tmp_path / "project-documents/user/pipelines").resolve()
