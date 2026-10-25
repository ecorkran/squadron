"""TypeScript duplication: tree-sitter leaf tokens fed to the shared window pass (slice 401, D3)."""

from __future__ import annotations

from collections.abc import Sequence

from squadron.metrology.snapshot.contract import AdapterContext
from squadron.metrology.snapshot.duplication import duplication_tool_identity, measure_duplication
from squadron.metrology.snapshot.typescript_length import (
    TypeScriptParseError,
    parse_checked,
    tree_sitter_tool_identity,
)
from squadron.metrology.snapshot_models import Measurement, SourceLanguage

#: Leaf node types that carry no code (D3).
_DROPPED_LEAF_TYPES = frozenset({"comment"})


def _tokenize(path: str, text: str) -> list[tuple[str, int]]:
    """Code tokens (tree-sitter leaves) with their 1-based start line; comments dropped."""
    tree = parse_checked(path, text)
    tokens: list[tuple[str, int]] = []
    pending = [tree.root_node]
    while pending:
        node = pending.pop()
        if node.children:
            pending.extend(reversed(node.children))
        elif node.type not in _DROPPED_LEAF_TYPES and node.text is not None:
            tokens.append((node.text.decode("utf-8", errors="replace"), node.start_point.row + 1))
    return tokens


def measure_typescript_duplication(ctx: AdapterContext, files: Sequence[str]) -> Measurement:
    """Duplicated lines across *files*, from tree-sitter leaf tokens (no Node)."""
    return measure_duplication(
        ctx.repo_root,
        files,
        SourceLanguage.TYPESCRIPT,
        duplication_tool_identity(tree_sitter_tool_identity()),
        _tokenize,
        (TypeScriptParseError,),
    )
