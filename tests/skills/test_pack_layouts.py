"""Tests for the per-target skill-pack layout table (slice 928, D3, D6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.skills.models import PackEntry, SkillSourceError
from squadron.skills.pack_layouts import PACK_LAYOUTS, validate_agents_source
from squadron.skills.targets import CommandTarget

PREFIX_ENTRY = PackEntry(source="bundled", prefix="demo")
DISPATCH_ENTRY = PackEntry(source="bundled", dispatch_file="hello")


def test_pack_layouts_covers_every_target() -> None:
    assert set(PACK_LAYOUTS) == set(CommandTarget)


# ---------------------------------------------------------------------------
# Claude installed_path
# ---------------------------------------------------------------------------


def test_claude_prefix_missing_dir_is_not_installed(tmp_path: Path) -> None:
    assert PACK_LAYOUTS[CommandTarget.CLAUDE].installed_path(PREFIX_ENTRY, tmp_path) is None


def test_claude_prefix_empty_dir_is_not_installed(tmp_path: Path) -> None:
    (tmp_path / "demo").mkdir()
    assert PACK_LAYOUTS[CommandTarget.CLAUDE].installed_path(PREFIX_ENTRY, tmp_path) is None


def test_claude_prefix_non_empty_dir_is_installed(tmp_path: Path) -> None:
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "a.md").write_text("x")
    path = PACK_LAYOUTS[CommandTarget.CLAUDE].installed_path(PREFIX_ENTRY, tmp_path)
    assert path == tmp_path / "demo"


@pytest.mark.parametrize("present", [False, True])
def test_claude_dispatch_file(tmp_path: Path, present: bool) -> None:
    if present:
        (tmp_path / "sq").mkdir()
        (tmp_path / "sq" / "hello.md").write_text("x")
    path = PACK_LAYOUTS[CommandTarget.CLAUDE].installed_path(DISPATCH_ENTRY, tmp_path)
    assert path == (tmp_path / "sq" / "hello.md" if present else None)


# ---------------------------------------------------------------------------
# Agents install and D3 validation
# ---------------------------------------------------------------------------

AGENTS = PACK_LAYOUTS[CommandTarget.AGENTS]


def _skill(source: Path, dir_name: str, *, name: str | None = None, description: str = "d") -> Path:
    skill_dir = source / "agents" / dir_name
    skill_dir.mkdir(parents=True)
    declared = dir_name if name is None else name
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {declared}\ndescription: {description}\n---\nbody\n"
    )
    return skill_dir


def _install_error(source: Path, root: Path, entry: PackEntry = PREFIX_ENTRY) -> str:
    with pytest.raises(SkillSourceError) as exc:
        AGENTS.install("demo", entry, source, root)
    assert not root.exists() or not any(root.iterdir()), "nothing may be written on failure"
    return str(exc.value)


def test_no_agents_dir_refuses_with_the_d2_message(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "hello.md").write_text("use $ARGUMENTS")

    message = _install_error(source, tmp_path / "root")

    assert message == (
        f"Pack 'demo' has no agents/ directory at {source}; it ships no Codex content. "
        "Install it for Claude with --ide claude."
    )


def test_empty_agents_dir_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "src" / "agents").mkdir(parents=True)
    assert "holds no skill directories" in _install_error(tmp_path / "src", tmp_path / "root")


def test_prefix_pack_rejects_a_misnamed_skill(tmp_path: Path) -> None:
    _skill(tmp_path / "src", "hello")
    assert "agents/hello must be named demo-<name>" in _install_error(
        tmp_path / "src", tmp_path / "root"
    )


def test_prefix_pack_rejects_uppercase(tmp_path: Path) -> None:
    _skill(tmp_path / "src", "demo-Hello")
    assert "agents/demo-Hello must be named" in _install_error(tmp_path / "src", tmp_path / "root")


def test_dispatch_pack_requires_exactly_its_skill(tmp_path: Path) -> None:
    _skill(tmp_path / "src", "hello")
    message = _install_error(tmp_path / "src", tmp_path / "root", DISPATCH_ENTRY)
    assert "agents/sq-hello/ is missing" in message
    assert "agents/hello is not allowed" in message


def test_mismatched_name_frontmatter(tmp_path: Path) -> None:
    _skill(tmp_path / "src", "demo-a", name="other")
    assert "declares name 'other'; it must be 'demo-a'" in _install_error(
        tmp_path / "src", tmp_path / "root"
    )


def test_missing_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "src" / "agents" / "demo-a"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("no fence here")
    assert "has no YAML frontmatter" in _install_error(tmp_path / "src", tmp_path / "root")


def test_broken_yaml_is_reported_as_invalid_not_missing(tmp_path: Path) -> None:
    skill_dir = tmp_path / "src" / "agents" / "demo-a"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: [unclosed\n---\n")
    message = _install_error(tmp_path / "src", tmp_path / "root")
    assert "has invalid YAML frontmatter" in message
    assert "has no YAML frontmatter" not in message


def test_non_mapping_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "src" / "agents" / "demo-a"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\n- just\n- a list\n---\n")
    assert "frontmatter is not a mapping" in _install_error(tmp_path / "src", tmp_path / "root")


def test_missing_skill_md(tmp_path: Path) -> None:
    (tmp_path / "src" / "agents" / "demo-a").mkdir(parents=True)
    assert "agents/demo-a/SKILL.md is missing" in _install_error(tmp_path / "src", tmp_path / "root")


def test_empty_description(tmp_path: Path) -> None:
    _skill(tmp_path / "src", "demo-a", description="''")
    assert "has no description" in _install_error(tmp_path / "src", tmp_path / "root")


def test_every_violation_is_reported_together(tmp_path: Path) -> None:
    _skill(tmp_path / "src", "hello")
    _skill(tmp_path / "src", "demo-b", name="wrong", description="''")
    message = _install_error(tmp_path / "src", tmp_path / "root")
    assert "agents/hello must be named demo-<name>" in message
    assert "declares name 'wrong'" in message
    assert "agents/demo-b/SKILL.md has no description" in message


def test_leading_html_comment_is_tolerated(tmp_path: Path) -> None:
    skill_dir = tmp_path / "src" / "agents" / "demo-a"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "<!-- attribution -->\n---\nname: demo-a\ndescription: d\n---\n"
    )
    result = AGENTS.install("demo", PREFIX_ENTRY, tmp_path / "src", tmp_path / "root")
    assert result.files_written == ["demo-a/SKILL.md"]


def test_successful_install_copies_nested_files(tmp_path: Path) -> None:
    skill_dir = _skill(tmp_path / "src", "demo-a")
    (skill_dir / "agents").mkdir()
    (skill_dir / "agents" / "openai.yaml").write_text("policy: {}")
    _skill(tmp_path / "src", "demo-b")
    root = tmp_path / "root"

    result = AGENTS.install("demo", PREFIX_ENTRY, tmp_path / "src", root)

    assert result.destination == root
    assert result.files_written == ["demo-a/SKILL.md", "demo-a/agents/openai.yaml", "demo-b/SKILL.md"]
    assert (root / "demo-a" / "agents" / "openai.yaml").read_text() == "policy: {}"


def test_dispatch_pack_installs_its_skill(tmp_path: Path) -> None:
    _skill(tmp_path / "src", "sq-hello")
    result = AGENTS.install("demo", DISPATCH_ENTRY, tmp_path / "src", tmp_path / "root")
    assert result.files_written == ["sq-hello/SKILL.md"]


# ---------------------------------------------------------------------------
# Agents installed_path
# ---------------------------------------------------------------------------


def test_agents_prefix_installed_path(tmp_path: Path) -> None:
    assert AGENTS.installed_path(PREFIX_ENTRY, tmp_path) is None
    (tmp_path / "demo-a").mkdir()
    assert AGENTS.installed_path(PREFIX_ENTRY, tmp_path) is None, (
        "a directory without SKILL.md is not a skill"
    )
    (tmp_path / "demo-a" / "SKILL.md").write_text("x")
    assert AGENTS.installed_path(PREFIX_ENTRY, tmp_path) == tmp_path / "demo-a" / "SKILL.md"


@pytest.mark.parametrize("present", [False, True])
def test_agents_dispatch_installed_path(tmp_path: Path, present: bool) -> None:
    if present:
        (tmp_path / "sq-hello").mkdir()
        (tmp_path / "sq-hello" / "SKILL.md").write_text("x")
    path = AGENTS.installed_path(DISPATCH_ENTRY, tmp_path)
    assert path == (tmp_path / "sq-hello" / "SKILL.md" if present else None)


def test_bundled_analysis_pack_passes_validation() -> None:
    from squadron.skills.resolver import resolve_source

    entry = PackEntry(source="bundled", prefix="analysis")
    validate_agents_source("analysis", entry, resolve_source(entry, "analysis"))
