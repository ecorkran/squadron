"""Python language adapter (slice 400).

File and function length come from the stdlib ``ast`` (D6): no dependency, exact
spans through ``end_lineno``, and the measured project's code is parsed, never
imported or executed. Lint and type errors are added by the sibling modules
``python_lint`` and ``python_types``, which this class delegates to.
"""

from __future__ import annotations

import ast
import platform
from collections.abc import Sequence

from squadron import __version__
from squadron.metrology.snapshot.contract import AdapterContext
from squadron.metrology.snapshot.lengths import (
    FunctionLength,
    count_non_blank_span,
    measure_length_metrics,
    physical_lines,
)
from squadron.metrology.snapshot.python_lint import measure_ruff_lint
from squadron.metrology.snapshot.python_types import measure_pyright_types
from squadron.metrology.snapshot_models import (
    Measurement,
    SnapshotMetric,
    SourceLanguage,
    ToolIdentity,
)

AST_TOOL_NAME = "squadron-python-ast"

_AST_COUNTING = (
    "non-blank physical lines; a function spans its first decorator (or def line) "
    "through its last body line; def and async def at any depth, lambdas excluded"
)

_FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def ast_tool_identity() -> ToolIdentity:
    """The in-process counter as a tool: squadron's version plus the parser's (Python's)."""
    return ToolIdentity(
        name=AST_TOOL_NAME,
        version=f"{__version__}+python{platform.python_version()}",
        counting=_AST_COUNTING,
    )


def _span_start(node: _FunctionNode) -> int:
    decorator_lines = [decorator.lineno for decorator in node.decorator_list]
    return min([node.lineno, *decorator_lines])


def _collect_functions(
    tree: ast.AST, path: str, lines: Sequence[str], prefix: str = ""
) -> list[FunctionLength]:
    """Every def and async def at any depth, named like ``__qualname__``."""
    found: list[FunctionLength] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            found.extend(_collect_functions(node, path, lines, f"{prefix}{node.name}."))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = _span_start(node)
            end = node.end_lineno if node.end_lineno is not None else node.lineno
            found.append(
                FunctionLength(
                    path=path,
                    qualified_name=f"{prefix}{node.name}",
                    start_line=start,
                    length=count_non_blank_span(lines, start, end),
                )
            )
            found.extend(_collect_functions(node, path, lines, f"{prefix}{node.name}.<locals>."))
        else:
            found.extend(_collect_functions(node, path, lines, prefix))
    return found


_PARSE_ERRORS: tuple[type[Exception], ...] = (SyntaxError, RecursionError, MemoryError, ValueError)


def _extract_functions(path: str, text: str) -> list[FunctionLength]:
    return _collect_functions(ast.parse(text, filename=path), path, physical_lines(text))


def measure_lengths(ctx: AdapterContext, files: Sequence[str]) -> list[Measurement]:
    """File length and function length for *files* (no external tool)."""
    return measure_length_metrics(
        ctx.repo_root,
        files,
        SourceLanguage.PYTHON,
        ast_tool_identity(),
        ctx.limits,
        _extract_functions,
        _PARSE_ERRORS,
    )


class PythonAdapter:
    """Measures Python: all four metrics."""

    language = SourceLanguage.PYTHON
    metrics = frozenset(SnapshotMetric)
    convention_exclusions: tuple[str, ...] = ("**/*_pb2.py", "**/*_pb2_grpc.py")

    def measure(self, ctx: AdapterContext, files: Sequence[str]) -> list[Measurement]:
        listed = list(files)
        return [
            *measure_lengths(ctx, listed),
            measure_ruff_lint(ctx, listed),
            measure_pyright_types(ctx, listed),
        ]
