"""Tests for install-commands and uninstall-commands CLI commands."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands import install as install_module
from squadron.cli.commands.install import _get_commands_source
from squadron.skills.targets import DELIVERIES, CommandTarget

runner = CliRunner()

EXPECTED_FILES = {
    "analysis.md",
    "auth.md",
    "list.md",
    "pr.md",
    "review.md",
    "run.md",
    "shutdown.md",
    "spawn.md",
    "summary.md",
    "task.md",
}


def _receipts_dir(target: Path) -> Path:
    """Receipts location for a test, always under the test's own tmp_path.

    Never the real ``~/.config/squadron/receipts``: these tests install and uninstall
    for real, and a receipt written to the user's actual directory would make the next
    real ``sq uninstall-commands`` delete files this test invented.
    """
    return target.parent / "receipts"


def _install(runner_: CliRunner, target: Path) -> object:
    return runner_.invoke(
        app,
        [
            "install-commands",
            "--target",
            str(target),
            "--receipts-dir",
            str(_receipts_dir(target)),
        ],
    )


def _uninstall(runner_: CliRunner, target: Path) -> object:
    return runner_.invoke(
        app,
        [
            "uninstall-commands",
            "--target",
            str(target),
            "--receipts-dir",
            str(_receipts_dir(target)),
        ],
    )


def test_install_copies_files(tmp_path: Path) -> None:
    """Install copies all 10 command files to the target directory."""
    result = _install(runner, tmp_path)
    assert result.exit_code == 0  # type: ignore[attr-defined]

    sq_dir = tmp_path / "sq"
    assert sq_dir.is_dir()
    installed = {f.name for f in sq_dir.iterdir()}
    assert installed == EXPECTED_FILES


def test_install_creates_directories(tmp_path: Path) -> None:
    """Install creates target and subdirectories if they don't exist."""
    deep_target = tmp_path / "a" / "b" / "c"
    result = _install(runner, deep_target)
    assert result.exit_code == 0  # type: ignore[attr-defined]
    assert (deep_target / "sq").is_dir()
    assert len(list((deep_target / "sq").glob("*.md"))) == 10


def test_install_overwrites_existing(tmp_path: Path) -> None:
    """Install overwrites existing files."""
    sq_dir = tmp_path / "sq"
    sq_dir.mkdir(parents=True)
    (sq_dir / "spawn.md").write_text("old content")

    result = _install(runner, tmp_path)
    assert result.exit_code == 0  # type: ignore[attr-defined]

    content = (sq_dir / "spawn.md").read_text()
    assert content != "old content"
    assert "sq spawn" in content


def test_uninstall_removes_sq_directory(tmp_path: Path) -> None:
    """Uninstall removes the sq/ directory and its contents."""
    # First install
    _install(runner, tmp_path)
    assert (tmp_path / "sq").is_dir()

    # Then uninstall
    result = _uninstall(runner, tmp_path)
    assert result.exit_code == 0  # type: ignore[attr-defined]
    assert not (tmp_path / "sq").exists()


def test_uninstall_preserves_other_files(tmp_path: Path) -> None:
    """Uninstall only removes sq/, not other files in the target."""
    # Install commands
    _install(runner, tmp_path)

    # Add a non-sq file
    (tmp_path / "other-command.md").write_text("keep me")

    # Uninstall
    result = _uninstall(runner, tmp_path)
    assert result.exit_code == 0  # type: ignore[attr-defined]
    assert not (tmp_path / "sq").exists()
    assert (tmp_path / "other-command.md").read_text() == "keep me"


def test_uninstall_graceful_when_nothing_installed(tmp_path: Path) -> None:
    """Uninstall reports gracefully when nothing is installed."""
    result = _uninstall(runner, tmp_path)
    assert result.exit_code == 0  # type: ignore[attr-defined]
    assert "Nothing to remove" in result.output  # type: ignore[attr-defined]


def test_target_flag_overrides_default(tmp_path: Path) -> None:
    """--target flag directs installation to a custom path."""
    custom = tmp_path / "custom-location"
    result = _install(runner, custom)
    assert result.exit_code == 0  # type: ignore[attr-defined]
    assert (custom / "sq").is_dir()
    assert len(list((custom / "sq").glob("*.md"))) == 10


