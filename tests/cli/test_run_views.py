"""Rich views shared by the run, pipelines and runs commands (slice 199)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from squadron.cli.run_views import render_pipeline_listing
from squadron.data import data_dir
from squadron.pipeline.loader import discover_pipelines


def write_pipeline(directory: Path, name: str, description: str = "") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    data = {
        "name": name,
        "description": description or f"{name} pipeline",
        "steps": [{"design": {"phase": 4}}],
    }
    (directory / f"{name}.yaml").write_text(yaml.dump(data))


class TestPipelineListing:
    def test_groups_in_listing_order_with_shadowing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        project, user = tmp_path / "project", tmp_path / "user"
        write_pipeline(project, "zeta")
        write_pipeline(project, "alpha")
        write_pipeline(project, "p4", "project copy of p4")
        write_pipeline(user, "mine")

        render_pipeline_listing(discover_pipelines(project_dir=project, user_dir=user))
        out = capsys.readouterr().out

        built_in_count = len(list((data_dir() / "pipelines").glob("*.yaml"))) - 1  # p4 shadowed
        built_in = out.index(f"Built-in ({built_in_count})")
        project_at = out.index("Project (3)")
        user_at = out.index("User (1)")
        assert built_in < project_at < user_at
        assert out.index("alpha") < out.index("zeta")
        # p4 appears only under Project, as its project copy.
        assert "project copy of p4" in out[project_at:user_at]
        assert " p4 " not in out[built_in:project_at]

    def test_empty_group_is_omitted(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        render_pipeline_listing(
            discover_pipelines(project_dir=tmp_path / "none", user_dir=tmp_path / "none")
        )
        out = capsys.readouterr().out

        assert "Built-in (" in out
        assert "Project (" not in out
        assert "User (" not in out

    def test_no_pipelines(self, capsys: pytest.CaptureFixture[str]) -> None:
        render_pipeline_listing([])
        assert capsys.readouterr().out.strip() == "No pipelines found."
