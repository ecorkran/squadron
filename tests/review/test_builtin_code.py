"""Tests for the code built-in review template and prompt builder."""

from __future__ import annotations

from pathlib import Path

from squadron.review.builders.code import code_review_prompt
from squadron.review.templates import load_template


def _code_yaml() -> Path:
    from squadron.data import data_dir

    return data_dir() / "templates" / "code.yaml"


class TestCodeTemplate:
    """Test code.yaml template loading."""

    def test_load_template(self) -> None:
        t = load_template(_code_yaml())
        assert t.name == "code"
        assert t.prompt_builder is not None
        assert callable(t.prompt_builder)
        assert t.prompt_template is None
        assert t.allowed_tools == ["Read", "Glob", "Grep", "Bash"]
        assert t.permission_mode == "bypassPermissions"
        assert t.setting_sources == ["project"]
        assert t.model == "sonnet"

    def test_no_required_inputs(self) -> None:
        t = load_template(_code_yaml())
        assert t.required_inputs == []

    def test_optional_inputs(self) -> None:
        t = load_template(_code_yaml())
        names = [i.name for i in t.optional_inputs]
        assert "cwd" in names
        assert "files" in names
        assert "diff" in names


class TestCodeReviewPrompt:
    """Test code_review_prompt builder function."""

    def test_diff_only(self) -> None:
        prompt = code_review_prompt({"diff": "main", "cwd": "."})
        assert "git diff main" in prompt
        assert "." in prompt

    def test_files_only(self) -> None:
        prompt = code_review_prompt({"files": "src/**/*.py", "cwd": "/proj"})
        assert "src/**/*.py" in prompt
        assert "/proj" in prompt

    def test_neither_diff_nor_files(self) -> None:
        prompt = code_review_prompt({"cwd": "/project"})
        assert "Survey" in prompt
        assert "/project" in prompt

    def test_both_diff_and_files(self) -> None:
        prompt = code_review_prompt(
            {"diff": "HEAD~3", "files": "src/**/*.py", "cwd": "."}
        )
        assert "git diff HEAD~3" in prompt
        assert "src/**/*.py" in prompt

    def test_default_cwd(self) -> None:
        prompt = code_review_prompt({})
        assert "." in prompt

    def test_build_prompt_via_template(self) -> None:
        t = load_template(_code_yaml())
        prompt = t.build_prompt({"cwd": "/myproject", "diff": "main"})
        assert "/myproject" in prompt
        assert "git diff main" in prompt
