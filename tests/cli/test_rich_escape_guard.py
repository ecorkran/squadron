"""Guard: exception text interpolated into Rich output must be escaped (#177).

Rich treats ``[codex]`` in an f-string as markup and silently drops it. Any
f-string passed to ``rprint`` / ``.print`` that interpolates a name bound by an
enclosing ``except ... as <name>`` must wrap that expression in ``escape(...)``.
"""

import ast
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CLI_DIR = _REPO_ROOT / "src" / "squadron" / "cli"
_PRINT_FUNCTION_NAME = "rprint"
_PRINT_METHOD_NAME = "print"
_ESCAPE_NAME = "escape"


def _is_print_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == _PRINT_FUNCTION_NAME
    return isinstance(func, ast.Attribute) and func.attr == _PRINT_METHOD_NAME


def _is_escape_call(node: ast.expr) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == _ESCAPE_NAME
    return isinstance(func, ast.Attribute) and func.attr == _ESCAPE_NAME


def _references(node: ast.expr, names: set[str]) -> bool:
    return any(isinstance(n, ast.Name) and n.id in names for n in ast.walk(node))


class _UnescapedSiteFinder(ast.NodeVisitor):
    """Collect line numbers of unescaped exception-bound names in Rich prints."""

    def __init__(self) -> None:
        self.lines: list[int] = []
        self._exception_names: list[str] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name is None:
            self.generic_visit(node)
            return
        self._exception_names.append(node.name)
        try:
            self.generic_visit(node)
        finally:
            self._exception_names.pop()

    def visit_Call(self, node: ast.Call) -> None:
        if self._exception_names and _is_print_call(node):
            for arg in node.args:
                if isinstance(arg, ast.JoinedStr):
                    self._check_fstring(arg)
        self.generic_visit(node)

    def _check_fstring(self, fstring: ast.JoinedStr) -> None:
        names = set(self._exception_names)
        for part in fstring.values:
            if not isinstance(part, ast.FormattedValue):
                continue
            if _is_escape_call(part.value):
                continue
            if _references(part.value, names):
                self.lines.append(part.value.lineno)


def find_unescaped_sites(source: str) -> list[int]:
    """Return line numbers of unescaped exception interpolations in ``source``."""
    finder = _UnescapedSiteFinder()
    finder.visit(ast.parse(source))
    return sorted(finder.lines)


def _flagged_sites() -> dict[str, list[int]]:
    flagged: dict[str, list[int]] = {}
    for path in sorted(_CLI_DIR.rglob("*.py")):
        lines = find_unescaped_sites(path.read_text(encoding="utf-8"))
        if lines:
            flagged[path.relative_to(_REPO_ROOT).as_posix()] = lines
    return flagged


# Files not yet swept; shrinks as Tasks 3-8 proceed and is deleted at the end.
_UNSWEPT: set[str] = {
    "src/squadron/cli/commands/spawn.py",
}


def test_no_unescaped_exception_text_outside_unswept_files() -> None:
    offenders = {rel: lines for rel, lines in _flagged_sites().items() if rel not in _UNSWEPT}
    assert not offenders, "Unescaped exception text in Rich output (wrap in escape()): " + "; ".join(
        f"{rel}:{line}" for rel, lines in offenders.items() for line in lines
    )


def test_unswept_files_still_have_flagged_sites() -> None:
    flagged = _flagged_sites()
    clean = sorted(rel for rel in _UNSWEPT if rel not in flagged)
    assert not clean, f"Remove from _UNSWEPT (no flagged sites left): {clean}"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "try:\n    pass\nexcept ValueError as exc:\n    rprint(f'bad: {exc}')\n",
            [4],
        ),
        (
            "try:\n    pass\nexcept ValueError as exc:\n    rprint(f'bad: {escape(str(exc))}')\n",
            [],
        ),
        (
            "try:\n    pass\nexcept OSError as problem:\n    console.print(f'bad: {problem}')\n",
            [4],
        ),
        (
            "try:\n    pass\nexcept OSError as e:\n"
            "    rprint(\n        f'one '\n        f'two {e}'\n    )\n",
            [6],
        ),
        (
            "try:\n    pass\nexcept OSError as e:\n    typer.echo(f'bad: {e}')\n",
            [],
        ),
        (
            "x = 1\nrprint(f'plain {x}')\n",
            [],
        ),
    ],
    ids=["unescaped", "escaped", "other-name", "multi-line", "typer-echo", "no-except"],
)
def test_checker_flags_exactly_unescaped_sites(source: str, expected: list[int]) -> None:
    assert find_unescaped_sites(source) == expected
