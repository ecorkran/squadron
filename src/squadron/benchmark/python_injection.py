"""Hidden-test injection for Python: a sibling module per hidden test file (slice 425 D3).

For each test file that holds hidden tests, ``test_sqhidden_<stem>.py`` is written beside it.
Its content, in order: the conftest imports the reference added (placed after the file's
docstring and ``from __future__`` imports, which Python requires to come first), the
reference's whole version of the test file, then the source of each hidden fixture whose
``conftest.py`` is on the file's path. Nothing the producer wrote is removed or overwritten.
"""

from __future__ import annotations

import ast
import logging
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath

from squadron.benchmark.grading_adapter import InjectionResult
from squadron.benchmark.tree_reader import TreeReader, TreeReadError
from squadron.metrology.benchmark_models import BenchmarkCase, ConftestFixture

_logger = logging.getLogger(__name__)

CONFTEST_NAME = "conftest.py"
INJECTED_PREFIX = "test_sqhidden_"
NODE_ID_SEPARATOR = "::"
_FUTURE_MODULE = "__future__"
PARAMETER_OPEN = "["


class ClashKind(StrEnum):
    """The kinds of clash an injection records; a clash line is ``<kind>: <detail>``."""

    SAME_TEST_NAME = "same_test_name"
    SAME_FIXTURE_NAME = "same_fixture_name"
    FILENAME_TAKEN = "filename_taken"


def clash(kind: ClashKind, detail: str) -> str:
    """The stable text of one clash, which the report counts by kind."""
    return f"{kind.value}: {detail}"


@dataclass(frozen=True)
class _ImportLine:
    """One top-level import: the text to copy and the names it binds."""

    key: str
    text: str
    bound_names: frozenset[str]


def _parse(source: str, path: str) -> ast.Module:
    try:
        return ast.parse(source)
    except SyntaxError as exc:
        _logger.error("%s at the reference does not parse: %s", path, exc)
        raise TreeReadError(f"parse {path} at the reference", str(exc)) from exc


def _read_text(reader: TreeReader, paths: frozenset[str], path: str) -> str | None:
    return reader.read(path).decode("utf-8") if path in paths else None


def _import_lines(source: str, module: ast.Module) -> list[_ImportLine]:
    lines: list[_ImportLine] = []
    for node in module.body:
        if isinstance(node, ast.ImportFrom) and node.module == _FUTURE_MODULE:
            continue
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        text = ast.get_source_segment(source, node)
        if text is None:
            continue
        names = frozenset(
            alias.asname
            or (alias.name if isinstance(node, ast.ImportFrom) else alias.name.split(".")[0])
            for alias in node.names
        )
        lines.append(_ImportLine(key=ast.unparse(node), text=text, bound_names=names))
    return lines


def _source_lines(source: str, node: ast.stmt) -> str:
    first = min([node.lineno, *(d.lineno for d in getattr(node, "decorator_list", []))])
    last = node.end_lineno or node.lineno
    return "\n".join(source.split("\n")[first - 1 : last])


