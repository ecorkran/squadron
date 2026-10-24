"""Python cyclomatic complexity: one case per decision point (slice 401, D2)."""

from __future__ import annotations

import ast
import textwrap

import pytest

from squadron.metrology.snapshot.python_complexity import (
    COMPLEXITY_COUNTING,
    DECISION_NODES,
    python_complexity,
)


def score(source: str, name: str = "f") -> int:
    tree = ast.parse(textwrap.dedent(source))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return python_complexity(node)
    raise AssertionError(f"no function {name!r} in source")


def test_body_with_no_decisions_scores_one() -> None:
    assert score("def f():\n    return 1\n") == 1


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("if x:\n        pass", 2),
        ("if x:\n        pass\n    elif y:\n        pass", 3),
        ("for i in x:\n        pass", 2),
        ("while x:\n        pass", 2),
        ("return 1 if x else 2", 2),
        ("try:\n        pass\n    except ValueError:\n        pass", 2),
        ("return x and y", 2),
        ("return x and y and z", 3),
        ("return [i for i in x]", 2),
        ("return [i for i in x if i]", 3),
        ("match x:\n        case 1:\n            pass\n        case _:\n            pass", 3),
    ],
)
def test_each_decision_point_adds_to_the_score(body: str, expected: int) -> None:
    assert score(f"def f(x, y=None, z=None):\n    {body}\n") == expected


def test_async_for_and_async_def_are_scored() -> None:
    source = "async def f(x):\n    async for i in x:\n        pass\n"
    assert score(source) == 2


@pytest.mark.parametrize(
    "body",
    [
        "try:\n        pass\n    except ValueError:\n        pass\n    else:\n        pass",
        "with x:\n        pass",
        "assert x",
    ],
)
def test_try_with_assert_and_else_add_nothing_beyond_handlers(body: str) -> None:
    expected = 2 if "except" in body else 1
    assert score(f"def f(x):\n    {body}\n") == expected


def test_success_criterion_fixture() -> None:
    source = """
    def f(a, b, items):
        if a:
            pass
        elif b and a:
            pass
        values = [i for i in items if i]
        try:
            pass
        except ValueError:
            pass
    """
    # D2 counts a comprehension's `for` as well as its `if`:
    # 1 + if + elif + and + comprehension for + comprehension if + except
    assert score(source) == 7


def test_nested_def_is_scored_on_its_own() -> None:
    source = """
    def f():
        def inner(x):
            if x:
                pass
            if x:
                pass
    """
    assert score(source) == 1
    assert score(source, "inner") == 3


def test_lambda_decisions_count_toward_the_enclosing_function() -> None:
    assert score("def f(x):\n    return lambda y: 1 if y else 2\n") == 2


def test_counting_text_names_every_decision_node() -> None:
    for node in DECISION_NODES:
        assert node.__name__ in COMPLEXITY_COUNTING
    assert "module-level code is not in any function" in COMPLEXITY_COUNTING
