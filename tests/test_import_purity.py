"""Importing squadron must not read the home directory or ``.env``.

Module-level ``Path.home()`` is bound before any test fixture runs, so a
per-test ``HOME`` cannot reach it; module-level ``load_dotenv`` puts the
working directory's credentials into every importer's environment. Both are
fine inside a function body, which runs at call time.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "squadron"


def _module_level_calls(tree: ast.Module) -> Iterator[ast.Call]:
    """Yield calls evaluated at import: top level, class bodies, defaults, decorators."""
    stack: list[ast.AST] = list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            # The body runs at call time; defaults and decorators run at import.
            stack.extend(node.args.defaults)
            stack.extend(d for d in node.args.kw_defaults if d is not None)
            if not isinstance(node, ast.Lambda):
                stack.extend(node.decorator_list)
            continue
        if isinstance(node, ast.Call):
            yield node
        stack.extend(ast.iter_child_nodes(node))


def _is_forbidden(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr == "home":
        owner = func.value
        return (isinstance(owner, ast.Name) and owner.id == "Path") or (
            isinstance(owner, ast.Attribute) and owner.attr == "Path"
        )
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
    return name == "load_dotenv"


def _violations(source: str, filename: str) -> list[str]:
    tree = ast.parse(source, filename=filename)
    return [
        f"{filename}:{call.lineno}: {ast.unparse(call)}"
        for call in _module_level_calls(tree)
        if _is_forbidden(call)
    ]


def test_src_has_no_import_time_home_or_dotenv() -> None:
    found: list[str] = []
    for module in sorted(SRC_ROOT.rglob("*.py")):
        found.extend(_violations(module.read_text(), str(module.relative_to(SRC_ROOT))))
    assert not found, "Import-time Path.home()/load_dotenv — make these call-time:\n" + "\n".join(found)


@pytest.mark.parametrize(
    "source",
    [
        "from pathlib import Path\nX = Path.home() / '.config'\n",
        "import pathlib\nX = pathlib.Path.home()\n",
        "from pathlib import Path\nclass C:\n    home = Path.home()\n",
        "from pathlib import Path\ndef f(p=Path.home()):\n    return p\n",
        "from pathlib import Path\ndef f(*, p=str(Path.home())):\n    return p\n",
        "from dotenv import load_dotenv\nload_dotenv()\n",
        "import dotenv\nif True:\n    dotenv.load_dotenv('.env')\n",
    ],
)
def test_scanner_flags_import_time_calls(source: str) -> None:
    assert _violations(source, "sample.py")


@pytest.mark.parametrize(
    "source",
    [
        "from pathlib import Path\ndef f():\n    return Path.home()\n",
        "from pathlib import Path\nclass C:\n    def m(self):\n        return Path.home()\n",
        "from pathlib import Path\nf = lambda: Path.home()\n",
        "from dotenv import load_dotenv\ndef main():\n    load_dotenv()\n",
    ],
)
def test_scanner_allows_call_time_calls(source: str) -> None:
    assert _violations(source, "sample.py") == []
