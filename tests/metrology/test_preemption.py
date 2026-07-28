"""Fragment generation, file I/O, and freshness (324 T2-T4).

The read paths are also the dispatch-time read paths, so their tests assert
``None`` rather than an exception for every malformed input — a fragment
problem must never be able to fail a dispatch.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadron.metrology.audit_models import (
    AuditCategory,
    BaselineCell,
    FloorStat,
    ProjectBaseline,
)
from squadron.metrology.models import ProjectId, ProjectIdSource
from squadron.metrology.preemption import (
    CATEGORY_GUIDANCE,
    check_freshness,
    fragment_path_for,
    read_fragment_body,
    read_fragment_header,
    render_fragment,
    write_fragment,
)

_HASH = "b" * 64
_MEASURED_AT = datetime(2026, 7, 26, 12, 30, tzinfo=UTC)


def make_baseline(
    *,
    counts: dict[AuditCategory, int] | None = None,
    audit_prompt_hash: str = _HASH,
    measured_at: datetime = _MEASURED_AT,
    project_value: str = "github.com/manta/example-repo",
    floors: dict[AuditCategory, FloorStat] | None = None,
) -> ProjectBaseline:
    """A ProjectBaseline with one cell per entry in ``counts``."""
    resolved = counts if counts is not None else {AuditCategory.TEST_DEBT: 4}
    floors = floors or {}
    cells = [
        BaselineCell(
            category=category,
            count=count,
            floor=floors.get(category),
            floor_note=None if category in floors else "no floor measured",
        )
        for category, count in resolved.items()
    ]
    return ProjectBaseline(
        project_id=ProjectId(value=project_value, source=ProjectIdSource.REMOTE),
        commit_sha="a" * 40,
        audit_prompt_hash=audit_prompt_hash,
        run_id="audit-20260726-abcd1234",
        measured_at=measured_at,
        total_findings=sum(resolved.values()),
        unnormalized_count=0,
        cells=cells,
    )


@pytest.mark.parametrize("category", list(AuditCategory))
def test_every_category_has_guidance(category: AuditCategory) -> None:
    """A category added to the enum without a guidance line fails here."""
    assert category in CATEGORY_GUIDANCE
    assert CATEGORY_GUIDANCE[category].strip()


def test_guidance_covers_the_enum_exactly() -> None:
    assert set(CATEGORY_GUIDANCE) == set(AuditCategory)
    assert len(CATEGORY_GUIDANCE) == 10


def test_render_includes_only_nonzero_categories() -> None:
    baseline = make_baseline(
        counts={
            AuditCategory.ARCHITECTURAL_DECAY: 3,
            AuditCategory.TEST_DEBT: 0,
            AuditCategory.SECURITY_HYGIENE: 1,
            AuditCategory.DOCUMENTATION_DRIFT: 0,
        }
    )
    fragment = render_fragment(baseline)

    assert CATEGORY_GUIDANCE[AuditCategory.ARCHITECTURAL_DECAY] in fragment.text
    assert CATEGORY_GUIDANCE[AuditCategory.SECURITY_HYGIENE] in fragment.text
    assert CATEGORY_GUIDANCE[AuditCategory.TEST_DEBT] not in fragment.text
    assert CATEGORY_GUIDANCE[AuditCategory.DOCUMENTATION_DRIFT] not in fragment.text
    # Exactly two guidance lines for two nonzero cells.
    assert len([line for line in fragment.text.splitlines() if line.startswith("- ")]) == 2


def test_render_preserves_baseline_cell_order() -> None:
    """Ordering follows the baseline's cells, so output is stable."""
    baseline = make_baseline(
        counts={
            AuditCategory.SECURITY_HYGIENE: 2,
            AuditCategory.ARCHITECTURAL_DECAY: 5,
        }
    )
    text = render_fragment(baseline).text
    assert text.index(CATEGORY_GUIDANCE[AuditCategory.SECURITY_HYGIENE]) < text.index(
        CATEGORY_GUIDANCE[AuditCategory.ARCHITECTURAL_DECAY]
    )


def test_render_stamps_provenance_from_baseline() -> None:
    baseline = make_baseline()
    fragment = render_fragment(baseline)

    assert fragment.audit_prompt_hash == baseline.audit_prompt_hash
    assert fragment.measured_at == baseline.measured_at
    assert fragment.project_id == baseline.project_id
    assert _MEASURED_AT.isoformat() in fragment.text


def test_render_all_zero_baseline_is_never_empty() -> None:
    """An empty prepend is indistinguishable from no fragment at dispatch."""
    baseline = make_baseline(
        counts={AuditCategory.TEST_DEBT: 0, AuditCategory.OTHER: 0},
    )
    fragment = render_fragment(baseline)

    assert fragment.text.strip()
    assert "no recurring issue classes" in fragment.text
    assert not any(guidance in fragment.text for guidance in CATEGORY_GUIDANCE.values())


