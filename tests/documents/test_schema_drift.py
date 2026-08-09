"""Fails when Context Forge and the schema enums disagree.

Context Forge owns the frontmatter schema (D10); squadron's ``schema.py`` keeps
only the values squadron *writes*. These tests assert cf accepts every value
squadron emits, by running ``cf validate frontmatter`` against generated
fixtures. Deliberately fails rather than skips when ``cf`` is absent — a
skipped drift test is a silent fallback, and drift is the exact risk that left
slice 171's frontmatter consumer designing against a schema nobody re-checked.

``cf validate frontmatter`` silently skips out-of-root paths and reports
``filesChecked: 0`` with exit 0, so every assertion here checks
``filesChecked`` — a fixture cf never looked at must fail the test, not pass it.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import tokenize
import uuid
from pathlib import Path

from squadron.documents.schema import MACHINE_ARTIFACT_DOC_TYPES, DocType, DocumentStatus

_DOC_ROOT = Path("project-documents/user")


def _cf_validate(paths: list[Path]) -> dict:
    """Run ``cf validate frontmatter --json`` on paths; fail (never skip) if cf is absent."""
    try:
        result = subprocess.run(
            ["cf", "validate", "frontmatter", "--json", *[str(p) for p in paths]],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        raise AssertionError(
            "'cf' is not on PATH — the frontmatter schema lives in Context Forge, "
            "so this drift test cannot run without it. Install context-forge >= 0.12.0."
        ) from None
    return json.loads(result.stdout)


def _write_fixtures(frontmatters: list[dict[str, str]]) -> list[Path]:
    paths: list[Path] = []
    for frontmatter in frontmatters:
        lines = "\n".join(f"{key}: {value}" for key, value in frontmatter.items())
        path = _DOC_ROOT / f"zz-drift-{uuid.uuid4().hex}.md"
        path.write_text(f"---\n{lines}\n---\nDrift-test fixture.\n", encoding="utf-8")
        paths.append(path)
    return paths


def _assert_cf_accepts(frontmatters: list[dict[str, str]]) -> None:
    paths = _write_fixtures(frontmatters)
    try:
        report = _cf_validate(paths)
    finally:
        for path in paths:
            path.unlink()
    assert report["filesChecked"] == len(paths), (
        f"cf checked {report['filesChecked']} of {len(paths)} fixtures — "
        "a skipped fixture proves nothing"
    )
    assert report["totalFindings"] == 0, report["findings"]


# The one spec docType squadron writes (review/persistence.py). It must be a
# docType cf has a schema for: cf validates per-docType, and several docTypes
# (guide, notes, slice, template, ...) fall through unvalidated — a status
# test built on one of those would prove nothing.
_WRITTEN_DOC_TYPE = DocType.REVIEW


def _universal_fields(doc_type: str, status: str) -> dict[str, str]:
    return {
        "docType": doc_type,
        "project": "squadron",
        "dateCreated": "20260809",
        "dateUpdated": "20260809",
        "status": status,
    }


def test_cf_accepts_every_status_squadron_writes() -> None:
    _assert_cf_accepts(
        [_universal_fields(_WRITTEN_DOC_TYPE, member.value) for member in DocumentStatus]
    )


def test_cf_accepts_machine_artifacts_squadron_writes() -> None:
    """Machine artifacts carry only docType and dateCreated — no status, and no
    dateUpdated, which a validator reading one file cannot justify requiring."""
    _assert_cf_accepts(
        [
            {"docType": doc_type, "dateCreated": "20260809"}
            for doc_type in sorted(MACHINE_ARTIFACT_DOC_TYPES)
        ]
    )


def test_cf_rejects_a_bad_status() -> None:
    """Harness sanity: a value cf should refuse produces a finding on a checked
    file. Without this, a cf that checked nothing would pass every test above."""
    paths = _write_fixtures([_universal_fields(_WRITTEN_DOC_TYPE, "definitely-not-a-status")])
    try:
        report = _cf_validate(paths)
    finally:
        for path in paths:
            path.unlink()
    assert report["filesChecked"] == 1
    assert report["totalFindings"] > 0


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
