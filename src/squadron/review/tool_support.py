"""Run-scoped reasoning about which tools a review will actually have.

The injection decision — whether file bodies are pasted into the prompt — used to key off
``ProviderCapabilities.can_read_files``, a per-provider constant. That constant cannot see
what a particular run was given: a non-SDK model with ``read_file`` in its ``allowed_tools``
can read files perfectly well, and injecting bodies for it wastes context on content the model
would have fetched itself.

Computed per call rather than stored on ``ProviderCapabilities`` (design D1): the answer
depends on the template and step in front of it, not on the provider.
"""

from __future__ import annotations

from squadron import tools
from squadron.providers.base import ProviderType
from squadron.tools.builtin import READ_FILE_NAME


def effective_tools(allowed_tools: list[str] | None, provider: str) -> list[str]:
    """Return the tool names a run will actually be able to call.

    SDK profiles resolve names themselves at the config edge (their vocabulary is Claude's,
    not squadron's), so their declared list passes through untouched. Non-SDK profiles run
    against the squadron registry, so only registered names survive.
    """
    if not allowed_tools:
        return []
    if provider == ProviderType.SDK:
        return list(allowed_tools)
    return [name for name in allowed_tools if tools.lookup(name) is not None]


def should_inject_file_bodies(
    *, can_read_files: bool, allowed_tools: list[str] | None, provider: str
) -> bool:
    """Return True when the prompt must carry file bodies because nothing else can fetch them.

    ``can_read_files`` keeps its existing meaning and is untouched elsewhere; this adds the
    second half of the question it could never answer on its own.
    """
    if can_read_files:
        return False
    return READ_FILE_NAME not in effective_tools(allowed_tools, provider)
