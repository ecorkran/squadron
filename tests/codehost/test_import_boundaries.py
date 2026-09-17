"""The import direction the architecture fixes: ``cli -> codehost -> core``.

Walked from the source rather than asserted in prose, because an import added
in a hurry is exactly the kind of thing a reviewer does not notice and a test
does. ``codehost`` must stay independent of the review engine, the CLI, the
pipeline, and the providers; ``review`` must not learn about ``codehost``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_SRC = Path(__file__).parent.parent.parent / "src" / "squadron"

#: What no module under ``codehost`` may import.
_FORBIDDEN_FROM_CODEHOST = (
    "squadron.review",
    "squadron.cli",
    "squadron.pipeline",
    "squadron.providers",
)

#: And the reverse direction: the review engine must not depend on the adapter.
_FORBIDDEN_FROM_REVIEW = ("squadron.codehost",)

#: The one permitted exception (384, D2): ``pr_comment.py`` takes a
#: ``PullRequestRecord`` — a frozen dataclass carrying no host behavior — so
#: the composer can build a body without the review package learning the
#: host's other shapes. No other ``codehost`` symbol is exempt.
_PERMITTED_REVIEW_IMPORT = "squadron.codehost.models"


def _imported_modules(path: Path) -> set[str]:
    """Every module name imported by ``path``, including ``from`` targets."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


def _imported_names_from(path: Path, module: str) -> set[str]:
    """Names imported via ``from <module> import ...`` in ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module and node.level == 0:
            found.update(alias.name for alias in node.names)
    return found


def _python_files(package: str) -> list[Path]:
    files = sorted((_SRC / package).rglob("*.py"))
    assert files, f"expected python files under {package}"
    return files


@pytest.mark.parametrize("path", _python_files("codehost"), ids=lambda p: p.name)
def test_codehost_does_not_import_upward(path: Path) -> None:
    for imported in _imported_modules(path):
        for forbidden in _FORBIDDEN_FROM_CODEHOST:
            assert not imported.startswith(forbidden), (
                f"{path.name} imports {imported}; codehost must not depend on "
                f"{forbidden} — the direction is cli -> codehost -> core"
            )


@pytest.mark.parametrize("path", _python_files("review"), ids=lambda p: p.name)
def test_review_does_not_import_codehost(path: Path) -> None:
    for imported in _imported_modules(path):
        for forbidden in _FORBIDDEN_FROM_REVIEW:
            if not imported.startswith(forbidden):
                continue
            if path.name == "pr_comment.py" and imported == _PERMITTED_REVIEW_IMPORT:
                # 384, D2: the one exception, checked precisely below rather
                # than merely allowed through here.
                continue
            raise AssertionError(
                f"{path.name} imports {imported}; the review engine must not "
                "depend on the code-host adapter"
            )


def test_pr_comment_imports_only_pull_request_record() -> None:
    """The one exception is exactly one symbol, from exactly one module (D2).

    A looser exception here would let ``pr_comment.py`` grow a dependency on
    ``HostComment`` or the error taxonomy without this guard noticing.
    """
    path = _SRC / "review" / "pr_comment.py"
    names = _imported_names_from(path, _PERMITTED_REVIEW_IMPORT)
    assert names == {"PullRequestRecord"}, (
        f"pr_comment.py imports {names} from {_PERMITTED_REVIEW_IMPORT}; "
        "only PullRequestRecord is permitted"
    )


def test_codehost_may_import_core() -> None:
    """The permitted direction, asserted so the test above cannot pass vacuously."""
    imports = _imported_modules(_SRC / "codehost" / "github_cli.py")
    assert any(name.startswith("squadron.core") for name in imports), (
        "github_cli.py should import squadron.core — if this fails the walker "
        "is not seeing imports and the prohibitions above prove nothing"
    )
