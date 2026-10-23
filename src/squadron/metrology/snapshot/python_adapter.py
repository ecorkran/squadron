"""Python language adapter (slice 400).

File and function length come from the stdlib ``ast`` (D6): no dependency, exact
spans through ``end_lineno``, and the measured project's code is parsed, never
imported or executed. Lint and type errors are added by the sibling modules
``python_lint`` and ``python_types``, which this class delegates to.
"""

from __future__ import annotations

import ast
import logging
import platform
from collections.abc import Sequence

from squadron import __version__
from squadron.metrology.snapshot.contract import AdapterContext
from squadron.metrology.snapshot.lengths import (
    FunctionLength,
    count_non_blank,
    count_non_blank_span,
    file_length_measurement,
    function_length_measurement,
    physical_lines,
)
from squadron.metrology.snapshot.python_lint import measure_ruff_lint
from squadron.metrology.snapshot_models import (
    Measurement,
    SnapshotMetric,
    SourceLanguage,
    ToolIdentity,
)

_logger = logging.getLogger(__name__)

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


def _measure_file(
    ctx: AdapterContext,
    path: str,
    per_file: dict[str, int],
    functions: list[FunctionLength],
    unparsed: list[str],
) -> None:
    try:
        raw = (ctx.repo_root / path).read_bytes()
    except OSError as exc:
        _logger.warning("Can't read %s for length (%s); not measured", path, exc)
        unparsed.append(path)
        return
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        # Still counts for file length (with replacement characters); it just
        # contributes no functions.
        _logger.warning("%s isn't valid UTF-8 (%s); no functions measured", path, exc)
        per_file[path] = count_non_blank(raw.decode("utf-8", errors="replace"))
        unparsed.append(path)
        return
    per_file[path] = count_non_blank(text)
    try:
        tree = ast.parse(text, filename=path)
        functions.extend(_collect_functions(tree, path, physical_lines(text)))
    except (SyntaxError, RecursionError, MemoryError, ValueError) as exc:
        # A file this interpreter can't parse (newer syntax, pathological nesting,
        # NUL bytes) keeps its file length and contributes no functions; it's
        # listed so the gap is visible.
        _logger.warning("Can't parse %s (%s: %s); no functions measured", path, type(exc).__name__, exc)
        unparsed.append(path)


def measure_lengths(ctx: AdapterContext, files: Sequence[str]) -> list[Measurement]:
    """File length and function length for *files* (no external tool)."""
    tool = ast_tool_identity()
    per_file: dict[str, int] = {}
    functions: list[FunctionLength] = []
    unparsed: list[str] = []
    for path in files:
        _measure_file(ctx, path, per_file, functions, unparsed)
    return [
        file_length_measurement(SourceLanguage.PYTHON, tool, per_file, ctx.limits.max_file_lines),
        function_length_measurement(
            SourceLanguage.PYTHON, tool, functions, ctx.limits.max_function_lines, unparsed
        ),
    ]


class PythonAdapter:
    """Measures Python: file length, function length and ruff lint count."""

    language = SourceLanguage.PYTHON
    metrics = frozenset(
        {SnapshotMetric.FILE_LENGTH, SnapshotMetric.FUNCTION_LENGTH, SnapshotMetric.LINT_COUNT}
    )
    convention_exclusions = ("**/*_pb2.py", "**/*_pb2_grpc.py")

    def measure(self, ctx: AdapterContext, files: Sequence[str]) -> list[Measurement]:
        return [*measure_lengths(ctx, files), measure_ruff_lint(ctx, list(files))]
