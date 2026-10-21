"""build_probe's output must match the example and field table in the contract document."""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from squadron.probe import PROBE_VERSION, build_probe

CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "project-documents"
    / "user"
    / "reference"
    / "capability-probe-contract.md"
)
SURFACE_WILDCARD = "<s>"
STRING_OR_NULL_EXAMPLE = "string or null"
EXACT_SURFACE_FIELDS = ("entry", "concept", "graph_build")


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}.*?\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match, f"contract has no '## {heading}' section"
    return match.group(1)


def _contract_example(text: str) -> dict[str, Any]:
    block = re.search(r"```json\n(.*?)```", _section(text, "Shape"), re.S)
    assert block, "contract Shape section has no json block"
    return json.loads(block.group(1))


def _nullable_paths(text: str) -> set[str]:
    """Dotted field paths whose Type column says 'or null'; surfaces use the <s> wildcard."""
    paths: set[str] = set()
    for row in re.findall(r"^\| `([^`]+)` \| ([^|]+) \|", text, re.M):
        field, type_column = row
        if "or null" in type_column:
            paths.add(field)
    assert paths, "no 'or null' rows found in the contract field table"
    return paths


def _json_type(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    return type(value).__name__


def _normalize(path: str) -> str:
    parts = path.split(".")
    if parts[0] == "surfaces" and len(parts) > 1:
        parts[1] = SURFACE_WILDCARD
    return ".".join(parts)


def _compare(example: object, actual: object, path: str, nullable: set[str]) -> None:
    if isinstance(example, dict):
        assert isinstance(actual, dict), f"{path}: expected an object"
        assert set(actual) == set(example), f"{path}: keys differ"
        for key in example:
            _compare(example[key], actual[key], f"{path}.{key}" if path else key, nullable)
        return
    if actual is None:
        assert _normalize(path) in nullable, f"{path}: null but the contract does not allow it"
        return
    expected_type = "str" if example == STRING_OR_NULL_EXAMPLE else _json_type(example)
    assert _json_type(actual) == expected_type, f"{path}: expected {expected_type}"


@pytest.fixture
def contract_text() -> str:
    return CONTRACT.read_text(encoding="utf-8")


def test_probe_matches_contract_example(tmp_path: Path, contract_text: str) -> None:
    example = _contract_example(contract_text)
    probe = json.loads(json.dumps(build_probe(tmp_path)))

    _compare(example, probe, "", _nullable_paths(contract_text))


def test_probe_version_matches_contract(tmp_path: Path, contract_text: str) -> None:
    example = _contract_example(contract_text)

    assert PROBE_VERSION == 1
    assert example["probe_version"] == PROBE_VERSION
    assert build_probe(tmp_path)["probe_version"] == PROBE_VERSION


def test_contract_strings_match_exactly(tmp_path: Path, contract_text: str) -> None:
    example = _contract_example(contract_text)
    probe = build_probe(tmp_path)

    for surface, fields in example["surfaces"].items():
        for field in EXACT_SURFACE_FIELDS:
            assert probe["surfaces"][surface][field] == fields[field], f"{surface}.{field}"
