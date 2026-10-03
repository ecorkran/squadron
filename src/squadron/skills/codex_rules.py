"""Codex sandbox approval rules for the sq commands that need the network or home dir.

Codex's sandbox refuses network access and writes outside the workspace unless a
rule allows the command, and the refusal reads like a provider failure (issue
#127). Installing squadron's Codex skills writes one squadron-owned rules file so
a first ``$sq-review`` works without the user ever editing Codex's config.

The file is squadron's alone: Codex loads every ``*.rules`` file under
``<codex home>/rules/``, so the whole file is rewritten on each install and
deleted on uninstall. The user's ``default.rules`` — which Codex appends its own
"always allow" approvals to — is never read or written (928 D9).
"""

from __future__ import annotations

import os
from pathlib import Path

#: Codex reads this variable for its home directory; ``~/.codex`` when unset.
CODEX_HOME_ENV = "CODEX_HOME"

#: The squadron-owned rules file, relative to Codex's home.
RULES_RELATIVE_PATH = Path("rules") / "squadron.rules"

#: ``sq`` subcommands the sandbox blocks, with one example invocation each. Chosen
#: by probing each command under ``codex sandbox`` (928 D10): ``pr`` and
#: ``review`` need the network, ``run`` writes run state under
#: ``~/.config/squadron``, ``auth login`` writes ``~/.codex``, ``metrology``
#: reaches a provider, and ``skills install`` clones github sources.
SQ_RULE_EXAMPLES: dict[str, str] = {
    "review": "sq review code 100",
    "run": "sq run P4 100",
    "pr": "sq pr show 1",
    "metrology": "sq metrology audit run .",
    "auth": "sq auth login",
    "skills": "sq skills install analysis",
}


def codex_home() -> Path:
    """Codex's home directory, resolved the way Codex resolves it."""
    configured = os.environ.get(CODEX_HOME_ENV)
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def render_sq_rules() -> str:
    """The full contents of the squadron rules file.

    One ``prefix_rule`` with the subcommands as alternatives. ``match`` lists an
    example per subcommand; Codex validates those when it loads the file, so a
    rule that stopped matching fails loudly instead of silently allowing nothing.
    """
    alternatives = ", ".join(f'"{name}"' for name in SQ_RULE_EXAMPLES)
    examples = "\n".join(f'        "{example}",' for example in SQ_RULE_EXAMPLES.values())
    return (
        "# Written by squadron (sq install-commands --ide codex); rewritten on every\n"
        "# install and removed by sq uninstall-commands --ide codex. Do not edit —\n"
        "# put your own rules in default.rules or another file in this directory.\n"
        "prefix_rule(\n"
        f'    pattern = ["sq", [{alternatives}]],\n'
        '    decision = "allow",\n'
        '    justification = "squadron commands that call a model provider or GitHub, '
        'or write squadron/Codex state",\n'
        "    match = [\n"
        f"{examples}\n"
        "    ],\n"
        ")\n"
    )


def write_sq_rules(home: Path) -> Path:
    """Write the squadron rules file under ``home`` and return its path."""
    rules_path = home / RULES_RELATIVE_PATH
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    rules_path.write_text(render_sq_rules(), encoding="utf-8")
    return rules_path


def remove_sq_rules(home: Path) -> Path | None:
    """Delete the squadron rules file; return its path, or ``None`` if it was absent."""
    rules_path = home / RULES_RELATIVE_PATH
    if not rules_path.exists():
        return None
    rules_path.unlink()
    return rules_path
