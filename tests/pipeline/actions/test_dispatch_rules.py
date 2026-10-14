"""Tests for the pipeline-side project rules glue (slice 935)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from squadron.pipeline.actions import dispatch_rules
from squadron.pipeline.actions.dispatch_rules import (
    ProjectRulesContextError,
    build_rule_context,
    dispatch_requires_writes,
    native_conventions_for,
    rule_step_for,
    tracked_files,
)
from squadron.pipeline.steps import StepTypeName
from squadron.pipeline.steps.phase import RULES_STEP_PARAM
from squadron.project_rules.conventions import ConventionsSource
from squadron.project_rules.frontmatter import RuleStep
from squadron.providers.base import ProviderType


@pytest.mark.parametrize(
    ("step_type", "rule_step"),
    [
        (StepTypeName.DESIGN, RuleStep.DESIGN),
        (StepTypeName.TASKS, RuleStep.TASKS),
        (StepTypeName.IMPLEMENT, RuleStep.IMPLEMENT),
        (StepTypeName.DISPATCH, RuleStep.DISPATCH),
    ],
)
def test_step_table(step_type: StepTypeName, rule_step: RuleStep) -> None:
    assert rule_step_for(step_type) is rule_step


def test_unmapped_step_type_raises() -> None:
    with pytest.raises(ProjectRulesContextError, match="'summary'"):
        rule_step_for(StepTypeName.SUMMARY)


@pytest.mark.parametrize(
    ("provider", "native"),
    [
        (ProviderType.SDK, ConventionsSource.CLAUDE_MD),
        (ProviderType.OPENAI_OAUTH, ConventionsSource.AGENTS_MD),
        (ProviderType.OPENAI, None),
    ],
)
def test_native_table(provider: ProviderType, native: ConventionsSource | None) -> None:
    assert native_conventions_for(provider) is native


def test_unmapped_provider_type_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(dispatch_rules._NATIVE_CONVENTIONS, ProviderType.OPENAI)  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ProjectRulesContextError, match="'openai'"):
        native_conventions_for(ProviderType.OPENAI)


def _git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "a.py").write_text("print('a')\n")
    (root / "untracked.py").write_text("print('u')\n")
    subprocess.run(["git", "add", "a.py"], cwd=root, check=True)


def test_implement_gets_tracked_files(tmp_path: Path) -> None:
    _git_repo(tmp_path)
    ctx = build_rule_context(StepTypeName.IMPLEMENT, ProviderType.OPENAI, str(tmp_path))
    assert ctx.step_kind is RuleStep.IMPLEMENT
    assert ctx.file_paths == ["a.py"]
    assert ctx.native is None
    assert ctx.root == tmp_path
    assert ctx.max_chars == 48_000


def test_design_gets_no_file_paths(tmp_path: Path) -> None:
    ctx = build_rule_context(StepTypeName.DESIGN, ProviderType.OPENAI_OAUTH, str(tmp_path))
    assert ctx.file_paths is None
    assert ctx.native is ConventionsSource.AGENTS_MD


def test_git_unavailable_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(dispatch_rules, "run_git", lambda args, *, cwd: None)
    with pytest.raises(ProjectRulesContextError, match="git ls-files could not run"):
        tracked_files(str(tmp_path))


def test_git_refusal_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    refused = subprocess.CompletedProcess(
        ["git", "ls-files"], 128, stdout="", stderr="fatal: not a git repository"
    )
    monkeypatch.setattr(dispatch_rules, "run_git", lambda args, *, cwd: refused)
    with pytest.raises(ProjectRulesContextError, match="exit 128.*not a git repository"):
        tracked_files(str(tmp_path))


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({RULES_STEP_PARAM: StepTypeName.DESIGN}, True),
        ({RULES_STEP_PARAM: StepTypeName.TASKS}, True),
        ({RULES_STEP_PARAM: StepTypeName.IMPLEMENT}, True),
        ({"feedback": "fix the typo"}, True),
        ({}, False),
        ({RULES_STEP_PARAM: StepTypeName.DISPATCH}, False),
    ],
)
def test_dispatch_requires_writes(params: dict[str, object], expected: bool) -> None:
    assert dispatch_requires_writes(params) is expected
