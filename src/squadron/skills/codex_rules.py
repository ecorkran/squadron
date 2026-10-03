"""Codex sandbox approval rules for the sq commands that reach the network.

Codex's sandbox refuses a network-enabled command unless a rule in
``<codex home>/rules/default.rules`` allows it, and the refusal reads like a
provider failure (issue #127). Installing squadron's Codex skills writes the
rules those skills need, so a first ``$sq-review`` works instead of failing
with a misleading "provider connection failed".
"""

from __future__ import annotations

import os
import re
from pathlib import Path

#: Codex reads this variable for its home directory; ``~/.codex`` when unset.
CODEX_HOME_ENV = "CODEX_HOME"

#: The rules file Codex loads, relative to its home.
RULES_RELATIVE_PATH = Path("rules") / "default.rules"

#: Commands whose skills reach a model provider or GitHub.
NETWORK_COMMAND_PREFIXES: tuple[tuple[str, ...], ...] = (
    ("sq", "review"),
    ("sq", "run"),
    ("sq", "pr"),
)

_WHITESPACE = re.compile(r"\s+")


def codex_home() -> Path:
    """Codex's home directory, resolved the way Codex resolves it."""
    configured = os.environ.get(CODEX_HOME_ENV)
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def _pattern_text(prefix: tuple[str, ...]) -> str:
    return "[" + ", ".join(f'"{token}"' for token in prefix) + "]"


def _rule_line(prefix: tuple[str, ...]) -> str:
    return f'prefix_rule(pattern={_pattern_text(prefix)}, decision="allow")'


def _covered(prefix: tuple[str, ...], compact_rules: str) -> bool:
    """Whether an allow rule for *prefix*, or any shorter prefix of it, exists.

    Compared with all whitespace removed, so the multi-line form a user may
    have pasted by hand matches the single-line form Codex itself writes.
    """
    for length in range(1, len(prefix) + 1):
        pattern = _WHITESPACE.sub("", f"pattern={_pattern_text(prefix[:length])}")
        if pattern in compact_rules:
            return True
    return False


def ensure_sq_rules(home: Path) -> list[str]:
    """Append an allow rule for each network command not already covered.

    Returns the rule lines added; empty when every command was already allowed.
    Existing content is never rewritten — only appended to.
    """
    rules_path = home / RULES_RELATIVE_PATH
    existing = rules_path.read_text(encoding="utf-8") if rules_path.exists() else ""
    compact = _WHITESPACE.sub("", existing)
    added = [_rule_line(p) for p in NETWORK_COMMAND_PREFIXES if not _covered(p, compact)]
    if not added:
        return []
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    separator = "" if not existing or existing.endswith("\n") else "\n"
    rules_path.write_text(existing + separator + "\n".join(added) + "\n", encoding="utf-8")
    return added