def test_render_every_category_exercises_the_table() -> None:
    """A fragment naming all ten categories renders without a KeyError."""
    baseline = make_baseline(counts={category: 1 for category in AuditCategory})
    text = render_fragment(baseline).text
    for guidance in CATEGORY_GUIDANCE.values():
        assert guidance in text


def test_write_then_read_header_round_trips(tmp_path: Path) -> None:
    fragment = render_fragment(make_baseline())
    path = write_fragment(fragment, directory=tmp_path / "fragments")

    assert path.is_file()
    header = read_fragment_header(path)
    assert header is not None
    assert header == (_HASH, _MEASURED_AT)


def test_write_uses_the_conventional_path(tmp_path: Path) -> None:
    """The writer and ``--check`` must agree on where a fragment lives."""
    directory = tmp_path / "fragments"
    fragment = render_fragment(make_baseline())
    path = write_fragment(fragment, directory=directory)

    assert path == fragment_path_for(fragment.project_id.value, directory=directory)
    assert "/" not in path.name


def test_write_creates_directory_and_overwrites(tmp_path: Path) -> None:
    directory = tmp_path / "nested" / "fragments"
    first = write_fragment(render_fragment(make_baseline()), directory=directory)
    second = write_fragment(
        render_fragment(make_baseline(audit_prompt_hash="c" * 64)), directory=directory
    )

    assert first == second
    header = read_fragment_header(second)
    assert header is not None
    assert header[0] == "c" * 64


def test_write_then_read_body_round_trips(tmp_path: Path) -> None:
    fragment = render_fragment(make_baseline())
    path = write_fragment(fragment, directory=tmp_path)

    assert read_fragment_body(path) == fragment.text


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("empty.md", ""),
        ("whitespace.md", "   \n\n  \n"),
        ("no-header.md", "Just some prose with no header at all.\n"),
        ("truncated.md", "---\naudit_prompt_hash: abc\n"),
        ("missing-hash.md", "---\nmeasured_at: 2026-07-26T12:30:00+00:00\n---\n\nbody\n"),
        ("missing-timestamp.md", "---\naudit_prompt_hash: abc\n---\n\nbody\n"),
        ("bad-timestamp.md", "---\naudit_prompt_hash: abc\nmeasured_at: not-a-date\n---\n\nbody\n"),
    ],
)
def test_read_header_degrades_to_none(tmp_path: Path, name: str, content: str) -> None:
    """Every malformed shape returns None rather than raising."""
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")

    assert read_fragment_header(path) is None
    assert read_fragment_body(path) is None


def test_read_nonexistent_path_returns_none(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.md"

    assert read_fragment_header(missing) is None
    assert read_fragment_body(missing) is None


def test_read_directory_path_returns_none(tmp_path: Path) -> None:
    """A directory where a file was expected is an OSError, not a crash."""
    assert read_fragment_header(tmp_path) is None
    assert read_fragment_body(tmp_path) is None


def test_read_body_none_when_header_valid_but_body_empty(tmp_path: Path) -> None:
    path = tmp_path / "headers-only.md"
    path.write_text(
        f"---\naudit_prompt_hash: {_HASH}\nmeasured_at: {_MEASURED_AT.isoformat()}\n---\n\n   \n",
        encoding="utf-8",
    )

    assert read_fragment_header(path) is not None
    assert read_fragment_body(path) is None


def test_freshness_current_on_matching_hash(tmp_path: Path) -> None:
    baseline = make_baseline()
    path = write_fragment(render_fragment(baseline), directory=tmp_path)

    result = check_freshness(path, baseline)

    assert result.is_current is True
    assert result.fragment_audit_prompt_hash == _HASH
    assert result.current_audit_prompt_hash == _HASH
    assert result.fragment_measured_at == _MEASURED_AT
    assert "current" in result.note


def test_freshness_stale_names_both_hashes(tmp_path: Path) -> None:
    path = write_fragment(render_fragment(make_baseline()), directory=tmp_path)
    newer = make_baseline(audit_prompt_hash="d" * 64)

    result = check_freshness(path, newer)

    assert result.is_current is False
    assert result.fragment_audit_prompt_hash == _HASH
    assert result.current_audit_prompt_hash == "d" * 64
    assert _HASH in result.note
    assert "d" * 64 in result.note
    assert "stale" in result.note


def test_freshness_absent_is_distinct_from_stale(tmp_path: Path) -> None:
    """Absent and stale need different corrective actions, so never conflate."""
    result = check_freshness(tmp_path / "never-generated.md", make_baseline())

    assert result.is_current is False
    assert result.fragment_audit_prompt_hash is None
    assert result.fragment_measured_at is None
    assert "absent" in result.note
    assert "stale" not in result.note
