"""Canonical squadron tool names translated to Claude Code's vocabulary.

Templates and pipeline steps declare tools in the canonical vocabulary: the tools
``squadron.tools.builtin`` implements, plus a few Claude-only capabilities named below. The
Claude Code CLI behind the SDK provider knows a different set
of names for the same capabilities, so the two are reconciled at exactly one place: the point
where ``AgentConfig`` becomes ``ClaudeAgentOptions``. Nothing upstream of that edge needs to
know Claude's names, and nothing downstream sees canonical ones.

An unmapped name raises rather than being dropped (design D3): a review that silently loses
its file-reading tools produces a confident, uninformed verdict, which is worse than a crash.
"""

from __future__ import annotations

from squadron.providers.errors import ProviderError

CANONICAL_TO_CLAUDE: dict[str, str] = {
    # Implemented by squadron.tools.builtin, so every provider can offer them.
    "read_file": "Read",
    "list_files": "Glob",
    "grep": "Grep",
    "write_file": "Write",
    "bash": "Bash",
    # Claude Code's own tools with no squadron executor. They are canonical names
    # so callers never spell Claude's vocabulary, but only this provider can offer
    # them; a non-SDK agent rejects them as unknown rather than dropping them (#107).
    "edit_file": "Edit",
    "task": "Task",
    "todo_write": "TodoWrite",
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
