"""Fails when file-naming-conventions.md and the schema enums disagree.

Deliberately fails rather than skips when the submodule is absent — a skipped
drift test is a silent fallback, and drift is the exact risk that left slice
171's frontmatter consumer designing against a schema nobody re-checked.
"""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

from squadron.documents.schema import MACHINE_ARTIFACT_DOC_TYPES, DocType, DocumentStatus

_SPEC_PATH = Path("project-documents/ai-project-guide/file-naming-conventions.md")

_STATUS_SECTION_RE = re.compile(r"###\s*Valid Status Values\s*\n(.*?)(?=\n##|\Z)", re.DOTALL)
_STATUS_BULLET_RE = re.compile(r"^-\s*`([a-z_]+)`", re.MULTILINE)
_DOCTYPE_LINE_RE = re.compile(r"Valid `docType` values:\s*(.+)$")
_BACKTICK_TOKEN_RE = re.compile(r"`([a-z-]+)`")


def _read_spec() -> str:
    if not _SPEC_PATH.is_file():
        raise AssertionError(
            f"{_SPEC_PATH} not found — run 'git submodule update --init' "
            "to fetch the ai-project-guide submodule before running this test"
        )
    return _SPEC_PATH.read_text(encoding="utf-8")


def _parse_status_values(spec_text: str) -> set[str]:
    section_match = _STATUS_SECTION_RE.search(spec_text)
    if not section_match:
        raise AssertionError("Could not find a '### Valid Status Values' section in the spec")
    return set(_STATUS_BULLET_RE.findall(section_match.group(1)))


def _parse_doctype_values(spec_text: str) -> set[str]:
    for line in spec_text.splitlines():
        match = _DOCTYPE_LINE_RE.search(line)
        if match:
            return set(_BACKTICK_TOKEN_RE.findall(match.group(1)))
    raise AssertionError("Could not find a 'Valid `docType` values:' line in the spec")


def test_status_enum_matches_spec() -> None:
    spec_text = _read_spec()
    spec_values = _parse_status_values(spec_text)
    enum_values = {member.value for member in DocumentStatus}
    assert spec_values == enum_values


def test_doctype_enum_matches_spec() -> None:
    spec_text = _read_spec()
    spec_values = _parse_doctype_values(spec_text)
    enum_values = {member.value for member in DocType}
    assert spec_values == enum_values


def test_machine_artifact_types_are_not_in_spec() -> None:
    spec_text = _read_spec()
    spec_doctypes = _parse_doctype_values(spec_text)
    assert not (MACHINE_ARTIFACT_DOC_TYPES & spec_doctypes)


_SRC_ROOT = Path("src/squadron")
_SCHEMA_MODULE = _SRC_ROOT / "documents" / "schema.py"

# The mechanical form of success criterion 6: no module outside schema.py may
# hand-render a frontmatter docType/status *key* with a canonical value
# literal rather than importing it. Scoped to the "key: value" shape rather
# than a bare substring search — `slice`, `tasks`, `review`, and `template`
# are also review-type names, pipeline step names, and other unrelated
# vocabulary throughout squadron, so a substring grep would be almost all
# false positives (exactly the gate-fatigue risk D3 warns against) rather
# than the one mechanical fix a check here is supposed to have.
_CANONICAL_VALUES = frozenset(
    {member.value for member in DocumentStatus}
    | {member.value for member in DocType}
    | MACHINE_ARTIFACT_DOC_TYPES
)


def _frontmatter_key_literal_patterns(value: str) -> list[re.Pattern[str]]:
    escaped = re.escape(value)
    return [
        # f-string / plain source: docType: review  or  status: complete
        re.compile(rf"""["']?(docType|status):\s*["']?{escaped}["']?"""),
        # dict-literal form: "docType": "review"
        re.compile(rf"""["'](docType|status)["']\s*:\s*["']{escaped}["']"""),
    ]


def _strip_comments_and_docstrings(text: str) -> str:
    """Blank out comments and docstrings, keeping every other token in place.

    A docstring documenting the schema (``Example: docType: review``) is not a
    hand-rendered canonical value, but a naive text scan cannot tell it from
    ``f"docType: review"`` in real code. Tokenizing draws that line exactly.
    String tokens are otherwise preserved, because the literals this test hunts
    for live inside them.
    """
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # Unparseable source cannot be scoped, so scan it verbatim rather than
        # letting a tokenizer failure silently exempt a file from the gate.
        return text

    kept: list[str] = []
    previous_meaningful: int | None = None
    for token in tokens:
        if token.type == tokenize.COMMENT:
            continue
        # A string in statement position (start of a logical line, or opening a
        # module/class/function body) is a docstring, not a value expression.
        is_docstring = token.type == tokenize.STRING and previous_meaningful in (
            None,
            tokenize.INDENT,
            tokenize.NEWLINE,
            tokenize.DEDENT,
        )
        if is_docstring:
            continue
        kept.append(token.string)
        if token.type not in (tokenize.NL, tokenize.COMMENT):
            previous_meaningful = token.type
    # Space-joined, not newline-joined: the patterns match a key and its value
    # as adjacent text, and splitting tokens across lines would hide the very
    # literals this test exists to catch.
    return " ".join(kept)


def test_no_canonical_literal_outside_schema_module() -> None:
    offenders: list[str] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        if path == _SCHEMA_MODULE:
            continue
        text = _strip_comments_and_docstrings(path.read_text(encoding="utf-8"))
        for value in _CANONICAL_VALUES:
            for pattern in _frontmatter_key_literal_patterns(value):
                if pattern.search(text):
                    offenders.append(f"{path}: {value!r}")
    assert not offenders, (
        "canonical status/docType key-value pairs must be built from "
        f"documents/schema.py, not restated as literals: {offenders}"
    )


def _scan_finds_literal(source: str, value: str) -> bool:
    scoped = _strip_comments_and_docstrings(source)
    return any(pattern.search(scoped) for pattern in _frontmatter_key_literal_patterns(value))


def test_drift_scan_ignores_docstrings_and_comments() -> None:
    """Documentation describing the schema is not a hand-rendered literal.

    Without this scoping the gate fires on prose, which is the false-positive
    gate fatigue the scan is deliberately shaped to avoid.
    """
    documented = '''
def render() -> str:
    """Emits frontmatter, e.g. docType: review at the top."""
    # status: complete is written by the caller
    return build()
'''
    assert not _scan_finds_literal(documented, "review")
    assert not _scan_finds_literal(documented, "complete")


def test_drift_scan_still_catches_literals_in_code() -> None:
    """Scoping must not blind the gate to the thing it exists to catch."""
    fstring_form = 'def render() -> str:\n    return f"docType: review"\n'
    dict_form = 'def render() -> dict[str, str]:\n    return {"status": "complete"}\n'
    assert _scan_finds_literal(fstring_form, "review")
    assert _scan_finds_literal(dict_form, "complete")
