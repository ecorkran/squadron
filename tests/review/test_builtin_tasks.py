"""Tests for the tasks built-in review template."""

from __future__ import annotations

from pathlib import Path

from squadron.review.templates import load_template


def _tasks_yaml() -> Path:
    from squadron.data import data_dir

    return data_dir() / "templates" / "tasks.yaml"


class TestTasksTemplate:
    """Test tasks.yaml template loading and prompt construction."""

    def test_load_template(self) -> None:
        t = load_template(_tasks_yaml())
        assert t.name == "tasks"
        assert "task" in t.description.lower()
        assert t.allowed_tools == ["Read", "Glob", "Grep"]
        assert t.permission_mode == "bypassPermissions"
        assert t.setting_sources is None
        assert t.prompt_builder is None
        assert t.prompt_template is not None
        assert t.model == "opus"

    def test_required_inputs(self) -> None:
        t = load_template(_tasks_yaml())
        names = [i.name for i in t.required_inputs]
        assert "input" in names
        assert "against" in names

    def test_build_prompt_with_required_inputs(self) -> None:
        t = load_template(_tasks_yaml())
        prompt = t.build_prompt(
            {"input": "tasks/105-tasks.md", "against": "slices/105-slice.md"}
        )
        assert "tasks/105-tasks.md" in prompt
        assert "slices/105-slice.md" in prompt
