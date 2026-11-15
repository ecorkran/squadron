"""A conftest that does not parse names the tree it came from (slice 425 review F006)."""

from __future__ import annotations

import logging

import pytest

from squadron.benchmark.python_injection import (
    REFERENCE_TREE,
    START_TREE,
    _added_imports,  # pyright: ignore[reportPrivateUsage]
)
from squadron.benchmark.tree_reader import TreeReadError

CONFTEST = "conftest.py"
VALID = "import os\n"
BROKEN = "def (:\n"


class _OneFile:
    """A tree holding a single conftest."""

    def __init__(self, text: str) -> None:
        self._text = text

    def read(self, path: str) -> bytes:
        return self._text.encode("utf-8")

    def list_paths(self) -> tuple[str, ...]:
        return (CONFTEST,)


@pytest.mark.parametrize(
    ("start_text", "reference_text", "tree_name"),
    [(BROKEN, VALID, START_TREE), (VALID, BROKEN, REFERENCE_TREE)],
)
def test_a_parse_failure_names_the_tree_it_came_from(
    start_text: str,
    reference_text: str,
    tree_name: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    start, reference = _OneFile(start_text), _OneFile(reference_text)
    paths = frozenset({CONFTEST})
    with caplog.at_level(logging.ERROR), pytest.raises(TreeReadError, match=tree_name) as caught:
        _added_imports(CONFTEST, start, paths, reference, paths)  # type: ignore[arg-type]
    assert tree_name in caught.value.action
    assert any(tree_name in record.getMessage() for record in caplog.records)
