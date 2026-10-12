"""Tests for rule-file frontmatter parsing (``paths`` and ``steps``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.project_rules.frontmatter import (
    RuleFrontmatter,
    RuleStep,
    load_rules_frontmatter,
    parse_rule_frontmatter,
)

#: squadron's own rules directory: the real format this parser consumes.
_PROJECT_RULES_DIR = Path(__file__).resolve().parents[2] / ".claude" / "rules"


class TestParseSteps:
    def test_inline_steps(self) -> None:
        fm = parse_rule_frontmatter("---\nsteps: [implement, review]\n---\nBody\n", "a.md")
        assert fm.steps == frozenset({RuleStep.IMPLEMENT, RuleStep.REVIEW})

    def test_block_steps_varying_indent_and_trailing_space(self) -> None:
        content = "---\nsteps:  \n  - design\n    - tasks   \n---\nBody\n"
        fm = parse_rule_frontmatter(content, "a.md")
        assert fm.steps == frozenset({RuleStep.DESIGN, RuleStep.TASKS})

    def test_scalar_steps(self) -> None:
        fm = parse_rule_frontmatter("---\nsteps: implement\n---\nBody\n", "a.md")
        assert fm.steps == frozenset({RuleStep.IMPLEMENT})

    def test_steps_with_paths(self) -> None:
        content = '---\ndescription: x\npaths:\n - "**/*.py"\nsteps: [implement]\n---\nBody\n'
        fm = parse_rule_frontmatter(content, "a.md")
        assert fm == RuleFrontmatter(paths=["**/*.py"], steps=frozenset({RuleStep.IMPLEMENT}))

    def test_no_frontmatter(self) -> None:
        assert parse_rule_frontmatter("### Rules\n", "a.md") == RuleFrontmatter(None, None)

    def test_paths_only_leaves_steps_none(self) -> None:
        fm = parse_rule_frontmatter("---\npaths: [**/*.py]\n---\nBody\n", "a.md")
        assert fm.paths == ["**/*.py"]
        assert fm.steps is None

    def test_unknown_value_names_file_and_value(self) -> None:
        with pytest.raises(ValueError, match=r"typo\.md.*'implemnt'"):
            parse_rule_frontmatter("---\nsteps: [implemnt]\n---\nBody\n", "typo.md")

    def test_load_propagates_unknown_value(self, tmp_path: Path) -> None:
        (tmp_path / "bad.md").write_text("---\nsteps: [nope]\n---\nBody\n")
        with pytest.raises(ValueError, match=r"bad\.md"):
            load_rules_frontmatter(tmp_path)


class TestRealRules:
    def test_every_project_rule_file_parses(self) -> None:
        result = load_rules_frontmatter(_PROJECT_RULES_DIR)
        names = {p.name for p in _PROJECT_RULES_DIR.glob("*.md")}
        assert set(result) == names
        assert result["python.md"].paths is not None
        assert "**/*.py" in result["python.md"].paths
        assert result["bug-fixes.md"] == RuleFrontmatter(paths=None, steps=None)
