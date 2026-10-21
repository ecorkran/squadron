"""The analysis dispatchers must list exactly the skills the pack ships."""

from pathlib import Path

from squadron.skills.dispatcher import dispatcher_skills

COMMANDS = Path(__file__).resolve().parents[2] / "commands"
ANALYSIS_PACK = COMMANDS / "analysis"
CLAUDE_DISPATCHER = COMMANDS / "sq" / "analysis.md"
CODEX_DISPATCHER = COMMANDS / "agents" / "sq-analysis" / "SKILL.md"
CODEX_SKILL_PREFIX = "analysis-"


def _declared_skills(dispatcher: Path) -> set[str]:
    skills = dispatcher_skills(dispatcher.read_text(encoding="utf-8"))
    assert skills is not None, f"{dispatcher} has no 'Valid skills:' line"
    return skills


def test_claude_dispatcher_lists_every_pack_skill() -> None:
    shipped = {path.stem for path in ANALYSIS_PACK.glob("*.md")}

    assert _declared_skills(CLAUDE_DISPATCHER) == shipped


def test_codex_dispatcher_lists_every_pack_skill() -> None:
    shipped = {
        path.parent.name.removeprefix(CODEX_SKILL_PREFIX)
        for path in (ANALYSIS_PACK / "agents").glob("*/SKILL.md")
    }

    assert _declared_skills(CODEX_DISPATCHER) == shipped
