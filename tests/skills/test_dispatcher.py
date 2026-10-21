from pathlib import Path

from squadron.skills.dispatcher import dispatcher_skills

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_lowercase_prefix_leading_whitespace_and_mixed_separators() -> None:
    text = "intro\n   valid skills: `alpha`, `beta` and `gamma`\nmore"

    assert dispatcher_skills(text) == {"alpha", "beta", "gamma"}


def test_no_valid_skills_line_returns_none() -> None:
    assert dispatcher_skills("Run an analysis skill.\n\nNo list here.") is None


def test_real_claude_dispatcher_lists_tech_debt_audit() -> None:
    text = (REPO_ROOT / "commands" / "sq" / "analysis.md").read_text(encoding="utf-8")

    skills = dispatcher_skills(text)

    assert skills is not None
    assert "tech-debt-audit" in skills
