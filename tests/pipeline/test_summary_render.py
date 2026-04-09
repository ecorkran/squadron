"""Tests for pipeline.summary_render — shared helpers for template rendering."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.integrations.context_forge import (
    ContextForgeError,
    ContextForgeNotAvailable,
    ProjectInfo,
)
from squadron.pipeline import summary_render as mod
from squadron.pipeline.summary_render import (
    gather_cf_params,
    resolve_template_instructions,
    resolve_template_suffix,
)

# ---------------------------------------------------------------------------
# resolve_template_instructions
# ---------------------------------------------------------------------------


class TestResolveTemplateInstructions:
    def test_builtin_minimal_returns_nonempty(self) -> None:
        """Loading the built-in 'minimal' template produces rendered text."""
        result = resolve_template_instructions("minimal")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_nonexistent_template_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            resolve_template_instructions("nonexistent")

    def test_renders_slice_placeholder_when_cf_provides_it(self) -> None:
        """When CF returns a slice, {slice} placeholders are substituted."""
        info = ProjectInfo(
            arch_file="x.md",
            slice_plan="y.md",
            phase="4",
            slice="162",
        )
        with patch.object(
            mod.ContextForgeClient,
            "get_project",
            return_value=info,
        ):
            result = resolve_template_instructions("minimal")
        # minimal.yaml contains {slice} — should be rendered to "162"
        assert "162" in result
        assert "{slice}" not in result

    def test_preserves_placeholders_when_cf_unavailable(self) -> None:
        """Without CF, {slice} stays as literal text via LenientDict."""
        with patch.object(
            mod.ContextForgeClient,
            "get_project",
            side_effect=ContextForgeNotAvailable("not installed"),
        ):
            result = resolve_template_instructions("minimal")
        assert "{slice}" in result

    def test_minimal_sdk_template_loads(self) -> None:
        """The built-in 'minimal-sdk' template also loads successfully."""
        result = resolve_template_instructions("minimal-sdk")
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# gather_cf_params
# ---------------------------------------------------------------------------


class TestGatherCfParams:
    def test_returns_info_on_success(self, tmp_path: Path) -> None:
        info = ProjectInfo(
            arch_file="x.md",
            slice_plan="y.md",
            phase="5",
            slice="162",
        )
        with patch.object(
            mod.ContextForgeClient,
            "get_project",
            return_value=info,
        ):
            params = gather_cf_params(str(tmp_path))
        assert params == {"slice": "162", "phase": "5", "project": tmp_path.name}

    def test_returns_empty_on_context_forge_error(self, tmp_path: Path) -> None:
        with patch.object(
            mod.ContextForgeClient,
            "get_project",
            side_effect=ContextForgeError("cf get failed"),
        ):
            assert gather_cf_params(str(tmp_path)) == {}

    def test_returns_empty_when_cf_not_available(self, tmp_path: Path) -> None:
        with patch.object(
            mod.ContextForgeClient,
            "get_project",
            side_effect=ContextForgeNotAvailable("not installed"),
        ):
            assert gather_cf_params(str(tmp_path)) == {}

    def test_returns_empty_on_missing_cwd(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nope"
        assert gather_cf_params(str(nonexistent)) == {}

    def test_empty_slice_and_phase_omitted(self, tmp_path: Path) -> None:
        """Empty CF values should not clobber {slice}/{phase} placeholders."""
        info = ProjectInfo(arch_file="x.md", slice_plan="y.md", phase="", slice="")
        with patch.object(
            mod.ContextForgeClient,
            "get_project",
            return_value=info,
        ):
            params = gather_cf_params(str(tmp_path))
        assert params == {"project": tmp_path.name}


# ---------------------------------------------------------------------------
# resolve_template_suffix
# ---------------------------------------------------------------------------


class TestResolveTemplateSuffix:
    def test_minimal_sdk_returns_nonempty_suffix(self) -> None:
        """minimal-sdk.yaml defines a suffix; it should be returned."""
        result = resolve_template_suffix("minimal-sdk")
        assert isinstance(result, str)
        assert len(result.strip()) > 0
        assert "Do not take any action" in result

    def test_minimal_returns_empty_suffix(self) -> None:
        """minimal.yaml has no suffix field; returns empty string."""
        result = resolve_template_suffix("minimal")
        assert result == ""

    def test_nonexistent_template_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            resolve_template_suffix("nonexistent")
