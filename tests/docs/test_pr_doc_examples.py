"""Documentation-example parse test for the PR surface (D5).

Every ``sq review pr`` / ``sq pr`` example inside a ``bash``-fenced code block in
README.md, docs/COMMANDS.md, and docs/QUICKSTART.md is parsed against the real
Click command it names, without invoking it. An unknown flag, or a flag missing
its required value, fails the suite — "examples run as written" is held
mechanically here, and by the live run's use of the same invocations (Task 9).
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import click
from typer.main import get_command

from squadron.cli.app import app

_REPO_ROOT = Path(__file__).parents[2]
_DOCS = [
    _REPO_ROOT / "README.md",
    _REPO_ROOT / "docs" / "COMMANDS.md",
    _REPO_ROOT / "docs" / "QUICKSTART.md",
]

_BASH_FENCE_RE = re.compile(r"```bash(?:[^\S\r\n]+[^\n]*)?\r?\n(.*?)```", re.DOTALL)
_EXAMPLE_PREFIXES = ("sq review pr", "sq pr")


def _extract_examples(text: str) -> list[str]:
    """Every line starting `sq review pr` or `sq pr` inside a ```bash fence.

    Lenient: tolerates a leading `$ ` prompt, a trailing `#` comment, and joins a
    line ending in `\\` with the line that follows (a wrapped example).
    """
    examples: list[str] = []
    for block in _BASH_FENCE_RE.findall(text):
        lines = block.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("$ "):
                line = line[2:].strip()
            joined = line
            while joined.endswith("\\") and i + 1 < len(lines):
                i += 1
                continuation = lines[i].strip()
                joined = joined[:-1].rstrip() + " " + continuation
            # Strip a trailing comment, but not a `#` that is part of a target
            # like `owner/repo#116` — only a comment preceded by whitespace.
            joined = re.sub(r"(?<=\s)#.*$", "", joined).rstrip()
            if joined.startswith(_EXAMPLE_PREFIXES):
                examples.append(joined)
            i += 1
    return examples


def _collect_all_examples() -> list[str]:
    examples: list[str] = []
    for doc in _DOCS:
        examples.extend(_extract_examples(doc.read_text()))
    return examples


def _resolve_command(example: str) -> tuple[click.Command, list[str]]:
    """Resolve the Click command an example names, and its remaining args."""
    root = get_command(app)
    assert isinstance(root, click.Group)
    tokens = shlex.split(example)
    assert tokens[0] == "sq", f"example does not start with sq: {example!r}"

    if tokens[1] == "review":
        # sq review pr {args...}
        review = root.commands["review"]
        assert isinstance(review, click.Group)
        return review.commands["pr"], tokens[3:]

    # sq pr show|create {args...}
    pr = root.commands["pr"]
    assert isinstance(pr, click.Group)
    return pr.commands[tokens[2]], tokens[3:]


def test_at_least_one_example_collected() -> None:
    """An extractor that silently finds nothing must fail, not pass vacuously."""
    examples = _collect_all_examples()
    assert examples, "no `sq review pr` / `sq pr` examples found in README/COMMANDS/QUICKSTART"


def test_every_example_parses_against_the_real_command() -> None:
    for example in _collect_all_examples():
        command, args = _resolve_command(example)
        try:
            with command.make_context("test", list(args)):
                pass
        except click.ClickException as exc:
            raise AssertionError(f"example failed to parse: {example!r} ({exc})") from exc
