"""Tests for project rule selection (D3, D5, D6) and rendering."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest

from squadron.project_rules.conventions import ConventionsSource
from squadron.project_rules.frontmatter import RuleStep
from squadron.project_rules.render import render_project_rules
from squadron.project_rules.selection import (
    MAX_CHARS_KEY,
    ProjectRulesBudgetError,
    RuleContext,
    select_project_rules,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BIG_BUDGET = 1_000_000


def _ctx(
    root: Path,
    step: RuleStep,
    file_paths: list[str] | None = None,
    *,
    native: ConventionsSource | None = None,
    max_chars: int = _BIG_BUDGET,
) -> RuleContext:
    return RuleContext(
        step_kind=step,
        file_paths=file_paths,
        root=root,
        rules_dir=root / "rules",
        native=native,
        max_chars=max_chars,
    )


def _rule(root: Path, name: str, frontmatter: str = "", body: str = "Rule body.") -> None:
    rules = root / "rules"
    rules.mkdir(exist_ok=True)
    head = f"---\n{frontmatter}\n---\n" if frontmatter else ""
    (rules / name).write_text(f"{head}{body}\n")


def _names(root: Path, ctx: RuleContext) -> list[str]:
    return [rule.name for rule in select_project_rules(ctx).rules]


class TestStepSelection:
    def test_review_template_files_are_skipped(self, tmp_path: Path) -> None:
        _rule(tmp_path, "review.md")
        _rule(tmp_path, "review-code.md")
        _rule(tmp_path, "general.md")
        assert _names(tmp_path, _ctx(tmp_path, RuleStep.DESIGN)) == ["general.md"]

    def test_explicit_steps(self, tmp_path: Path) -> None:
        _rule(tmp_path, "impl.md", "steps: [implement]")
        assert _names(tmp_path, _ctx(tmp_path, RuleStep.IMPLEMENT, [])) == ["impl.md"]
        assert _names(tmp_path, _ctx(tmp_path, RuleStep.DESIGN)) == []

    @pytest.mark.parametrize("step", list(RuleStep))
    def test_default_without_paths_is_every_kind(self, tmp_path: Path, step: RuleStep) -> None:
        _rule(tmp_path, "general.md")
        assert _names(tmp_path, _ctx(tmp_path, step, ["a.py"])) == ["general.md"]

    @pytest.mark.parametrize(
        ("step", "expected"),
        [
            (RuleStep.IMPLEMENT, ["python.md"]),
            (RuleStep.REVIEW, ["python.md"]),
            (RuleStep.DESIGN, []),
            (RuleStep.TASKS, []),
            (RuleStep.DISPATCH, []),
        ],
    )
    def test_default_with_paths_is_implement_and_review(
        self, tmp_path: Path, step: RuleStep, expected: list[str]
    ) -> None:
        _rule(tmp_path, "python.md", 'paths: ["**/*.py"]')
        assert _names(tmp_path, _ctx(tmp_path, step, ["src/a.py"])) == expected

    def test_path_check_skipped_without_file_paths(self, tmp_path: Path) -> None:
        _rule(tmp_path, "python.md", 'paths: ["**/*.py"]\nsteps: [design]')
        assert _names(tmp_path, _ctx(tmp_path, RuleStep.DESIGN, None)) == ["python.md"]

    def test_path_scoped_rule_without_matching_file_is_excluded(self, tmp_path: Path) -> None:
        _rule(tmp_path, "python.md", 'paths: ["**/*.py"]')
        assert _names(tmp_path, _ctx(tmp_path, RuleStep.IMPLEMENT, ["src/lib.rs"])) == []

    def test_no_rules_dir(self, tmp_path: Path) -> None:
        ctx = RuleContext(RuleStep.DESIGN, None, tmp_path, None, None, _BIG_BUDGET)
        assert select_project_rules(ctx).rules == []


class TestConventions:
    def test_native_match_omits_content_keeps_rules(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("Agent conventions.")
        _rule(tmp_path, "general.md")
        ctx = _ctx(tmp_path, RuleStep.DESIGN, native=ConventionsSource.AGENTS_MD)
        rules = select_project_rules(ctx)
        assert rules.native is True
        rendered = render_project_rules(rules)
        assert "Agent conventions." not in rendered
        assert "Rule body." in rendered
        assert rules.chars == len("Rule body.\n")

    def test_no_native_match_injects_content(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("Claude conventions.")
        ctx = _ctx(tmp_path, RuleStep.DESIGN, native=ConventionsSource.AGENTS_MD)
        rules = select_project_rules(ctx)
        assert rules.native is False
        assert "Claude conventions." in render_project_rules(rules)


class TestFailureModes:
    def test_rule_over_budget_is_dropped_with_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        (tmp_path / "AGENTS.md").write_text("x" * 50)
        _rule(tmp_path, "a.md", body="small")
        _rule(tmp_path, "b.md", body="y" * 100)
        _rule(tmp_path, "c.md", body="tiny")
        with caplog.at_level(logging.WARNING):
            rules = select_project_rules(_ctx(tmp_path, RuleStep.DESIGN, max_chars=70))
        assert [rule.name for rule in rules.rules] == ["a.md", "c.md"]
        assert rules.dropped == ["b.md"]
        assert "b.md" in caplog.text
        assert MAX_CHARS_KEY in caplog.text

    def test_conventions_over_budget_raises_naming_the_key(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("x" * 100)
        with pytest.raises(ProjectRulesBudgetError, match=r"AGENTS\.md.*100.*project_rules\.max_chars"):
            select_project_rules(_ctx(tmp_path, RuleStep.DESIGN, max_chars=50))

    def test_unreadable_rule_is_dropped_with_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        _rule(tmp_path, "good.md")
        (tmp_path / "rules" / "broken.md").symlink_to(tmp_path / "missing.md")
        with caplog.at_level(logging.WARNING):
            rules = select_project_rules(_ctx(tmp_path, RuleStep.DESIGN))
        assert [rule.name for rule in rules.rules] == ["good.md"]
        assert rules.dropped == ["broken.md"]
        assert "broken.md" in caplog.text


class TestRecordAndRender:
    def test_record_shape(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("Agent conventions.")
        (tmp_path / "CLAUDE.md").write_text("Claude conventions.")
        _rule(tmp_path, "a.md", body="Alpha.")
        record = select_project_rules(_ctx(tmp_path, RuleStep.DESIGN)).to_record()
        assert record == {
            "conventions": "AGENTS.md",
            "native": False,
            "skipped": ["CLAUDE.md"],
            "rules": ["a.md"],
            "dropped": [],
            "chars": len("Agent conventions.") + len("Alpha.\n"),
        }

    def test_record_with_no_conventions(self, tmp_path: Path) -> None:
        record = select_project_rules(_ctx(tmp_path, RuleStep.DESIGN)).to_record()
        assert record["conventions"] == "none"
        assert record["chars"] == 0

    def test_render_heading_order_and_demotion(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("# Conventions\nC.")
        _rule(tmp_path, "a.md", body="## Alpha\nA.")
        _rule(tmp_path, "b.md", body="Beta.")
        rendered = render_project_rules(select_project_rules(_ctx(tmp_path, RuleStep.DESIGN)))
        assert rendered.startswith("## Project Rules\n\n")
        assert "### Conventions" in rendered
        assert "#### Alpha" in rendered
        assert rendered.index("C.") < rendered.index("A.") < rendered.index("Beta.")

    def test_render_empty_when_nothing_selected(self, tmp_path: Path) -> None:
        assert render_project_rules(select_project_rules(_ctx(tmp_path, RuleStep.DESIGN))) == ""


class TestRealFiles:
    """squadron's own root and .claude/rules: the format selection reads in production."""

    @staticmethod
    def _select(step: RuleStep, file_paths: list[str] | None) -> dict[str, object]:
        ctx = RuleContext(
            step_kind=step,
            file_paths=file_paths,
            root=_REPO_ROOT,
            rules_dir=_REPO_ROOT / ".claude" / "rules",
            native=None,
            max_chars=_BIG_BUDGET,
        )
        return select_project_rules(ctx).to_record()

    def test_implement_with_tracked_files(self) -> None:
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=_REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.splitlines()
        record = self._select(RuleStep.IMPLEMENT, tracked)
        assert record["conventions"] == "AGENTS.md"
        assert record["skipped"] == ["CLAUDE.md"]
        # sql.md matches through its **/tests/**/*.py and **/conftest.py globs.
        assert record["rules"] == ["bug-fixes.md", "python.md", "shell.md", "sql.md", "testing.md"]

    @pytest.mark.parametrize("step", [RuleStep.DESIGN, RuleStep.TASKS])
    def test_design_and_tasks(self, step: RuleStep) -> None:
        record = self._select(step, None)
        assert record["conventions"] == "AGENTS.md"
        assert record["rules"] == ["bug-fixes.md"]
