"""``commands/sq/run.md`` tells the harness how to run every action a fix step renders (slice 423).

The prompt-only harness is a Claude Code session reading ``run.md``. An action type with
no section there would be skipped, so the fix step's actions are checked against it.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock

from squadron.pipeline.fix_prompt_args import REPORT_PATH_PLACEHOLDER
from squadron.pipeline.models import StepConfig
from squadron.pipeline.prompt_renderer import render_step_instructions
from squadron.pipeline.resolver import ResolvedModel

RUN_MD = Path(__file__).resolve().parents[2] / "commands" / "sq" / "run.md"
FIX_CONTEXT = "fix-context"


def _fix_action_types(repo: Path) -> list[str]:
    resolver = MagicMock()
    resolver.resolve.return_value = ("resolved-model", None)
    resolver.resolve_full.return_value = ResolvedModel("resolved-model", None)
    step = StepConfig(
        step_type="fix",
        name="fix-0",
        config={"issue": "301", "model": "sonnet", "issue-file": "", "commit-to": "current"},
    )
    rendered = render_step_instructions(
        step,
        step_index=0,
        total_steps=1,
        params={},
        resolver=resolver,
        run_id="run-test",
        cwd=str(repo),
    )
    return [action.action_type for action in rendered.actions]


def _section(text: str, heading: str) -> str | None:
    """The body under ``### heading`` up to the next heading, or None when it is absent."""
    match = re.search(rf"^### {re.escape(heading)}\n(.*?)(?=^#{{1,3}} |\Z)", text, re.M | re.S)
    return match.group(1) if match else None


def run_md_problems(text: str, action_types: list[str]) -> list[str]:
    """What ``run.md`` lacks for ``action_types``; empty when it covers them."""
    problems = [
        f"no '### {action_type}' section"
        for action_type in action_types
        if _section(text, action_type) is None
    ]
    example = re.search(r'"action_type": "([^"]*)"', text)
    if example is None or FIX_CONTEXT not in example.group(1).split("|"):
        problems.append(f"the action_type list does not name {FIX_CONTEXT}")
    commit = _section(text, "commit")
    if commit is None or REPORT_PATH_PLACEHOLDER not in commit:
        problems.append(f"the commit section does not mention {REPORT_PATH_PLACEHOLDER}")
    return problems


def test_run_md_covers_every_action_the_fix_step_renders(temp_git_repo: Path) -> None:
    action_types = _fix_action_types(temp_git_repo)
    assert FIX_CONTEXT in action_types
    assert run_md_problems(RUN_MD.read_text(encoding="utf-8"), action_types) == []


def test_removing_the_fix_context_heading_fails_the_check(temp_git_repo: Path, tmp_path: Path) -> None:
    copy = tmp_path / "run.md"
    copy.write_text(
        RUN_MD.read_text(encoding="utf-8").replace(f"### {FIX_CONTEXT}\n", "### something-else\n"),
        encoding="utf-8",
    )
    problems = run_md_problems(copy.read_text(encoding="utf-8"), _fix_action_types(temp_git_repo))
    assert problems == [f"no '### {FIX_CONTEXT}' section"]
