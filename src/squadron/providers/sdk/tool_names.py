"""Canonical squadron tool names translated to Claude Code's vocabulary.

Templates and pipeline steps declare tools in the canonical vocabulary defined by
``squadron.tools.builtin``. The Claude Code CLI behind the SDK provider knows a different set
of names for the same capabilities, so the two are reconciled at exactly one place: the point
where ``AgentConfig`` becomes ``ClaudeAgentOptions``. Nothing upstream of that edge needs to
know Claude's names, and nothing downstream sees canonical ones.

An unmapped name raises rather than being dropped (design D3): a review that silently loses
its file-reading tools produces a confident, uninformed verdict, which is worse than a crash.
"""

from __future__ import annotations

from squadron.providers.errors import ProviderError

CANONICAL_TO_CLAUDE: dict[str, str] = {
    "read_file": "Read",
    "list_files": "Glob",
    "grep": "Grep",
    "write_file": "Write",
    "bash": "Bash",
}


def translate_tool_names(names: list[str]) -> list[str]:
    """Return *names* in Claude vocabulary, raising on any name with no mapping.

    All unmapped names are reported together — a caller fixing a template wants the whole list,
    not one name per run.
    """
    unmapped = [name for name in names if name not in CANONICAL_TO_CLAUDE]
    if unmapped:
        known = ", ".join(sorted(CANONICAL_TO_CLAUDE))
        raise ProviderError(
            f"No Claude tool name is mapped for {', '.join(unmapped)}. "
            f"Known canonical tool names: {known}."
        )
    return [CANONICAL_TO_CLAUDE[name] for name in names]
