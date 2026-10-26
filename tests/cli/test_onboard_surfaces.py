"""The /sq:onboard command file and the sq-onboard Codex skill carry every step (slice 440 D10)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from squadron.onboard.steps import OnboardStep

COMMANDS = Path(__file__).resolve().parents[2] / "commands"
CLAUDE_COMMAND = COMMANDS / "sq" / "onboard.md"
CODEX_SKILL = COMMANDS / "agents" / "sq-onboard" / "SKILL.md"
SURFACE_FILES = [CLAUDE_COMMAND, CODEX_SKILL]

STEP_HEADING = re.compile(r"^### Step: (\S+)\s*$", re.MULTILINE)
NO_PROGRESS_HEADING = "## No-progress stop"


@pytest.mark.parametrize("surface", SURFACE_FILES, ids=lambda path: path.parent.name)
def test_step_headings_are_exactly_the_onboard_steps(surface: Path) -> None:
    headings = STEP_HEADING.findall(surface.read_text(encoding="utf-8"))
    assert sorted(headings) == sorted(step.value for step in OnboardStep)


@pytest.mark.parametrize("surface", SURFACE_FILES, ids=lambda path: path.parent.name)
def test_no_progress_stop_section_is_not_empty(surface: Path) -> None:
    text = surface.read_text(encoding="utf-8")
    assert text.count(NO_PROGRESS_HEADING) == 1
    body = text.split(NO_PROGRESS_HEADING, 1)[1]
    next_heading = re.search(r"^#{1,6} ", body, re.MULTILINE)
    section = body[: next_heading.start()] if next_heading else body
    assert section.strip()


def test_codex_skill_registers_with_the_agents_ide() -> None:
    assert "--ide agents" in CODEX_SKILL.read_text(encoding="utf-8")
