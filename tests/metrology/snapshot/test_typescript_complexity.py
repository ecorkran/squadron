"""TypeScript cyclomatic complexity: one case per decision node and operator (slice 401, D2)."""

from __future__ import annotations

import pytest
import tree_sitter

from squadron.metrology.snapshot.typescript_complexity import (
    COMPLEXITY_COUNTING,
    DECISION_NODE_TYPES,
    SHORT_CIRCUIT_OPERATORS,
    typescript_complexity,
)
from squadron.metrology.snapshot.typescript_length import (  # pyright: ignore[reportPrivateUsage]
    _is_counted,
    _name,
    _parser,
)


def scores(source: str, *, tsx: bool = False) -> dict[str, int]:
    """Function name -> complexity, for every counted function in *source*."""
    tree = _parser(tsx).parse(source.encode("utf-8"))
    assert not tree.root_node.has_error
    found: dict[str, int] = {}
    pending: list[tree_sitter.Node] = [tree.root_node]
    while pending:
        node = pending.pop()
        if _is_counted(node):
            found[_name(node)] = typescript_complexity(node, _is_counted)
        pending.extend(node.children)
    return found


def score(body: str) -> int:
    return scores(f"function f(a: any, b: any) {{\n  {body}\n}}\n")["f"]


def test_body_with_no_decisions_scores_one() -> None:
    assert score("return 1;") == 1


@pytest.mark.parametrize(
    "body",
    [
        "if (a) { return 1; }",
        "for (let i = 0; i < 1; i++) { a(); }",
        "for (const x of a) { b(); }",
        "for (const k in a) { b(); }",
        "while (a) { b(); }",
        "do { b(); } while (a);",
        "switch (a) { case 1: break; }",
        "try { a(); } catch (e) { b(); }",
        "return a ? 1 : 2;",
        "return a && b;",
        "return a || b;",
        "return a ?? b;",
    ],
)
def test_each_decision_point_scores_two(body: str) -> None:
    assert score(body) == 2


def test_every_decision_node_type_is_covered_by_a_case() -> None:
    # for…of and for…in both parse as for_in_statement.
    assert len(DECISION_NODE_TYPES) == 8
    assert SHORT_CIRCUIT_OPERATORS == {"&&", "||", "??"}


def test_other_binary_operators_add_nothing() -> None:
    assert score("return a + b < 3;") == 1


def test_switch_with_two_cases_and_a_default_scores_three() -> None:
    assert score("switch (a) { case 1: break; case 2: break; default: break; }") == 3


def test_success_criterion_fixture() -> None:
    body = (
        "if (a) { b(); }\n  const c = a ?? b;\n  const d = a ? 1 : 2;\n"
        "  switch (a) { case 1: break; case 2: break; default: break; }"
    )
    assert score(body) == 6


def test_nested_block_arrow_is_scored_on_its_own() -> None:
    result = scores(
        "function f(a: any) {\n  const g = () => {\n    if (a) { return 1; }\n    return 2;\n  };\n}\n"
    )
    assert result == {"f": 1, "g": 2}


def test_expression_bodied_arrow_counts_toward_the_enclosing_function() -> None:
    assert scores("function f(a: any) {\n  return [1].map((x) => (a ? x : 0));\n}\n") == {"f": 2}


def test_ternary_inside_jsx_in_a_tsx_file() -> None:
    source = "function View(p: any) {\n  return <div>{p.on ? <b /> : <i />}</div>;\n}\n"
    assert scores(source, tsx=True) == {"View": 2}


def test_counting_text_names_the_decision_nodes_and_operators() -> None:
    for name in DECISION_NODE_TYPES | SHORT_CIRCUIT_OPERATORS:
        assert name in COMPLEXITY_COUNTING
