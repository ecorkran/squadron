"""Resolve a command's executable through PATH before spawning it.

On Windows, ``CreateProcess`` searches PATH for a bare name with only ``.exe``
appended, so npm-installed CLIs — ``cf`` and ``npm`` itself ship as ``.cmd``
shims — raise ``FileNotFoundError`` when launched as ``["cf", ...]``.
``shutil.which`` honours ``PATHEXT`` and finds the shim.
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Sequence

#: Only Windows needs resolving: POSIX ``exec`` already searches PATH for a bare name.
_RESOLVE_ON_PATH = sys.platform == "win32"


def resolve_argv(argv: Sequence[str]) -> list[str]:
    """Return ``argv`` with ``argv[0]`` replaced by its full path on PATH (Windows only).

    A name that does not resolve is returned unchanged, so the spawn still
    raises ``FileNotFoundError`` and each caller's missing-tool handling keeps
    reporting the tool by name.
    """
    if not _RESOLVE_ON_PATH:
        return list(argv)
    resolved = shutil.which(argv[0])
    return [resolved if resolved is not None else argv[0], *argv[1:]]
