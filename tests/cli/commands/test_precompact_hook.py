"""Tests for the hidden ``sq _precompact-hook`` subcommand and its helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands import precompact_hook as hook_mod
from squadron.cli.commands.precompact_hook import (
    _gather_params,
    _resolve_instructions,
    precompact_hook,
)
from squadron.config.manager import set_config
from squadron.integrations.context_forge import (
    ContextForgeError,
    ContextForgeNotAvailable,
    ProjectInfo,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# T6: hidden subcommand registration
# ---------------------------------------------------------------------------


class TestHiddenRegistration:
    def test_not_listed_in_top_level_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "_precompact-hook" not in result.output
        assert "precompact" not in result.output.lower()

    def test_hidden_command_is_still_invokable(self) -> None:
        result = runner.invoke(app, ["_precompact-hook", "--help"])
        assert result.exit_code == 0

    def test_hidden_command_no_config_runs_clean(
        self, tmp_path: Path, patch_config_paths: dict[str, Path]
    ) -> None:
        result = runner.invoke(app, ["_precompact-hook"])
        assert result.exit_code == 0
        payload = json.loads(result.output.strip())
        assert payload["hookSpecificOutput"]["hookEventName"] == "PreCompact"


# ---------------------------------------------------------------------------
# T3: _resolve_instructions
# ---------------------------------------------------------------------------


class TestResolveInstructions:
    def test_literal_instructions_wins(
        self, patch_config_paths: dict[str, Path]
    ) -> None:
        set_config("compact.instructions", "literal text", project=True)
        assert _resolve_instructions(".") == "literal text"

    def test_template_default_minimal(
        self, patch_config_paths: dict[str, Path]
    ) -> None:
        # No config set — default template is "minimal", which ships in
        # src/squadron/data/compaction/minimal.yaml
        result = _resolve_instructions(".")
        assert "{slice}" in result
        assert "slice" in result.lower()

    def test_literal_beats_template_when_both_set(
        self, patch_config_paths: dict[str, Path]
    ) -> None:
        set_config("compact.template", "minimal", project=True)
        set_config("compact.instructions", "literal wins", project=True)
        assert _resolve_instructions(".") == "literal wins"

    def test_nonexistent_template_returns_empty(
        self, patch_config_paths: dict[str, Path]
    ) -> None:
        set_config("compact.template", "does-not-exist", project=True)
        assert _resolve_instructions(".") == ""

    def test_empty_literal_falls_through_to_template(
        self, patch_config_paths: dict[str, Path]
    ) -> None:
        # Whitespace-only literal should NOT beat template
        set_config("compact.instructions", "   ", project=True)
        result = _resolve_instructions(".")
        assert "{slice}" in result


# ---------------------------------------------------------------------------
# T4: _gather_params
# ---------------------------------------------------------------------------


class TestGatherParams:
    def test_returns_info_on_success(self, tmp_path: Path) -> None:
        info = ProjectInfo(
            arch_file="x.md",
            slice_plan="y.md",
            phase="5",
            slice="157",
        )
        with patch.object(
            hook_mod.ContextForgeClient,
            "get_project",
            return_value=info,
        ):
            params = _gather_params(str(tmp_path))
        assert params == {"slice": "157", "phase": "5", "project": tmp_path.name}

    def test_returns_empty_on_context_forge_error(self, tmp_path: Path) -> None:
        with patch.object(
            hook_mod.ContextForgeClient,
            "get_project",
            side_effect=ContextForgeError("cf get failed"),
        ):
            assert _gather_params(str(tmp_path)) == {}

    def test_returns_empty_when_cf_not_available(self, tmp_path: Path) -> None:
        with patch.object(
            hook_mod.ContextForgeClient,
            "get_project",
            side_effect=ContextForgeNotAvailable("cf not installed"),
        ):
            assert _gather_params(str(tmp_path)) == {}

    def test_returns_empty_on_missing_cwd(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nope"
        # No patching needed — chdir into a missing dir should short-circuit
        assert _gather_params(str(nonexistent)) == {}

    def test_empty_slice_and_phase_are_omitted(self, tmp_path: Path) -> None:
        """Empty CF values should NOT clobber {slice}/{phase} placeholders."""
        info = ProjectInfo(arch_file="x.md", slice_plan="y.md", phase="", slice="")
        with patch.object(
            hook_mod.ContextForgeClient,
            "get_project",
            return_value=info,
        ):
            params = _gather_params(str(tmp_path))
        # project is always set; slice/phase omitted when empty
        assert params == {"project": tmp_path.name}


# ---------------------------------------------------------------------------
# T5: precompact_hook command body
# ---------------------------------------------------------------------------


class TestPrecompactHookCommand:
    def test_renders_params_into_additional_context(
        self, tmp_path: Path, patch_config_paths: dict[str, Path]
    ) -> None:
        with (
            patch.object(
                hook_mod,
                "_resolve_instructions",
                return_value="Keep slice {slice}.",
            ),
            patch.object(
                hook_mod,
                "_gather_params",
                return_value={"slice": "157"},
            ),
        ):
            result = runner.invoke(app, ["_precompact-hook"])
        assert result.exit_code == 0
        payload = json.loads(result.output.strip())
        assert payload["hookSpecificOutput"]["hookEventName"] == "PreCompact"
        assert payload["hookSpecificOutput"]["additionalContext"] == "Keep slice 157."

    def test_unexpected_error_yields_empty_context_exit_zero(
        self, tmp_path: Path, patch_config_paths: dict[str, Path]
    ) -> None:
        with patch.object(
            hook_mod,
            "_resolve_instructions",
            side_effect=RuntimeError("boom"),
        ):
            result = runner.invoke(app, ["_precompact-hook"])
        assert result.exit_code == 0
        payload = json.loads(result.output.strip())
        assert payload["hookSpecificOutput"]["additionalContext"] == ""
        assert payload["hookSpecificOutput"]["hookEventName"] == "PreCompact"

    def test_output_is_single_line_json(
        self, tmp_path: Path, patch_config_paths: dict[str, Path]
    ) -> None:
        with (
            patch.object(hook_mod, "_resolve_instructions", return_value="hi"),
            patch.object(hook_mod, "_gather_params", return_value={}),
        ):
            result = runner.invoke(app, ["_precompact-hook"])
        assert result.exit_code == 0
        # Exactly one JSON line on stdout (trailing newline from print() OK)
        lines = [ln for ln in result.output.splitlines() if ln.strip()]
        assert len(lines) == 1
        json.loads(lines[0])  # parseable

    def test_direct_invocation_no_typer(
        self,
        tmp_path: Path,
        patch_config_paths: dict[str, Path],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with (
            patch.object(hook_mod, "_resolve_instructions", return_value="x"),
            patch.object(hook_mod, "_gather_params", return_value={}),
        ):
            precompact_hook(cwd=".")
        captured = capsys.readouterr()
        payload = json.loads(captured.out.strip())
        assert payload["hookSpecificOutput"]["additionalContext"] == "x"
