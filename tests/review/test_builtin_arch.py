"""Tests for the slice (formerly arch) built-in review template."""

from __future__ import annotations

from pathlib import Path

from squadron.review.templates import load_template


def _slice_yaml() -> Path:
    from squadron.data import data_dir

    return data_dir() / "templates" / "slice.yaml"


class TestArchTemplate:
    """Test slice.yaml template loading and prompt construction."""

    def test_load_template(self) -> None:
        t = load_template(_slice_yaml())
        assert t.name == "slice"
        assert "slice design review" in t.description.lower()
        assert t.allowed_tools == ["Read", "Glob", "Grep"]
        assert t.permission_mode == "bypassPermissions"
        assert t.setting_sources is None
        assert t.prompt_builder is None
        assert t.prompt_template is not None
        assert t.model == "opus"

    def test_required_inputs(self) -> None:
        t = load_template(_slice_yaml())
        names = [i.name for i in t.required_inputs]
        assert "input" in names
        assert "against" in names

    def test_optional_inputs(self) -> None:
        t = load_template(_slice_yaml())
        names = [i.name for i in t.optional_inputs]
        assert "cwd" in names
        cwd_def = next(i for i in t.optional_inputs if i.name == "cwd")
        assert cwd_def.default == "."

    def test_build_prompt_required_inputs(self) -> None:
        t = load_template(_slice_yaml())
        prompt = t.build_prompt(
            {"input": "slices/105-slice.md", "against": "arch/050-arch.md"}
        )
        assert "slices/105-slice.md" in prompt
        assert "arch/050-arch.md" in prompt

    def test_build_prompt_with_optional_cwd(self) -> None:
        t = load_template(_slice_yaml())
        prompt = t.build_prompt(
            {
                "input": "slice.md",
                "against": "arch.md",
                "cwd": "/project/root",
            }
        )
        assert "slice.md" in prompt
        assert "arch.md" in prompt
