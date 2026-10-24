"""TypeScript duplication through tree-sitter leaf tokens (slice 401, D3)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.metrology.snapshot import duplication
from squadron.metrology.snapshot.python_adapter import measure_python_duplication
from squadron.metrology.snapshot.typescript_length import measure_typescript_duplication
from squadron.metrology.snapshot_models import AbsenceReason, Measurement
from tests.metrology.snapshot.builders import make_context
from tests.metrology.snapshot.conftest import FakeToolRunner

STATEMENTS = 20  # nine tokens each: well over the 100-token window


def function_source(name: str, comment: str) -> str:
    body = [f"  const value_{i} = compute({i}, {i + 1}); // {comment}" for i in range(STATEMENTS)]
    return f"// {comment}\nexport function {name}() {{\n" + "\n".join(body) + "\n}\n"


def jsx_source(comment: str) -> str:
    items = [f'      <li key="k{i}">{{label_{i}}}</li>' for i in range(STATEMENTS)]
    return (
        f"// {comment}\nexport function View() {{\n  return (\n    <ul>\n"
        + "\n".join(items)
        + "\n    </ul>\n  );\n}\n"
    )


def measure(repo: Path, files: dict[str, str]) -> Measurement:
    for name, content in files.items():
        (repo / name).write_text(content, encoding="utf-8")
    ctx = make_context(repo, FakeToolRunner())
    return measure_typescript_duplication(ctx, list(files))


def test_shared_block_is_reported_in_both_files_despite_different_comments(tmp_path: Path) -> None:
    measured = measure(
        tmp_path,
        {
            "a.ts": function_source("same", "first"),
            "b.ts": function_source("same", "a different comment"),
        },
    )

    assert measured.per_file == {"a.ts": STATEMENTS + 2, "b.ts": STATEMENTS + 2}
    assert measured.tool is not None
    assert measured.tool.name == "squadron-tree-sitter-ts"
    assert "type-1" in measured.tool.counting


def test_tsx_files_with_a_shared_jsx_block_are_reported(tmp_path: Path) -> None:
    measured = measure(tmp_path, {"a.tsx": jsx_source("one"), "b.tsx": jsx_source("two")})

    assert measured.unparsed_files == []
    assert set(measured.per_file) == {"a.tsx", "b.tsx"}
    assert all(count >= STATEMENTS for count in measured.per_file.values())


def test_syntax_error_file_is_unparsed_with_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        measured = measure(tmp_path, {"broken.ts": "export function broken( {\n"})

    assert measured.unparsed_files == ["broken.ts"]
    assert "Can't tokenize broken.ts" in caplog.text


def test_ceiling_fails_duplication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(duplication, "DUPLICATION_MAX_TOKENS", 10)

    measured = measure(tmp_path, {"a.ts": function_source("same", "c")})

    assert measured.absent is AbsenceReason.TOOL_FAILED


def test_languages_are_never_compared_with_each_other(tmp_path: Path) -> None:
    # The same token text in both languages; each adapter sees only its own files.
    shared = "\n".join(f"const value_{i} = compute({i}, {i + 1});" for i in range(STATEMENTS)) + "\n"
    (tmp_path / "a.py").write_text(shared, encoding="utf-8")
    (tmp_path / "a.ts").write_text(shared, encoding="utf-8")
    ctx = make_context(tmp_path, FakeToolRunner())

    assert measure_python_duplication(ctx, ["a.py"]).per_file == {}
    assert measure_typescript_duplication(ctx, ["a.ts"]).per_file == {}
