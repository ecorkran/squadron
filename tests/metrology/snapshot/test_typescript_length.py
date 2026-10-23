"""TypeScript adapter: tree-sitter length (slice 400, D5, D6)."""

from __future__ import annotations

import logging
from pathlib import Path
from textwrap import dedent

import pytest

from squadron.metrology.snapshot.typescript_adapter import TypeScriptAdapter
from squadron.metrology.snapshot.typescript_length import measure_typescript_lengths
from squadron.metrology.snapshot_models import Measurement, SnapshotMetric, SourceLanguage
from tests.metrology.snapshot.builders import make_context
from tests.metrology.snapshot.conftest import FakeToolRunner


def measure(
    repo: Path, files: dict[str, str | bytes], *, max_function: int | None = 1
) -> dict[SnapshotMetric, Measurement]:
    """Write *files* and measure them. Every function here is 2+ lines, so limit 1 lists all."""
    for name, content in files.items():
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(dedent(content), encoding="utf-8")
    ctx = make_context(repo, FakeToolRunner(), max_function=max_function)
    return {m.metric: m for m in measure_typescript_lengths(ctx, list(files))}


def functions(measured: dict[SnapshotMetric, Measurement], path: str) -> dict[str, int]:
    rows = measured[SnapshotMetric.FUNCTION_LENGTH].over_limit
    return {row.qualified_name: row.length for row in rows if row.path == path}


def test_adapter_declares_length_and_the_typescript_conventions() -> None:
    adapter = TypeScriptAdapter()

    assert adapter.language is SourceLanguage.TYPESCRIPT
    assert SnapshotMetric.TYPE_ERRORS not in adapter.metrics
    assert adapter.convention_exclusions == ("**/*.d.ts", "**/node_modules/**", "**/dist/**")


def test_each_counted_node_kind(tmp_path: Path) -> None:
    source = """\
        export function declared(): number {
          return 1;
        }
        function* generated() {
          yield 1;
        }
        const assigned = function () {
          return 2;
        };
        const named = function inner() {
          return 3;
        };
        const arrow = () => {
          return 4;
        };
        class Box {
          constructor(private x: number) {
            this.x = x;
          }
          get value() {
            return this.x;
          }
          set value(next: number) {
            this.x = next;
          }
          method(): number {
            return 5;
          }
          async *stream() {
            yield 6;
          }
        }
    """
    measured = measure(tmp_path, {"a.ts": source})

    names = functions(measured, "a.ts")
    assert set(names) == {
        "declared",
        "generated",
        "assigned",
        "inner",
        "arrow",
        "constructor",
        "value",
        "method",
        "stream",
    }
    assert names["declared"] == 3
    assert names["constructor"] == 3


def test_expression_bodied_arrow_is_skipped(tmp_path: Path) -> None:
    source = """\
        const double = (x: number) => x * 2;
        const block = (x: number) => {
          return x;
        };
    """
    measured = measure(tmp_path, {"a.ts": source})

    assert set(functions(measured, "a.ts")) == {"block"}
    distribution = measured[SnapshotMetric.FUNCTION_LENGTH].distribution
    assert distribution is not None
    assert distribution.count == 1


def test_signatures_without_a_body_are_skipped(tmp_path: Path) -> None:
    source = """\
        function over(a: string): string;
        function over(a: number): number;
        function over(a: any): any {
          return a;
        }
        interface Shape {
          area(): number;
        }
        abstract class Base {
          abstract run(): void;
        }
        declare function external(): void;
    """
    measured = measure(tmp_path, {"a.ts": source})

    assert functions(measured, "a.ts") == {"over": 3}


def test_names_come_from_the_node_declarator_property_or_field(tmp_path: Path) -> None:
    source = """\
        const holder = {
          shorthand() {
            return 1;
          },
          pair: () => {
            return 2;
          },
          expr: function () {
            return 3;
          },
        };
        class Widget {
          handler = () => {
            return 4;
          };
        }
        [1].forEach((x) => {
          console.log(x);
        });
    """
    measured = measure(tmp_path, {"a.ts": source})

    assert sorted(functions(measured, "a.ts")) == [
        "<anonymous>",
        "expr",
        "handler",
        "pair",
        "shorthand",
    ]


def test_decorated_method_spans_from_its_first_decorator(tmp_path: Path) -> None:
    source = """\
        class Service {
          @Log()

          @Cache()
          fetch(): void {
            return;
          }
        }
    """
    measured = measure(tmp_path, {"a.ts": source})

    row = measured[SnapshotMetric.FUNCTION_LENGTH].over_limit[0]
    assert (row.qualified_name, row.start_line, row.length) == ("fetch", 2, 5)


def test_nested_function_counts_on_its_own_and_inside_its_parent(tmp_path: Path) -> None:
    source = """\
        function parent() {
          const x = 1;
          function child() {
            return x;
          }
          return child;
        }
    """
    measured = measure(tmp_path, {"a.ts": source})

    assert functions(measured, "a.ts") == {"parent": 7, "child": 3}


def test_tsx_with_jsx_parses(tmp_path: Path) -> None:
    source = """\
        export function View() {
          const items = [1, 2].map((n) => {
            return <li key={n}>{n}</li>;
          });
          return <ul>{items}</ul>;
        }
    """
    measured = measure(tmp_path, {"view.tsx": source})

    assert measured[SnapshotMetric.FUNCTION_LENGTH].unparsed_files == []
    assert set(functions(measured, "view.tsx")) == {"View", "<anonymous>"}


def test_file_length_counts_non_blank_lines_and_the_limit(tmp_path: Path) -> None:
    measured = measure(tmp_path, {"a.ts": "const a = 1;\n\n\nconst b = 2;\n"}, max_function=None)

    assert measured[SnapshotMetric.FILE_LENGTH].per_file == {"a.ts": 2}
    assert measured[SnapshotMetric.FUNCTION_LENGTH].distribution is None


def test_syntax_error_file_keeps_file_length_and_is_listed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        measured = measure(
            tmp_path, {"bad.ts": "function f( {\n  return ;\n", "ok.ts": "const a = 1;\n"}
        )

    assert measured[SnapshotMetric.FILE_LENGTH].per_file == {"bad.ts": 2, "ok.ts": 1}
    assert measured[SnapshotMetric.FUNCTION_LENGTH].unparsed_files == ["bad.ts"]
    assert any("bad.ts" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)


def test_undecodable_bytes_keep_file_length_and_are_listed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        measured = measure(tmp_path, {"latin.ts": b"const a = '\xff\xfe';\nconst b = 2;\n"})

    assert measured[SnapshotMetric.FILE_LENGTH].per_file == {"latin.ts": 2}
    assert measured[SnapshotMetric.FUNCTION_LENGTH].unparsed_files == ["latin.ts"]
    assert any("latin.ts" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)


def test_tool_identity_names_the_parser_and_grammar_versions(tmp_path: Path) -> None:
    measured = measure(tmp_path, {"a.ts": "const a = 1;\n"})

    tool = measured[SnapshotMetric.FILE_LENGTH].tool
    assert tool is not None
    assert tool.name == "squadron-tree-sitter-ts"
    assert "tree-sitter0.26" in tool.version
    assert "tree-sitter-typescript0.23" in tool.version
