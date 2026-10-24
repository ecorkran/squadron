"""Python cyclomatic complexity for one function node (slice 401, D2).

McCabe: 1 plus the decision points in the function's own body. Decision points inside a
nested def belong to that def, never to the function it sits in; a lambda has no score
of its own, so its decisions belong to the enclosing function.
"""

from __future__ import annotations

import ast

#: Statement and expression nodes that each add one decision point. ``If`` covers
#: ``elif`` (an ``If`` in ``orelse``). ``Try``, ``With``, ``Assert`` and ``else``
#: clauses add nothing.
DECISION_NODES: tuple[type[ast.AST], ...] = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.IfExp,
    ast.ExceptHandler,
    ast.match_case,
)

_NESTED_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)

#: The ``counting`` text for the complexity measurement, built from the constant above.
COMPLEXITY_COUNTING = (
    "McCabe cyclomatic complexity per function: 1 plus decision points ("
    + ", ".join(node.__name__ for node in DECISION_NODES)
    + "; each extra operand of a BoolOp; each for and each if of a comprehension); "
    "nested defs are scored on their own and lambdas count toward the enclosing "
    "function; try, with, assert and else clauses add nothing; "
    "module-level code is not in any function and is not counted"
)


def _decision_points(node: ast.AST) -> int:
    """Decision points in *node* itself, not descending into nested defs."""
    if isinstance(node, DECISION_NODES):
        own = 1
    elif isinstance(node, ast.BoolOp):
        own = len(node.values) - 1
    elif isinstance(node, ast.comprehension):
        own = 1 + len(node.ifs)
    else:
        own = 0
    return own + sum(
        _decision_points(child)
        for child in ast.iter_child_nodes(node)
        if not isinstance(child, _NESTED_FUNCTIONS)
    )


def python_complexity(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Cyclomatic complexity of one def or async def."""
    return 1 + sum(
        _decision_points(child)
        for child in ast.iter_child_nodes(function)
        if not isinstance(child, _NESTED_FUNCTIONS)
    )
