"""TypeScript cyclomatic complexity for one tree-sitter function node (slice 401, D2).

McCabe: 1 plus the decision points in the function's own body. A nested counted
function is scored on its own; an expression-bodied arrow isn't counted, so its
decisions belong to the enclosing function. The node names were checked against the
pinned grammar for both ``typescript`` and ``tsx``.
"""

from __future__ import annotations

from collections.abc import Callable

import tree_sitter

#: Node types that each add one decision point. ``switch_default`` is not in it.
DECISION_NODE_TYPES = frozenset(
    {
        "if_statement",
        "for_statement",
        "for_in_statement",
        "while_statement",
        "do_statement",
        "switch_case",
        "catch_clause",
        "ternary_expression",
    }
)

#: Short-circuit operators: a ``binary_expression`` using one adds a decision point.
SHORT_CIRCUIT_OPERATORS = frozenset({"&&", "||", "??"})

_BINARY = "binary_expression"

#: The ``counting`` text for the complexity measurement, built from the constants above.
COMPLEXITY_COUNTING = (
    "McCabe cyclomatic complexity per function: 1 plus decision points ("
    + ", ".join(sorted(DECISION_NODE_TYPES))
    + "; binary_expression with "
    + ", ".join(sorted(SHORT_CIRCUIT_OPERATORS))
    + "); nested functions are scored on their own and expression-bodied arrows "
    "count toward the enclosing function; switch_default adds nothing; "
    "module-level code is not in any function and is not counted"
)


def _is_decision(node: tree_sitter.Node) -> bool:
    if node.type in DECISION_NODE_TYPES:
        return True
    if node.type != _BINARY:
        return False
    operator = node.child_by_field_name("operator")
    return operator is not None and operator.type in SHORT_CIRCUIT_OPERATORS


def typescript_complexity(
    function: tree_sitter.Node, is_counted: Callable[[tree_sitter.Node], bool]
) -> int:
    """Cyclomatic complexity of *function*; *is_counted* says which nested nodes are functions."""
    score = 1
    pending = list(function.children)
    while pending:
        node = pending.pop()
        if is_counted(node):
            continue
        if _is_decision(node):
            score += 1
        pending.extend(node.children)
    return score
