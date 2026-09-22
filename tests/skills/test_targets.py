"""Tests for the command install target vocabulary and delivery table."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.skills.targets import (
    DELIVERIES,
    CommandTarget,
    normalize_target,
    receipt_name,
    write_flat_markdown,
    write_skill_dirs,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("claude", CommandTarget.CLAUDE),
        ("CLAUDE", CommandTarget.CLAUDE),
        ("  claude  ", CommandTarget.CLAUDE),
        ("agents", CommandTarget.AGENTS),
        ("Agents", CommandTarget.AGENTS),
        ("codex", CommandTarget.AGENTS),
        ("CODEX", CommandTarget.AGENTS),
        ("\tcodex\n", CommandTarget.AGENTS),
        ("openai", CommandTarget.AGENTS),
        ("OpenAI", CommandTarget.AGENTS),
    ],
)
def test_normalize_target_accepts_members_and_aliases(raw: str, expected: CommandTarget) -> None:
    assert normalize_target(raw) is expected


@pytest.mark.parametrize("raw", ["copilot", "cursor", "", "   ", "claude-code", "gpt"])
def test_normalize_target_rejects_everything_else(raw: str) -> None:
    with pytest.raises(ValueError) as exc:
        normalize_target(raw)
    message = str(exc.value)
    for spelling in ("claude", "agents", "codex", "openai"):
        assert spelling in message


def test_deliveries_covers_every_member() -> None:
    assert set(DELIVERIES) == set(CommandTarget)


def test_deliveries_entries_are_distinct() -> None:
    claude = DELIVERIES[CommandTarget.CLAUDE]
    agents = DELIVERIES[CommandTarget.AGENTS]
    assert claude.machine_root != agents.machine_root
    assert claude.local_root != agents.local_root
    assert claude.check_name != agents.check_name
    assert claude.receipt_base != agents.receipt_base
    assert claude.layout is not agents.layout


def test_receipt_names_are_the_four_expected() -> None:
    names = {receipt_name(target, local=local) for target in CommandTarget for local in (False, True)}
    assert names == {
        "squadron-commands",
        "squadron-commands-local",
        "squadron-commands-agents",
        "squadron-commands-agents-local",
    }


def test_claude_machine_receipt_name_is_unchanged() -> None:
    # Every receipt written since #65 carries this name; changing it orphans them.
    assert receipt_name(CommandTarget.CLAUDE, local=False) == "squadron-commands"


@pytest.mark.parametrize("target", list(CommandTarget))
def test_machine_root_resolves_under_patched_home(
    target: CommandTarget, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    resolved = DELIVERIES[target].resolve_root(local=False)
    assert resolved.is_relative_to(tmp_path)


@pytest.mark.parametrize("target", list(CommandTarget))
def test_local_root_resolves_under_cwd(
    target: CommandTarget, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    resolved = DELIVERIES[target].resolve_root(local=True)
    assert resolved.is_relative_to(tmp_path)


def test_write_flat_markdown_copies_into_a_named_subdirectory(tmp_path: Path) -> None:
    source = tmp_path / "bundle" / "sq"
    source.mkdir(parents=True)
    (source / "review.md").write_text("review body")
    (source / "run.md").write_text("run body")
    (source / "notes.txt").write_text("not a command")
    destination = tmp_path / "dest"

    written = write_flat_markdown(source, destination)

    assert written == ["sq/review.md", "sq/run.md"]
    assert (destination / "sq" / "review.md").read_text() == "review body"
    assert not (destination / "sq" / "notes.txt").exists()


def test_write_skill_dirs_copies_nested_files(tmp_path: Path) -> None:
    source = tmp_path / "bundle" / "agents"
    skill = source / "analysis-understand"
    (skill / "agents").mkdir(parents=True)
    (skill / "SKILL.md").write_text("skill body")
    (skill / "agents" / "openai.yaml").write_text("key: value")
    plain = source / "sq-auth"
    plain.mkdir()
    (plain / "SKILL.md").write_text("auth body")
    destination = tmp_path / "dest"

    written = write_skill_dirs(source, destination)

    assert written == [
        "analysis-understand/SKILL.md",
        "analysis-understand/agents/openai.yaml",
        "sq-auth/SKILL.md",
    ]
    assert (destination / "analysis-understand" / "agents" / "openai.yaml").read_text() == (
        "key: value"
    )


@pytest.mark.parametrize("writer", [write_flat_markdown, write_skill_dirs])
def test_layout_writers_create_missing_parents(writer: object, tmp_path: Path) -> None:
    source = tmp_path / "bundle" / "sq"
    source.mkdir(parents=True)
    (source / "auth.md").write_text("body")
    (source / "nested").mkdir()
    (source / "nested" / "SKILL.md").write_text("body")
    destination = tmp_path / "deeply" / "nested" / "dest"

    assert callable(writer)
    writer(source, destination)

    assert destination.is_dir()
