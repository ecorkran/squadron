"""Command install targets — the vocabulary and per-target delivery table.

`sq install-commands` writes the same bundled command set into two different
layouts: Claude Code reads flat markdown under `~/.claude/commands/<pack>/`,
while Codex and other agent-skill runtimes read a directory per skill under
`~/.agents/skills/<skill>/SKILL.md`. Everything that differs between the two
lives in `DELIVERIES`; the installer, the doctor check and the setup steps all
read it rather than branching on a target string.

The vocabulary is Context Forge's verbatim (D1) so `--ide codex` means the same
thing to `cf` and to `sq`.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class CommandTarget(StrEnum):
    """A runtime squadron can deliver its command set to.

    Only targets with a working delivery mechanism are members. Context Forge's
    `setup-ide` also knows `copilot` and `cursor`, but its `install-commands`
    rejects them for the same reason this enum omits them: there is nowhere to
    put the files (D1).
    """

    CLAUDE = "claude"
    AGENTS = "agents"


# Spellings a user may reasonably type for a member. `codex` and `openai` both
# name the runtime that reads the agent-skill layout.
TARGET_ALIASES: dict[str, CommandTarget] = {
    "codex": CommandTarget.AGENTS,
    "openai": CommandTarget.AGENTS,
}


def _accepted_spellings() -> str:
    """Every string `normalize_target` accepts, for error messages."""
    return ", ".join(sorted({*(t.value for t in CommandTarget), *TARGET_ALIASES}))


def normalize_target(raw: str) -> CommandTarget:
    """Resolve a user-supplied target name to a `CommandTarget`.

    Case- and whitespace-insensitive. Raises `ValueError` naming every accepted
    spelling when `raw` is neither a member nor an alias — including for
    `copilot` and `cursor`, which `cf` knows but neither tool can deliver to.
    """
    cleaned = raw.strip().lower()
    for member in CommandTarget:
        if cleaned == member.value:
            return member
    alias = TARGET_ALIASES.get(cleaned)
    if alias is not None:
        return alias
    raise ValueError(f"Unknown install target {raw!r}. Accepted: {_accepted_spellings()}.")


def write_flat_markdown(source: Path, destination: Path) -> list[str]:
    """Copy `source/*.md` to `destination/<source.name>/` — the Claude layout.

    Returns the written paths relative to `destination`, which is what the
    install receipt records.
    """
    dest_sub = destination / source.name
    dest_sub.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for md_file in sorted(source.glob("*.md")):
        shutil.copy2(md_file, dest_sub / md_file.name)
        written.append(f"{source.name}/{md_file.name}")
    return written


def write_skill_dirs(source: Path, destination: Path) -> list[str]:
    """Copy each directory under `source` to `destination/` — the agents layout.

    A skill is a directory, not a file: `SKILL.md` plus whatever sits beside it
    (`agents/openai.yaml`, for instance), so the whole tree is copied and every
    file in it is recorded individually. Recording the directory alone would
    leave uninstall unable to tell squadron's files from the user's.

    Ownership is read from the **source** tree, never the destination. The copy
    merges into an existing directory, so walking the destination afterwards
    would claim any file the user had put there — and a later uninstall, which
    trusts the receipt absolutely, would delete it. That is issue #65's
    ownership confusion arriving by a different route.
    """
    destination.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for skill_dir in sorted(source.iterdir()):
        if not skill_dir.is_dir():
            continue
        shutil.copytree(skill_dir, destination / skill_dir.name, dirs_exist_ok=True)
        for original in sorted(skill_dir.rglob("*")):
            if original.is_file():
                written.append((Path(skill_dir.name) / original.relative_to(skill_dir)).as_posix())
    return written


@dataclass(frozen=True)
class TargetDelivery:
    """Everything that differs between one install target and another.

    Roots are stored relative and expanded at use, not at import: the module
    must resolve against a patched `HOME` so tests never write to the real one
    (#47).
    """

    machine_root: Path
    local_root: Path
    bundle_subdirs: tuple[str, ...]
    check_name: str
    fix_hint: str
    receipt_base: str
    layout: Callable[[Path, Path], list[str]]
    #: Where the doctor check counts, relative to the install root. Claude's
    #: check has always pointed at the pack subdirectory rather than the commands
    #: root; the agents layout counts at the root itself.
    check_subdir: str | None

    def resolve_root(self, *, local: bool) -> Path:
        """The destination directory for this target at the given scope."""
        if local:
            return Path.cwd() / self.local_root
        return (Path("~") / self.machine_root).expanduser()

    def check_root(self) -> Path:
        """Where the doctor check looks for this target's installed commands.

        Machine scope only, which is what doctor has always reported. A project-local
        install is deliberately not checked: doctor answers "is squadron set up on this
        machine", and a `--local` install is scoped to one repository.
        """
        root = self.resolve_root(local=False)
        return root / self.check_subdir if self.check_subdir else root


def bundled_skill_names(source: Path) -> set[str]:
    """The skill directory names squadron itself ships under `source/agents`.

    The agents root is shared with every other agent-skill source, so "is
    squadron installed" cannot be answered by counting what is there. It is
    answered by counting how many of *our* skills are there.
    """
    agents_bundle = source / "agents"
    if not agents_bundle.is_dir():
        return set()
    return {child.name for child in agents_bundle.iterdir() if (child / "SKILL.md").is_file()}


DELIVERIES: dict[CommandTarget, TargetDelivery] = {
    CommandTarget.CLAUDE: TargetDelivery(
        machine_root=Path(".claude/commands"),
        local_root=Path(".claude/commands"),
        bundle_subdirs=("sq", "analysis"),
        check_name="slash commands",
        fix_hint="sq install-commands",
        # The name every receipt written since #65 carries. Changing it would
        # orphan those receipts and with them the stale-removal they govern (D5).
        receipt_base="squadron-commands",
        layout=write_flat_markdown,
        check_subdir="sq",
    ),
    CommandTarget.AGENTS: TargetDelivery(
        # `~/.codex/skills` is marked deprecated in Codex's own source; the
        # documented user root is `~/.agents/skills` (D2).
        machine_root=Path(".agents/skills"),
        local_root=Path(".agents/skills"),
        bundle_subdirs=("agents",),
        check_name="codex skills",
        fix_hint="sq install-commands --ide codex",
        receipt_base="squadron-commands-agents",
        layout=write_skill_dirs,
        check_subdir=None,
    ),
}

# A new enum member without a delivery is a missing install path, not a default.
assert set(DELIVERIES) == set(CommandTarget), "every CommandTarget needs a TargetDelivery"


def receipt_name(target: CommandTarget, *, local: bool) -> str:
    """The receipt key for a target/scope pair.

    Four distinct names, so a machine install and a local one never overwrite
    each other's record of what to remove (D5).
    """
    base = DELIVERIES[target].receipt_base
    return f"{base}-local" if local else base
