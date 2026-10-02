"""The Codex install command is defined in exactly one ``src`` module (slice 129 D9)."""

from __future__ import annotations

from pathlib import Path

import squadron
from squadron.providers.codex.runtime import CODEX_INSTALL_COMMAND


def test_install_command_has_one_definition_site() -> None:
    src_root = Path(squadron.__file__).parent
    sites = [
        path.relative_to(src_root).as_posix()
        for path in src_root.rglob("*.py")
        if CODEX_INSTALL_COMMAND in path.read_text(encoding="utf-8")
    ]
    assert sites == ["providers/codex/runtime.py"]