def _find_fixture(module: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def conftests_on_path(file_path: str) -> list[str]:
    """Every ``conftest.py`` path that applies to *file_path*, outermost first."""
    directory = PurePosixPath(file_path).parent
    chain = [*reversed(directory.parents), directory]
    unique = list(dict.fromkeys(chain))
    return [CONFTEST_NAME if str(parent) == "." else f"{parent}/{CONFTEST_NAME}" for parent in unique]


def _added_imports(
    conftest_path: str,
    start: TreeReader,
    start_paths: frozenset[str],
    reference: TreeReader,
    reference_paths: frozenset[str],
) -> list[_ImportLine]:
    reference_source = _read_text(reference, reference_paths, conftest_path)
    if reference_source is None:
        return []
    reference_lines = _import_lines(reference_source, _parse(reference_source, conftest_path))
    start_source = _read_text(start, start_paths, conftest_path)
    have = (
        {line.key for line in _import_lines(start_source, _parse(start_source, conftest_path))}
        if start_source is not None
        else set[str]()
    )
    return [line for line in reference_lines if line.key not in have]


def _insertion_index(source: str, module: ast.Module) -> int:
    """The 0-based line before which added imports go: after the docstring and future imports."""
    for position, node in enumerate(module.body):
        is_docstring = (
            position == 0
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
        is_future = isinstance(node, ast.ImportFrom) and node.module == _FUTURE_MODULE
        if is_docstring or is_future:
            continue
        first = min([node.lineno, *(d.lineno for d in getattr(node, "decorator_list", []))])
        return first - 1
    return len(source.split("\n"))


def build_module(
    file_path: str,
    fixtures: list[ConftestFixture],
    start: TreeReader,
    start_paths: frozenset[str],
    reference: TreeReader,
) -> str:
    """The injected module's text for one hidden test file."""
    reference_paths = frozenset(reference.list_paths())
    body = reference.read(file_path).decode("utf-8")
    body_module = _parse(body, file_path)
    have = {line.key for line in _import_lines(body, body_module)}
    conftests = conftests_on_path(file_path)
    hosted = [fixture for fixture in fixtures if fixture.conftest_path in conftests]

    wanted: dict[str, _ImportLine] = {}
    fixture_sources: list[str] = []
    for conftest_path in conftests:
        added = _added_imports(conftest_path, start, start_paths, reference, reference_paths)
        wanted.update({line.key: line for line in added})
    for fixture in hosted:
        conftest_source = reference.read(fixture.conftest_path).decode("utf-8")
        conftest_module = _parse(conftest_source, fixture.conftest_path)
        node = _find_fixture(conftest_module, fixture.fixture_name)
        if node is None:
            _logger.error(
                "hidden fixture %s not found in %s", fixture.fixture_name, fixture.conftest_path
            )
            raise TreeReadError(
                f"find fixture {fixture.fixture_name} in {fixture.conftest_path} at the reference",
                "no such top-level function",
            )
        used = {inner.id for inner in ast.walk(node) if isinstance(inner, ast.Name)}
        for line in _import_lines(conftest_source, conftest_module):
            if line.bound_names & used:
                wanted.setdefault(line.key, line)
        fixture_sources.append(_source_lines(conftest_source, node))

    extra = [line.text for key, line in wanted.items() if key not in have]
    lines = body.split("\n")
    at = _insertion_index(body, body_module)
    merged = [*lines[:at], *extra, *lines[at:]]
    text = "\n".join(merged).rstrip("\n") + "\n"
    for source in fixture_sources:
        text += f"\n\n{source}\n"
    return text


def injected_path(file_path: str, suffix: str = "") -> str:
    """``<dir>/test_sqhidden_<stem><suffix>.py`` beside *file_path*."""
    original = PurePosixPath(file_path)
    return str(original.with_name(f"{INJECTED_PREFIX}{original.stem}{suffix}.py"))


def _group_hidden(hidden_tests: tuple[str, ...]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for node_id in hidden_tests:
        file_path, separator, _ = node_id.partition(NODE_ID_SEPARATOR)
        if not separator:
            raise ValueError(f"hidden test id {node_id!r} has no file part")
        grouped[file_path].append(node_id)
    return dict(grouped)


def _free_target(tree: Path, file_path: str, clashes: list[str]) -> str:
    """The injected path beside *file_path*; ``_2``, ``_3`` ... when the name is taken."""
    base = injected_path(file_path)
    if not (tree / base).exists():
        return base
    number = 2
    while (tree / injected_path(file_path, f"_{number}")).exists():
        number += 1
    renamed = injected_path(file_path, f"_{number}")
    clashes.append(clash(ClashKind.FILENAME_TAKEN, f"{base} -> {renamed}"))
    return renamed


def _test_names(source: str) -> set[str]:
    """``test_x`` and ``Class::test_x`` names defined at module level or in a class."""
    names: set[str] = set()
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            for member in node.body:
                if isinstance(
                    member, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and member.name.startswith("test"):
                    names.add(f"{node.name}{NODE_ID_SEPARATOR}{member.name}")
    return names


def _same_name_tests(tree: Path, file_path: str, node_ids: list[str]) -> list[str]:
    """Hidden tests whose name the producer's own version of the file also defines."""
    produced = tree / file_path
    if not produced.exists():
        return []
    try:
        defined = _test_names(produced.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError) as exc:
        # Nothing in a file that does not import can clash with the injected module.
        _logger.warning("%s does not parse (%s); no same-name test clash recorded", file_path, exc)
        return []
    found: list[str] = []
    for node_id in node_ids:
        name = node_id.removeprefix(file_path + NODE_ID_SEPARATOR).split(PARAMETER_OPEN)[0]
        if name in defined:
            found.append(clash(ClashKind.SAME_TEST_NAME, f"{file_path}{NODE_ID_SEPARATOR}{name}"))
    return found


def _same_name_fixtures(tree: Path, fixtures: list[ConftestFixture], file_path: str) -> list[str]:
    """Hidden fixtures on the file's path that the producer's conftest also defines."""
    found: list[str] = []
    conftests = conftests_on_path(file_path)
    for fixture in fixtures:
        produced = tree / fixture.conftest_path
        if fixture.conftest_path not in conftests or not produced.exists():
            continue
        try:
            module = ast.parse(produced.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as exc:
            _logger.warning(
                "%s does not parse (%s); no same-name fixture clash recorded", produced, exc
            )
            continue
        if _find_fixture(module, fixture.fixture_name) is not None:
            detail = f"{fixture.conftest_path}{NODE_ID_SEPARATOR}{fixture.fixture_name}"
            found.append(clash(ClashKind.SAME_FIXTURE_NAME, detail))
    return found


def inject_hidden(
    tree: Path, case: BenchmarkCase, start: TreeReader, reference: TreeReader
) -> InjectionResult:
    """Write each hidden test file as a sibling module, map the ids and record clashes.

    Nothing the producer wrote is removed or overwritten: a taken filename gets ``_2``,
    ``_3``; a same-named test runs beside the injected one; a same-named conftest fixture is
    shadowed by the injected module's own definition, for that module only.
    """
    start_paths = frozenset(start.list_paths())
    id_map: list[tuple[str, str]] = []
    written: list[str] = []
    clashes: list[str] = []
    for file_path, node_ids in sorted(_group_hidden(case.hidden_tests).items()):
        fixtures = list(case.hidden_fixtures)
        clashes.extend(_same_name_tests(tree, file_path, node_ids))
        clashes.extend(_same_name_fixtures(tree, fixtures, file_path))
        module = build_module(file_path, fixtures, start, start_paths, reference)
        target = _free_target(tree, file_path, clashes)
        (tree / target).write_text(module, encoding="utf-8")
        written.append(target)
        for node_id in node_ids:
            id_map.append((node_id, target + node_id.removeprefix(file_path)))
    return InjectionResult(
        id_map=tuple(id_map),
        files_written=tuple(written),
        clashes=tuple(dict.fromkeys(clashes)),
    )
