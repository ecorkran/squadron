"""Tests for src/squadron/review/rules.py — language detection and rules matching."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.review.rules import (
    detect_languages_from_paths,
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

        result = resolve_rules_dir(str(tmp_path), str(config_dir), str(cli_dir))
        assert result == cli_dir

    def test_config_wins_over_default(self, tmp_path: Path) -> None:
        """Config beats cwd default."""
        config_dir = tmp_path / "config-rules"
        config_dir.mkdir()
        # create cwd/rules too — should be ignored since config present
        (tmp_path / "rules").mkdir()

        with patch("squadron.review.rules.get_config", return_value=str(config_dir)):
            result = resolve_rules_dir(str(tmp_path), None, None)
        assert result == config_dir

    def test_falls_back_to_cwd_rules(self, tmp_path: Path) -> None:
        """Uses {cwd}/rules/ when it exists."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()

        with patch("squadron.review.rules.get_config", return_value=None):
            result = resolve_rules_dir(str(tmp_path), None, None)
        assert result == rules_dir

    def test_claude_rules_fallback(self, tmp_path: Path) -> None:
        """Uses .claude/rules/ when rules/ is absent."""
        claude_rules = tmp_path / ".claude" / "rules"
        claude_rules.mkdir(parents=True)

        with patch("squadron.review.rules.get_config", return_value=None):
            result = resolve_rules_dir(str(tmp_path), None, None)
        assert result == claude_rules

    def test_returns_none_when_none_exist(self, tmp_path: Path) -> None:
        """Returns None when no rules dir found."""
        with patch("squadron.review.rules.get_config", return_value=None):
            result = resolve_rules_dir(str(tmp_path), None, None)
        assert result is None

    def test_cli_flag_nonexistent_returns_none(self, tmp_path: Path) -> None:
        """CLI flag pointing to non-existent dir returns None."""
        result = resolve_rules_dir(str(tmp_path), None, str(tmp_path / "nope"))
        assert result is None


# ---------------------------------------------------------------------------
# detect_languages_from_paths
# ---------------------------------------------------------------------------


class TestDetectLanguages:
    """Test extension extraction from diff paths."""

    def test_extracts_py_and_ts(self) -> None:
        paths = [
            "+++ b/src/main.py",
            "+++ b/frontend/app.ts",
            "+++ b/package.json",
        ]
        exts = detect_languages_from_paths(paths)
        assert ".py" in exts
        assert ".ts" in exts
        assert ".json" in exts

    def test_empty_list(self) -> None:
        assert detect_languages_from_paths([]) == set()

    def test_paths_without_extensions(self) -> None:
        exts = detect_languages_from_paths(["Makefile", "LICENSE"])
        assert exts == set()

    def test_lowercase_normalization(self) -> None:
        exts = detect_languages_from_paths(["src/foo.PY"])
        assert ".py" in exts


# ---------------------------------------------------------------------------
# load_rules_frontmatter
# ---------------------------------------------------------------------------


class TestLoadRulesFrontmatter:
    """Test frontmatter parsing and filename-based fallback."""

    def test_frontmatter_inline_paths(self, tmp_path: Path) -> None:
        """Parses inline-list paths from frontmatter."""
        (tmp_path / "python.md").write_text(
            "---\npaths: [**/*.py, **/*.pyi]\n---\nPython rules.\n"
        )
        result = load_rules_frontmatter(tmp_path)
        assert "python.md" in result
        assert "**/*.py" in result["python.md"]

    def test_frontmatter_block_paths(self, tmp_path: Path) -> None:
        """Parses block-list paths from frontmatter."""
        (tmp_path / "ts.md").write_text(
            "---\npaths:\n  - **/*.ts\n  - **/*.tsx\n---\nTS rules.\n"
        )
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


class TestMatchRulesFiles:
    """Test extension-to-rules-file matching."""

    def test_match_by_extension(self, tmp_path: Path) -> None:
        """'.py' extension matches python.md with frontmatter paths [**/*.py]."""
        py_file = tmp_path / "python.md"
        py_file.write_text("Python rules.")
        frontmatter = {"python.md": ["**/*.py"]}

        matched = match_rules_files({".py"}, tmp_path, frontmatter)
        assert py_file in matched

    def test_no_match_for_unrelated_extension(self, tmp_path: Path) -> None:
        """'.rs' does not match python.md."""
        (tmp_path / "python.md").write_text("Python rules.")
        frontmatter = {"python.md": ["**/*.py"]}

        matched = match_rules_files({".rs"}, tmp_path, frontmatter)
        assert matched == []

    def test_filename_fallback_match(self, tmp_path: Path) -> None:
        """python.md with no frontmatter paths falls back — should match .py."""
        py_file = tmp_path / "python.md"
        py_file.write_text("Python rules.")
        # simulate filename-derived patterns
        frontmatter = {"python.md": ["**/*.py", "**/*.pyi"]}

        matched = match_rules_files({".py"}, tmp_path, frontmatter)
        assert py_file in matched

    def test_result_is_sorted(self, tmp_path: Path) -> None:
        """Returned list is sorted."""
        for name in ("z_rules.md", "a_rules.md"):
            (tmp_path / name).write_text("rules")
        frontmatter = {
            "z_rules.md": ["**/*.py"],
            "a_rules.md": ["**/*.py"],
        }
        matched = match_rules_files({".py"}, tmp_path, frontmatter)
        assert matched == sorted(matched)


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