def test_get_commands_source_returns_valid_dir() -> None:
    """_get_commands_source returns a directory with sq/ subdirectory."""
    source = _get_commands_source()
    assert source.is_dir()
    assert (source / "sq").is_dir()
    assert len(list((source / "sq").glob("*.md"))) == 10


# ---------------------------------------------------------------------------
# T14: Source file verification
# ---------------------------------------------------------------------------

EXPECTED_COMMANDS = {
    "analysis.md": "/sq:analysis",
    "spawn.md": "sq spawn",
    "task.md": "sq task",
    "list.md": "sq list",
    "shutdown.md": "sq shutdown",
    "review.md": "sq review",
    "auth.md": "sq auth",
    "run.md": "/sq:run",
    "summary.md": "sq _summary-instructions",
    "pr.md": "sq pr",
}


def test_all_command_files_exist_in_source() -> None:
    """All 10 expected command files exist in commands/sq/."""
    source = _get_commands_source()
    sq_dir = source / "sq"
    for filename in EXPECTED_COMMANDS:
        assert (sq_dir / filename).is_file(), f"Missing: {filename}"


def test_command_files_are_nonempty() -> None:
    """Each command file is non-empty."""
    source = _get_commands_source()
    sq_dir = source / "sq"
    for filename in EXPECTED_COMMANDS:
        content = (sq_dir / filename).read_text()
        assert len(content.strip()) > 0, f"Empty: {filename}"


def test_command_files_reference_correct_subcommand() -> None:
    """Each command file references its expected sq subcommand."""
    source = _get_commands_source()
    sq_dir = source / "sq"
    for filename, expected_cmd in EXPECTED_COMMANDS.items():
        content = (sq_dir / filename).read_text()
        assert expected_cmd in content, f"{filename} missing reference to '{expected_cmd}'"


# ---------------------------------------------------------------------------
# Slice 918 Part 3: receipt-based install/uninstall (#65 finding 1)
# ---------------------------------------------------------------------------
#
# The bug these cover: install unlinked every *.md it did not recognize from any
# subdirectory it touched, and uninstall rmtree'd only sq/. Both mistakes come from the
# same missing fact — nothing recorded which files squadron had written, so the code
# inferred ownership from presence in a directory it shares with the user.
#
# The old suite never exercised a non-sq subdirectory, which is why the bug shipped
# despite the suite being green. The bundle ships analysis/ as well as sq/.


def _receipt_path(target: Path) -> Path:
    return _receipts_dir(target) / "squadron-commands.toml"


