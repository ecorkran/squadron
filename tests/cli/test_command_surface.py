"""Drift test: PR-related command files vs. the CLI surface they describe (D2).

A squadron slash command is a markdown file telling a session which `sq` command to
run — it has no code path pytest can execute, so "the transport matches the CLI"
cannot be tested by invoking it. What can be tested is the one thing that drifts:
whether the command file's description of the CLI surface still agrees with the
CLI itself. This module pins that for `review pr`, `pr show`, and `pr create`.
"""

from __future__ import annotations

import re
from pathlib import Path

import click
from typer.main import get_command

from squadron.cli.app import app
from squadron.cli.commands.install import _get_commands_source

# Flags excluded from the comparison. `--help` is registered on every Click command
# but never documented in a command file's section, so it is not a drift signal.
EXCLUDED_FLAGS = {"--help"}

# One entry per (command path, command file, section heading) so extending coverage
# to another subcommand later is an added entry, not a new test.
_COMMANDS_UNDER_TEST = [
    (("review", "pr"), "review.md", "## Subcommand: pr"),
    (("pr", "show"), "pr.md", "## Subcommand: show"),
    (("pr", "create"), "pr.md", "## Subcommand: create"),
]

_FLAG_TOKEN_RE = re.compile(r"--[a-z][a-z-]*")


def _extract_section(text: str, heading: str) -> str:
    """Return the text from `heading` up to the next `## ` heading, or end of file."""
    start = text.index(heading)
    start += len(heading)
    next_heading = re.search(r"^## ", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end]


def _flags_in_section(section: str) -> set[str]:
    """Lenient token scan: `--flag` anywhere in the section, in or out of backticks."""
    return set(_FLAG_TOKEN_RE.findall(section)) - EXCLUDED_FLAGS


def _cli_long_options(command_path: tuple[str, ...]) -> set[str]:
    """Registered long-form (--foo) options for a Click command reached by path."""
    root = get_command(app)
    node: click.Command = root
    for name in command_path:
        node = node.commands[name]  # type: ignore[attr-defined]

    opts: set[str] = set()
    for param in node.params:
        if isinstance(param, click.Option):
            opts.update(o for o in (*param.opts, *param.secondary_opts) if o.startswith("--"))
    return opts - EXCLUDED_FLAGS


def _command_file_path(filename: str) -> Path:
    return _get_commands_source() / "sq" / filename


def assert_surface_agreement(cli_flags: set[str], file_flags: set[str], label: str) -> None:
    """Shared comparison, called by the real test and by the fail-proof test (3.4)."""
    undocumented = cli_flags - file_flags
    unsupported = file_flags - cli_flags
    messages = []
    if undocumented:
        messages.append(
            f"{label}: CLI registers {sorted(undocumented)} but the command file "
            "does not document them (undocumented capability)"
        )
    if unsupported:
        messages.append(
            f"{label}: command file documents {sorted(unsupported)} but the CLI "
            "does not register them (instruction to pass a flag the CLI will reject)"
        )
    assert not messages, "; ".join(messages)


def test_pr_command_sections_exist() -> None:
    for _command_path, filename, heading in _COMMANDS_UNDER_TEST:
        text = _command_file_path(filename).read_text()
        assert heading in text, f"{filename} is missing heading {heading!r}"


def test_surface_agreement() -> None:
    for command_path, filename, heading in _COMMANDS_UNDER_TEST:
        text = _command_file_path(filename).read_text()
        section = _extract_section(text, heading)
        file_flags = _flags_in_section(section)
        cli_flags = _cli_long_options(command_path)
        label = f"{' '.join(command_path)} ({filename} {heading})"
        assert_surface_agreement(cli_flags, file_flags, label)


def test_delegation_line_has_no_injected_flags() -> None:
    delegation_commands = {
        ("review", "pr"): "sq review pr",
        ("pr", "show"): "sq pr show",
        ("pr", "create"): "sq pr create",
    }
    for command_path, filename, heading in _COMMANDS_UNDER_TEST:
        text = _command_file_path(filename).read_text()
        section = _extract_section(text, heading)
        delegation = delegation_commands[command_path]
        assert delegation in section, (
            f"{filename} {heading} does not contain its delegation command {delegation!r}"
        )
        # The pr section of review.md must not append -v, unlike code/slice/tasks/arch (D1).
        if command_path == ("review", "pr"):
            delegation_lines = [line for line in section.splitlines() if delegation in line]
            assert delegation_lines, f"no line in {filename} {heading} contains {delegation!r}"
            for line in delegation_lines:
                assert "-v" not in line.split(delegation, 1)[1].split("{remainder}")[0], (
                    f"{filename} {heading} appends a flag to the delegation line: {line!r}"
                )


def test_comparison_fails_on_incomplete_section() -> None:
    """Proves the drift test can fail (Success Criteria, Technical).

    Runs the real comparison function against a deliberately incomplete section
    string, exercising the production path rather than a copy of it.
    """
    cli_flags = _cli_long_options(("pr", "show"))
    assert cli_flags, "pr show must register at least one long option for this proof to mean anything"

    incomplete_file_flags: set[str] = set()  # documents none of the CLI's real flags
    try:
        assert_surface_agreement(cli_flags, incomplete_file_flags, "pr show (incomplete fixture)")
    except AssertionError:
        pass
    else:
        raise AssertionError(
            "assert_surface_agreement did not fail against a deliberately incomplete section"
        )
