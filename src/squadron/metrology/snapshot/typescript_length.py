"""TypeScript file and function length, parsed in-process with tree-sitter (D5, D6).

No Node process runs for length: tree-sitter is deterministic and works on a project
that has no ``node_modules``. ``.tsx`` uses the TSX grammar, everything else the
TypeScript grammar. The measured project's code is parsed, never executed.
"""

from __future__ import annotations

import functools
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path

import tree_sitter
import tree_sitter_typescript

from squadron import __version__
from squadron.metrology.snapshot.contract import AdapterContext
from squadron.metrology.snapshot.lengths import (
    FunctionLength,
    count_non_blank_span,
    measure_length_metrics,
    physical_lines,
)
from squadron.metrology.snapshot_models import Measurement, SourceLanguage, ToolIdentity

TREE_SITTER_TOOL_NAME = "squadron-tree-sitter-ts"

_TSX_SUFFIX = ".tsx"

_COUNTING = (
    "non-blank physical lines; a function spans its first decorator (or declaration) "
    "through its last body line; function declarations (generators included), methods "
    "(constructors and accessors included), function expressions and block-bodied "
    "arrow functions at any depth; expression-bodied arrows excluded"
)

#: Node types that can be a counted function. Signatures without a body (overloads,
#: interface members, abstract methods) have no ``body`` field and are skipped.
_FUNCTION_TYPES = frozenset(
    {
        "function_declaration",
        "generator_function_declaration",
        "function_expression",
        "generator_function",
        "method_definition",
        "arrow_function",
    }
)
_BODY_BLOCK = "statement_block"
_DECORATOR = "decorator"
_ANONYMOUS = "<anonymous>"

#: When a function has no name of its own, the enclosing node that names it, and the
#: field of that node holding the name.
_NAMING_PARENTS = {
    "variable_declarator": "name",
    "pair": "key",
    "public_field_definition": "name",
}


class TypeScriptParseError(ValueError):
    """tree-sitter produced a tree with an error node, so the file's functions can't be trusted."""


def tree_sitter_tool_identity() -> ToolIdentity:
    """The in-process counter as a tool: squadron's version plus the parser and grammar versions."""
    return ToolIdentity(
        name=TREE_SITTER_TOOL_NAME,
        version=(
            f"{__version__}+tree-sitter{version('tree-sitter')}"
            f"+tree-sitter-typescript{version('tree-sitter-typescript')}"
        ),
        counting=_COUNTING,
    )


@functools.cache
def _language(tsx: bool) -> tree_sitter.Language:
    grammar = (
        tree_sitter_typescript.language_tsx() if tsx else tree_sitter_typescript.language_typescript()
    )
    return tree_sitter.Language(grammar)


def _parser(tsx: bool) -> tree_sitter.Parser:
    return tree_sitter.Parser(_language(tsx))


def _name(node: tree_sitter.Node) -> str:
    own = node.child_by_field_name("name")
    if own is None and node.parent is not None:
        field = _NAMING_PARENTS.get(node.parent.type)
        own = node.parent.child_by_field_name(field) if field is not None else None
    if own is None or own.text is None:
        return _ANONYMOUS
    return own.text.decode("utf-8", errors="replace")


def _start_row(node: tree_sitter.Node) -> int:
    """The node's first row, moved up over any decorators written before a method."""
    start = node
    while start.prev_sibling is not None and start.prev_sibling.type == _DECORATOR:
        start = start.prev_sibling
    return start.start_point.row


def _is_counted(node: tree_sitter.Node) -> bool:
    if node.type not in _FUNCTION_TYPES:
        return False
    body = node.child_by_field_name("body")
    if body is None:
        return False
    return node.type != "arrow_function" or body.type == _BODY_BLOCK


def _extract_functions(path: str, text: str) -> list[FunctionLength]:
    tree = _parser(Path(path).suffix.lower() == _TSX_SUFFIX).parse(text.encode("utf-8"))
    if tree.root_node.has_error:
        raise TypeScriptParseError("the syntax tree contains an error node")
    lines = physical_lines(text)
    found: list[FunctionLength] = []
    pending = [tree.root_node]
    while pending:
        node = pending.pop()
        if _is_counted(node):
            start = _start_row(node) + 1
            found.append(
                FunctionLength(
                    path=path,
                    qualified_name=_name(node),
                    start_line=start,
                    length=count_non_blank_span(lines, start, node.end_point.row + 1),
                )
            )
        pending.extend(reversed(node.children))
    return found


def measure_typescript_lengths(ctx: AdapterContext, files: Sequence[str]) -> list[Measurement]:
    """File length and function length for *files* (no external tool, no Node)."""
    return measure_length_metrics(
        ctx.repo_root,
        files,
        SourceLanguage.TYPESCRIPT,
        tree_sitter_tool_identity(),
        ctx.limits,
        _extract_functions,
        (TypeScriptParseError, MemoryError),
    )