def test_install_writes_a_receipt_naming_every_file(tmp_path: Path) -> None:
    result = _install(runner, tmp_path)
    assert result.exit_code == 0  # type: ignore[attr-defined]

    import tomllib

    with open(_receipt_path(tmp_path), "rb") as fh:
        receipt = tomllib.load(fh)

    written = set(receipt["files_written"])
    on_disk = {str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*.md") if path.is_file()}
    assert written == on_disk
    # Spans every subdirectory, not just sq/ — the receipt is what makes uninstall
    # symmetric with install.
    assert any(name.startswith("analysis/") for name in written)
    assert any(name.startswith("sq/") for name in written)


def test_user_file_in_shared_subdirectory_survives_install(tmp_path: Path) -> None:
    """Issue #65 finding 1, stated directly.

    ``analysis/`` is squadron's *and* the user's. A file there that squadron never
    wrote is not stale — it is someone else's work.
    """
    analysis = tmp_path / "analysis"
    analysis.mkdir(parents=True)
    mine = analysis / "mine.md"
    mine.write_text("my own command")

    result = _install(runner, tmp_path)
    assert result.exit_code == 0  # type: ignore[attr-defined]

    assert mine.exists(), "install deleted a user file it never wrote"
    assert mine.read_text() == "my own command"


def test_user_file_in_shared_subdirectory_survives_uninstall(tmp_path: Path) -> None:
    _install(runner, tmp_path)
    mine = tmp_path / "analysis" / "mine.md"
    mine.write_text("my own command")

    result = _uninstall(runner, tmp_path)
    assert result.exit_code == 0  # type: ignore[attr-defined]

    assert mine.read_text() == "my own command"
    # The directory stays because it is not empty — never rmtree'd out from under a
    # file squadron does not own.
    assert mine.parent.is_dir()


def test_uninstall_removes_every_subdirectory_squadron_installed(tmp_path: Path) -> None:
    """The old uninstall rmtree'd sq/ alone, orphaning analysis/ forever."""
    _install(runner, tmp_path)
    assert (tmp_path / "analysis").is_dir()
    assert (tmp_path / "sq").is_dir()

    result = _uninstall(runner, tmp_path)
    assert result.exit_code == 0  # type: ignore[attr-defined]

    assert not (tmp_path / "sq").exists()
    assert not (tmp_path / "analysis").exists()
    assert not _receipt_path(tmp_path).exists(), "receipt outlived the uninstall"


def test_squadron_files_are_refreshed_on_reinstall(tmp_path: Path) -> None:
    _install(runner, tmp_path)
    stale = tmp_path / "sq" / "spawn.md"
    stale.write_text("edited by hand")

    result = _install(runner, tmp_path)
    assert result.exit_code == 0  # type: ignore[attr-defined]

    assert stale.read_text() != "edited by hand"


def test_two_consecutive_installs_are_idempotent(tmp_path: Path) -> None:
    _install(runner, tmp_path)
    first = {str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*.md")}

    result = _install(runner, tmp_path)
    assert result.exit_code == 0  # type: ignore[attr-defined]

    second = {str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*.md")}
    assert first == second
    # Nothing was stale, so nothing is reported removed.
    assert "stale" not in result.output  # type: ignore[attr-defined]


def test_stale_squadron_file_is_removed_and_reported(tmp_path: Path) -> None:
    """A file the previous receipt names and this bundle no longer ships.

    This is the one deletion install is still entitled to make, and it stays visible in
    the output — the fix narrows what may be deleted, it does not stop reporting it.
    """
    _install(runner, tmp_path)
    retired = tmp_path / "sq" / "retired.md"
    retired.write_text("shipped by an older squadron")

    import tomllib

    import tomli_w

    with open(_receipt_path(tmp_path), "rb") as fh:
        receipt = tomllib.load(fh)
    receipt["files_written"].append("sq/retired.md")
    with open(_receipt_path(tmp_path), "wb") as fh:
        tomli_w.dump(receipt, fh)

    result = _install(runner, tmp_path)
    assert result.exit_code == 0  # type: ignore[attr-defined]

    assert not retired.exists()
    assert "retired.md" in result.output  # type: ignore[attr-defined]


def test_receipt_entry_for_an_already_deleted_file_is_not_an_error(tmp_path: Path) -> None:
    """The desired end state is "absent", and it already holds."""
    _install(runner, tmp_path)

    import tomllib

    import tomli_w

    with open(_receipt_path(tmp_path), "rb") as fh:
        receipt = tomllib.load(fh)
    receipt["files_written"].append("sq/never-existed.md")
    with open(_receipt_path(tmp_path), "wb") as fh:
        tomli_w.dump(receipt, fh)

    result = _install(runner, tmp_path)
    assert result.exit_code == 0  # type: ignore[attr-defined]

    uninstalled = _uninstall(runner, tmp_path)
    assert uninstalled.exit_code == 0  # type: ignore[attr-defined]


def test_install_over_a_pre_receipt_installation_deletes_nothing(tmp_path: Path) -> None:
    """Files present, no receipt — squadron cannot tell its own from the user's.

    Upgrading into the receipt mechanism must not begin by destroying whatever the
    previous version left behind.
    """
    _install(runner, tmp_path)
    _receipt_path(tmp_path).unlink()
    survivor = tmp_path / "sq" / "from-an-older-version.md"
    survivor.write_text("installed before receipts existed")

    result = _install(runner, tmp_path)
    assert result.exit_code == 0  # type: ignore[attr-defined]

    assert survivor.read_text() == "installed before receipts existed"


def test_uninstall_without_a_receipt_removes_nothing_and_says_so(tmp_path: Path) -> None:
    _install(runner, tmp_path)
    _receipt_path(tmp_path).unlink()

    result = _uninstall(runner, tmp_path)
    assert result.exit_code == 0  # type: ignore[attr-defined]

    assert "no install receipt" in result.output.lower()  # type: ignore[attr-defined]
    assert (tmp_path / "sq").is_dir()
    assert (tmp_path / "analysis").is_dir()


def test_agents_tree_is_not_installed_for_claude(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Claude install takes only the subdirectories its delivery names.

    Before the delivery table, the installer walked every directory under the bundle,
    which would have swept ``commands/agents/`` into ``~/.claude/commands/`` the moment
    that tree was added (D8).
    """
    bundle = tmp_path / "bundle"
    for sub, name in (("sq", "review.md"), ("analysis", "understand.md")):
        (bundle / sub).mkdir(parents=True)
        (bundle / sub / name).write_text("claude command")
    skill = bundle / "agents" / "sq-review"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("agents skill")

    monkeypatch.setattr("squadron.cli.commands.install._get_commands_source", lambda: bundle)
    target = tmp_path / "target"
    result = _install(runner, target)
    assert result.exit_code == 0  # type: ignore[attr-defined]

    assert (target / "sq" / "review.md").exists()
    assert (target / "analysis" / "understand.md").exists()
    assert not (target / "agents").exists()
    assert not (target / "sq-review").exists()

    import tomllib

    receipt = tomllib.loads(_receipt_path(target).read_text())
    assert receipt["files_written"] == ["sq/review.md", "analysis/understand.md"]


# ---------------------------------------------------------------------------
# Slice 925: the agents asset tree must not drift from the Claude tree
# ---------------------------------------------------------------------------
#
# The two trees are authored separately by necessity — Codex performs no argument
# substitution, so an agents skill cannot be generated from its Claude twin (D3).
# Separately authored means they can silently diverge: a command added to
# commands/sq/ simply never appears for Codex users. These tests are the only thing
# that makes that divergence loud.

SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _agents_root() -> Path:
    # Resolved through the module rather than the name imported at the top of this
    # file, so the teeth test below can point the tree elsewhere with monkeypatch.
    return install_module._get_commands_source() / "agents"  # type: ignore[attr-defined]


def _skill_frontmatter(skill_md: Path) -> dict[str, object]:
    """Parse the YAML frontmatter of a SKILL.md.

    Tolerates a leading HTML comment: the forked analysis skills carry an attribution
    line above the frontmatter, and a parser requiring the fence on line 1 would report
    those two skills as having no frontmatter at all.
    """
    text = skill_md.read_text()
    fence_start = text.find("---\n")
    assert fence_start != -1, f"{skill_md} has no frontmatter"
    body = text[fence_start + 4 :]
    fence_end = body.find("\n---")
    assert fence_end != -1, f"{skill_md} has an unterminated frontmatter block"
    parsed = yaml.safe_load(body[:fence_end])
    assert isinstance(parsed, dict), f"{skill_md} frontmatter is not a mapping"
    return parsed  # type: ignore[return-value]


def _claude_twins() -> list[tuple[str, Path]]:
    """Every Claude command file, paired with the agents skill name it requires."""
    source = install_module._get_commands_source()  # type: ignore[attr-defined]
    pairs: list[tuple[str, Path]] = []
    for sub in DELIVERIES[CommandTarget.CLAUDE].bundle_subdirs:
        for md_file in sorted((source / sub).glob("*.md")):
            pairs.append((f"{sub}-{md_file.stem}", md_file))
    return pairs


def test_every_claude_command_has_an_agents_twin() -> None:
    for skill_name, claude_file in _claude_twins():
        expected = _agents_root() / skill_name / "SKILL.md"
        assert expected.is_file(), (
            f"{claude_file} has no agents twin — expected {expected}. "
            f"Every command in the Claude tree must be authored for the agents tree too."
        )


def test_every_agents_skill_has_a_claude_twin() -> None:
    required = {name for name, _ in _claude_twins()}
    for skill_dir in sorted(_agents_root().iterdir()):
        if not skill_dir.is_dir():
            continue
        assert skill_dir.name in required, (
            f"{skill_dir} has no Claude twin. Either add the Claude command or remove "
            f"this skill — the two trees are a bijection."
        )


def test_agents_skill_name_matches_its_directory() -> None:
    for skill_dir in sorted(_agents_root().iterdir()):
        if not skill_dir.is_dir():
            continue
        frontmatter = _skill_frontmatter(skill_dir / "SKILL.md")
        name = frontmatter.get("name")
        # Codex requires only non-empty and <=64 chars, but the agentskills.io spec
        # requires the directory and the name to agree (D4).
        assert name == skill_dir.name, f"{skill_dir}/SKILL.md declares name {name!r}"
        assert isinstance(name, str) and SKILL_NAME_PATTERN.match(name), (
            f"{skill_dir} name {name!r} is not lowercase-hyphenated"
        )
        assert len(name) <= 64, f"{skill_dir} name exceeds Codex's 64-character limit"


def test_agents_skill_has_a_nonempty_description() -> None:
    for skill_dir in sorted(_agents_root().iterdir()):
        if not skill_dir.is_dir():
            continue
        frontmatter = _skill_frontmatter(skill_dir / "SKILL.md")
        description = frontmatter.get("description")
        # Codex selects skills on the description, so an empty one is unreachable.
        assert isinstance(description, str) and description.strip(), (
            f"{skill_dir}/SKILL.md has no usable description"
        )


def test_openai_yaml_mirrors_disable_model_invocation() -> None:
    """``openai.yaml`` appears exactly where the Claude twin disables model invocation.

    Claude's ``disable-model-invocation: true`` has no frontmatter equivalent in Codex;
    the nearest behavior is ``policy.allow_implicit_invocation: false`` in a sibling
    YAML (D7).
    """
    for skill_name, claude_file in _claude_twins():
        twin_disables = "disable-model-invocation: true" in claude_file.read_text()
        policy_file = _agents_root() / skill_name / "agents" / "openai.yaml"
        assert policy_file.is_file() == twin_disables, (
            f"{claude_file} disable-model-invocation={twin_disables} but "
            f"{policy_file} exists={policy_file.is_file()}"
        )
        if twin_disables:
            policy = yaml.safe_load(policy_file.read_text())
            assert policy["policy"]["allow_implicit_invocation"] is False


def test_no_agents_skill_uses_claude_argument_substitution() -> None:
    """Codex performs no argument substitution, so these tokens never resolve (D3)."""
    for skill_md in sorted(_agents_root().rglob("SKILL.md")):
        text = skill_md.read_text()
        for token in ("$ARGUMENTS", "$1", "$2"):
            assert token not in text, (
                f"{skill_md} contains {token}, which Codex passes through literally"
            )


def test_drift_guard_fails_on_a_command_with_no_twin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard has teeth — verified against a copy, never the real bundle."""
    bundle = tmp_path / "commands"
    shutil.copytree(_get_commands_source(), bundle)
    (bundle / "sq" / "newcommand.md").write_text("a command with no agents twin")

    monkeypatch.setattr("squadron.cli.commands.install._get_commands_source", lambda: bundle)
    with pytest.raises(AssertionError, match="no agents twin"):
        test_every_claude_command_has_an_agents_twin()


def test_no_test_touches_the_real_receipts_directory() -> None:
    """The helpers must never resolve to ``~/.config/squadron/receipts``.

    Asserted mechanically rather than trusted: these tests install and uninstall for
    real, and a receipt written to the user's own directory would make their next real
    uninstall act on files a test invented.
    """
    from squadron.skills.receipts import DEFAULT_RECEIPTS_DIR

    assert _receipts_dir(Path("/tmp/pytest-example/target")) != DEFAULT_RECEIPTS_DIR
    assert DEFAULT_RECEIPTS_DIR not in _receipts_dir(Path("/tmp/pytest-example/target")).parents
