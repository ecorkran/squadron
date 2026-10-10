"""Tests for src/squadron/review/rules.py — language detection and rules matching."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.review.rules import (
    RulesSource,
    get_template_rules,
    load_rules_content,
    load_rules_frontmatter,
    match_rules_files,
    resolve_rules_dir,
)

# ---------------------------------------------------------------------------
# resolve_rules_dir
# ---------------------------------------------------------------------------


class TestResolveRulesDir:
    """Test rules directory resolution priority."""

    def test_cli_flag_wins(self, tmp_path: Path) -> None:
        """CLI flag overrides all others."""
        cli_dir = tmp_path / "cli-rules"
        cli_dir.mkdir()
        config_dir = tmp_path / "config-rules"
        config_dir.mkdir()

        result, source = resolve_rules_dir(str(tmp_path), str(config_dir), str(cli_dir))
        assert result == cli_dir
        assert source is RulesSource.FLAG

    def test_config_wins_over_default(self, tmp_path: Path) -> None:
        """Config beats cwd default."""
        config_dir = tmp_path / "config-rules"
        config_dir.mkdir()
        # create cwd/rules too — should be ignored since config present
        (tmp_path / "rules").mkdir()

        with patch("squadron.review.rules.get_config", return_value=str(config_dir)):
            result, source = resolve_rules_dir(str(tmp_path), None, None)
        assert result == config_dir
        assert source is RulesSource.CONFIG

    def test_falls_back_to_cwd_rules(self, tmp_path: Path) -> None:
        """Uses {cwd}/rules/ when it exists."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()

        with patch("squadron.review.rules.get_config", return_value=None):
            result, source = resolve_rules_dir(str(tmp_path), None, None)
        assert result == rules_dir
        assert source is RulesSource.PROJECT

    def test_claude_rules_fallback(self, tmp_path: Path) -> None:
        """Uses .claude/rules/ when rules/ is absent."""
        claude_rules = tmp_path / ".claude" / "rules"
        claude_rules.mkdir(parents=True)

        with patch("squadron.review.rules.get_config", return_value=None):
            result, source = resolve_rules_dir(str(tmp_path), None, None)
        assert result == claude_rules
        # Both project-local layouts report PROJECT: the source answers whose
        # rules these are, and either layout answers "the project's".
        assert source is RulesSource.PROJECT

    def test_user_rules_fallback(self, tmp_path: Path) -> None:
        """Uses ~/.config/squadron/rules/ when project-level dirs are absent."""
        project = tmp_path / "project"
        project.mkdir()
        user_rules = tmp_path / ".config" / "squadron" / "rules"
        user_rules.mkdir(parents=True)

        with (
            patch("squadron.review.rules.get_config", return_value=None),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            result, source = resolve_rules_dir(str(project), None, None)
        assert result == user_rules
        assert source is RulesSource.USER

    def test_user_templates_fallback(self, tmp_path: Path) -> None:
        """Uses ~/.config/squadron/templates/ when even user rules/ is absent."""
        project = tmp_path / "project"
        project.mkdir()
        user_templates = tmp_path / ".config" / "squadron" / "templates"
        user_templates.mkdir(parents=True)

        with (
            patch("squadron.review.rules.get_config", return_value=None),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            result, source = resolve_rules_dir(str(project), None, None)
        assert result == user_templates
        assert source is RulesSource.TEMPLATE

    def test_user_rules_beats_templates(self, tmp_path: Path) -> None:
        """Templates sit at the tail: user rules/ still wins when both exist."""
        project = tmp_path / "project"
        project.mkdir()
        user_rules = tmp_path / ".config" / "squadron" / "rules"
        user_rules.mkdir(parents=True)
        (tmp_path / ".config" / "squadron" / "templates").mkdir(parents=True)

        with (
            patch("squadron.review.rules.get_config", return_value=None),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            result, source = resolve_rules_dir(str(project), None, None)
        assert result == user_rules
        assert source is RulesSource.USER

    def test_user_rules_fallback_creates_path(self, tmp_path: Path) -> None:
        """User rules dir must exist to be returned."""
        with (
            patch("squadron.review.rules.get_config", return_value=None),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            result, source = resolve_rules_dir(str(tmp_path), None, None)
        assert result is None
        assert source is RulesSource.NONE

    def test_returns_none_when_none_exist(self, tmp_path: Path) -> None:
        """Returns None when no rules dir found."""
        with (
            patch("squadron.review.rules.get_config", return_value=None),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            result, source = resolve_rules_dir(str(tmp_path), None, None)
        assert result is None
        assert source is RulesSource.NONE

    def test_cli_flag_nonexistent_returns_none(self, tmp_path: Path) -> None:
        """CLI flag pointing to non-existent dir returns None."""
        result, source = resolve_rules_dir(str(tmp_path), None, str(tmp_path / "nope"))
        assert result is None
        assert source is RulesSource.NONE


# ---------------------------------------------------------------------------
# load_rules_frontmatter
# ---------------------------------------------------------------------------


class TestLoadRulesFrontmatter:
    """Test frontmatter parsing and filename-based fallback."""

    def test_frontmatter_inline_paths(self, tmp_path: Path) -> None:
        """Parses inline-list paths from frontmatter."""
        (tmp_path / "python.md").write_text("---\npaths: [**/*.py, **/*.pyi]\n---\nPython rules.\n")
        result = load_rules_frontmatter(tmp_path)
        assert "python.md" in result
        assert "**/*.py" in result["python.md"]

    def test_frontmatter_block_paths(self, tmp_path: Path) -> None:
        """Parses block-list paths from frontmatter."""
        (tmp_path / "ts.md").write_text("---\npaths:\n  - **/*.ts\n  - **/*.tsx\n---\nTS rules.\n")
        result = load_rules_frontmatter(tmp_path)
        assert "ts.md" in result
        assert "**/*.ts" in result["ts.md"]

    def test_filename_fallback_python(self, tmp_path: Path) -> None:
        """python.md with no frontmatter paths falls back to **/*.py."""
        (tmp_path / "python.md").write_text("Python rules.\n")
        result = load_rules_frontmatter(tmp_path)
        assert "python.md" in result
        assert "**/*.py" in result["python.md"]

    def test_skips_non_md(self, tmp_path: Path) -> None:
        """Non-.md files are ignored."""
        (tmp_path / "python.txt").write_text("not a rules file")
        result = load_rules_frontmatter(tmp_path)
        assert "python.txt" not in result


# ---------------------------------------------------------------------------
# match_rules_files
# ---------------------------------------------------------------------------


#: The guide's real rules directory: the frontmatter these tests parse is what
#: production reads, not a hand-made fixture.
_GUIDE_RULES_DIR = (
    Path(__file__).resolve().parents[2]
    / "project-documents"
    / "ai-project-guide"
    / "project-guides"
    / "rules"
)


class TestMatchRulesFiles:
    """Test path-to-rules-file matching."""

    def test_match_by_extension(self, tmp_path: Path) -> None:
        py_file = tmp_path / "python.md"
        py_file.write_text("Python rules.")
        frontmatter = {"python.md": ["**/*.py"]}

        assert py_file in match_rules_files(["src/app/main.py"], tmp_path, frontmatter)

    def test_top_level_file_matches_double_star_prefix(self, tmp_path: Path) -> None:
        frontmatter = {"python.md": ["**/*.py"]}
        assert match_rules_files(["main.py"], tmp_path, frontmatter) == [tmp_path / "python.md"]

    def test_no_match_for_unrelated_extension(self, tmp_path: Path) -> None:
        frontmatter = {"python.md": ["**/*.py"]}
        assert match_rules_files(["src/lib.rs"], tmp_path, frontmatter) == []

    def test_empty_paths_match_nothing(self, tmp_path: Path) -> None:
        assert match_rules_files([], tmp_path, {"python.md": ["**/*.py"]}) == []

    def test_result_is_sorted(self, tmp_path: Path) -> None:
        frontmatter = {"z_rules.md": ["**/*.py"], "a_rules.md": ["**/*.py"]}
        matched = match_rules_files(["a.py"], tmp_path, frontmatter)
        assert matched == sorted(matched)


class TestShellRulesMatching:
    """shell.md's real frontmatter against real-shaped paths (guide v0.20.x)."""

    @pytest.fixture
    def frontmatter(self) -> dict[str, list[str]]:
        return load_rules_frontmatter(_GUIDE_RULES_DIR)

    def _matches_shell(
        self, paths: list[str], frontmatter: dict[str, list[str]], cwd: str | None = None
    ) -> bool:
        matched = match_rules_files(paths, _GUIDE_RULES_DIR, frontmatter, cwd)
        return _GUIDE_RULES_DIR / "shell.md" in matched

    def test_real_frontmatter_lists_the_documented_globs(
        self, frontmatter: dict[str, list[str]]
    ) -> None:
        assert frontmatter["shell.md"] == [
            "**/*.sh",
            "**/*.bash",
            "**/.github/workflows/*.yml",
            "**/.github/workflows/*.yaml",
            "**/.gitlab-ci.yml",
        ]

    @pytest.mark.parametrize(
        "path",
        [
            "deploy.sh",
            "scripts/build.sh",
            "tools/x/run.bash",
            ".github/workflows/ci.yml",
            "sub/.github/workflows/release.yaml",
            ".gitlab-ci.yml",
            "svc/.gitlab-ci.yml",
        ],
    )
    def test_shell_and_ci_paths_match(self, path: str, frontmatter: dict[str, list[str]]) -> None:
        assert self._matches_shell([path], frontmatter)

    @pytest.mark.parametrize(
        "path",
        [
            "config.yml",
            "docs/openapi.yaml",
            "src/squadron/data/pipelines/P6.yaml",
            ".github/dependabot.yml",
            ".github/workflows/notes.txt",
            "src/app.py",
            "other.gitlab-ci.yml.bak",
        ],
    )
    def test_other_files_do_not_match(self, path: str, frontmatter: dict[str, list[str]]) -> None:
        assert not self._matches_shell([path], frontmatter)

    @pytest.mark.parametrize(
        "first_line",
        ["#!/bin/bash", "#!/bin/sh", "#!/usr/bin/env bash", "#!/usr/bin/env -S bash -e", "#! /bin/sh"],
    )
    def test_extensionless_shell_script_matches(
        self, first_line: str, tmp_path: Path, frontmatter: dict[str, list[str]]
    ) -> None:
        (tmp_path / "bin").mkdir()
        (tmp_path / "bin" / "deploy").write_text(f"{first_line}\nset -e\n")
        assert self._matches_shell(["bin/deploy"], frontmatter, str(tmp_path))

    @pytest.mark.parametrize("first_line", ["#!/usr/bin/env python3", "#!/bin/zsh", "no shebang"])
    def test_extensionless_non_shell_script_does_not_match(
        self, first_line: str, tmp_path: Path, frontmatter: dict[str, list[str]]
    ) -> None:
        (tmp_path / "tool").write_text(f"{first_line}\n")
        assert not self._matches_shell(["tool"], frontmatter, str(tmp_path))

    def test_deleted_extensionless_path_does_not_raise(
        self, tmp_path: Path, frontmatter: dict[str, list[str]]
    ) -> None:
        assert not self._matches_shell(["gone"], frontmatter, str(tmp_path))


# ---------------------------------------------------------------------------
# get_template_rules
# ---------------------------------------------------------------------------


class TestGetTemplateRules:
    """Test template-specific rules file discovery."""

    def test_both_files_concatenated(self, tmp_path: Path) -> None:
        """review.md and review-slice.md both present → concatenated."""
        (tmp_path / "review.md").write_text("General review rules.")
        (tmp_path / "review-slice.md").write_text("Slice-specific rules.")

        result = get_template_rules("slice", tmp_path)
        assert result is not None
        assert "General review rules." in result
        assert "Slice-specific rules." in result

    def test_general_only(self, tmp_path: Path) -> None:
        """Only review.md present → returned alone."""
        (tmp_path / "review.md").write_text("General review rules.")

        result = get_template_rules("code", tmp_path)
        assert result == "General review rules."

    def test_none_present(self, tmp_path: Path) -> None:
        """Neither file present → returns None."""
        result = get_template_rules("tasks", tmp_path)
        assert result is None

    def test_template_specific_only(self, tmp_path: Path) -> None:
        """Only review-code.md present → returned alone."""
        (tmp_path / "review-code.md").write_text("Code rules.")

        result = get_template_rules("code", tmp_path)
        assert result == "Code rules."


# ---------------------------------------------------------------------------
# load_rules_content
# ---------------------------------------------------------------------------


class TestLoadRulesContent:
    """Test reading and concatenating rules file content."""

    def test_concatenates_with_separator(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.md"
        f2 = tmp_path / "b.md"
        f1.write_text("Rule A.")
        f2.write_text("Rule B.")

        content = load_rules_content([f1, f2])
        assert "Rule A." in content
        assert "Rule B." in content
        assert "---" in content

    def test_empty_list(self) -> None:
        assert load_rules_content([]) == ""

    def test_skips_unreadable(self, tmp_path: Path) -> None:
        """Non-existent file is silently skipped."""
        f1 = tmp_path / "a.md"
        f1.write_text("Rule A.")
        content = load_rules_content([f1, tmp_path / "nonexistent.md"])
        assert "Rule A." in content
