"""Built-in tool implementations: ``read_file``, ``write_file``, ``bash``, ``list_files``, ``grep``.

These names are the start of the canonical squadron tool vocabulary. Every executor is bound
to a resolved :class:`~squadron.tools.models.JailSpec` by its factory; the file tools treat
its root as a jail root, refuse anything under its exclusions, and ``bash`` runs in the root.

The working directory is the only boundary at this stage. Network denial, environment
scrubbing, and process isolation are architecture-documented future work, deliberately out of
scope here.

Split from a single 690-line module into this package (slice 266, T23). The public import
surface is unchanged: ``squadron.tools.builtin.READ_FILE`` and its siblings still resolve,
and importing this package still registers all five descriptors exactly once — each
submodule calls ``register()`` at module scope, and importing it here is what fires that.
"""

from __future__ import annotations

from squadron.tools.builtin._shared import (
    BASH_NAME,
    GREP_NAME,
    LIST_FILES_NAME,
    READ_FILE_NAME,
    WRITE_FILE_NAME,
    contained_in_jail,
    resolve_in_jail,
)
from squadron.tools.builtin.bash_tool import BASH, BASH_PARAMETERS
from squadron.tools.builtin.file_tools import (
    LIST_FILES,
    LIST_FILES_PARAMETERS,
    READ_FILE,
    READ_FILE_PARAMETERS,
    WRITE_FILE,
    WRITE_FILE_PARAMETERS,
)
from squadron.tools.builtin.search_tools import GREP, GREP_PARAMETERS

# The jail helper was ``builtin._resolve_in_jail`` before the split, and the jail's own
# tests import it under that name. The split is a pure move, so the old name keeps
# resolving; ``resolve_in_jail`` is the same object under the package-internal spelling.
_resolve_in_jail = resolve_in_jail

__all__ = [
    "BASH",
    "BASH_NAME",
    "BASH_PARAMETERS",
    "GREP",
    "GREP_NAME",
    "GREP_PARAMETERS",
    "LIST_FILES",
    "LIST_FILES_NAME",
    "LIST_FILES_PARAMETERS",
    "READ_FILE",
    "READ_FILE_NAME",
    "READ_FILE_PARAMETERS",
    "WRITE_FILE",
    "WRITE_FILE_NAME",
    "WRITE_FILE_PARAMETERS",
    "_resolve_in_jail",
    "contained_in_jail",
    "resolve_in_jail",
]
