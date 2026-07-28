"""Pre-emption and delta CLI surfaces (324 T11-T12).

The refusals carry the weight here. A fragment generated with no baseline,
or a delta reported against a failed run, would wear the format of a real
measurement while resting on nothing — so both exit 1 rather than
improvising.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.metrology.audit import AuditRunFailure, AuditRunResult
from squadron.metrology.audit_models import AuditCategory, FloorStat
from squadron.metrology.models import ProjectId, ProjectIdSource
from squadron.metrology.store import MetrologyStore

from .conftest import make_audit_finding, make_audit_run, make_noise_floor

runner = CliRunner()

_PROJECT = "github.com/manta/example-repo"
_MODULE = "squadron.cli.commands.metrology_preemption"


def _normalized(output: str) -> str:
    """Collapse Rich line-wrapping so substring assertions survive width."""
    return " ".join(output.split())


@pytest.fixture
def cli_store(tmp_path: Path) -> Iterator[MetrologyStore]:
    """Redirect the 324 module's store construction to a temp path."""
    store = MetrologyStore(store_dir=tmp_path / "cli-store")
    with patch(f"{_MODULE}.MetrologyStore", return_value=store):
        yield store


@pytest.fixture
def fragment_dir(tmp_path: Path) -> Iterator[Path]:
    """Point the configured fragment directory at a temp path."""
    directory = tmp_path / "fragments"
    with patch(f"{_MODULE}._fragment_dir", return_value=directory):
        yield directory


@pytest.fixture
def known_project() -> Iterator[None]:
    """Resolve any project path to one fixed identity."""
    project_id = ProjectId(value=_PROJECT, source=ProjectIdSource.REMOTE)
    with patch(f"{_MODULE}.derive_project_id", return_value=project_id):
        yield


def _seed_baseline(
    store: MetrologyStore,
    *,
    categories: dict[AuditCategory, int] | None = None,
    with_floor: bool = True,
) -> None:
    """Persist an audit run (and optionally a floor) forming a baseline."""
    counts = categories or {AuditCategory.ARCHITECTURAL_DECAY: 3, AuditCategory.TEST_DEBT: 2}
    findings = [
        make_audit_finding(finding_id=f"F{category.value}-{index}", category=category)
        for category, count in counts.items()
        for index in range(count)
    ]
    store.write_audit_run(make_audit_run(project_value=_PROJECT, findings=findings))
    if with_floor:
        store.write_noise_floor(
            make_noise_floor(
                project_value=_PROJECT,
                total=FloorStat(min=3, max=9, mean=6.0, stddev=2.4),
                per_category={
                    category: FloorStat(min=1, max=6, mean=3.0, stddev=1.5) for category in counts
                },
            )
        )


# --------------------------------------------------------------------------
# preempt generate
# --------------------------------------------------------------------------


def test_generate_writes_fragment_and_prints_path(
    cli_store: MetrologyStore, fragment_dir: Path, known_project: None, tmp_path: Path
) -> None:
    _seed_baseline(cli_store)

    result = runner.invoke(app, ["metrology", "preempt", "generate", str(tmp_path)])

    assert result.exit_code == 0, result.output
    written = list(fragment_dir.glob("*.md"))
    assert len(written) == 1
    # Rich wraps long paths at the terminal width, and a narrow CI terminal
    # can break one mid-token ("github. com-..."), so assert on the file that
    # was actually written plus a short unwrappable marker rather than trying
    # to match the full path in the output.
    assert written[0].name == "github.com-manta-example-repo.md"
    assert "Wrote" in _normalized(result.output)
    assert "2 issue class(es) named" in _normalized(result.output)


def test_generate_json_parses_as_fragment(
    cli_store: MetrologyStore, fragment_dir: Path, known_project: None, tmp_path: Path
) -> None:
    _seed_baseline(cli_store)

    result = runner.invoke(app, ["metrology", "preempt", "generate", str(tmp_path), "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["project_id"]["value"] == _PROJECT
    assert payload["audit_prompt_hash"]
    assert payload["text"]


def test_generate_names_only_nonzero_categories(
    cli_store: MetrologyStore, fragment_dir: Path, known_project: None, tmp_path: Path
) -> None:
    _seed_baseline(cli_store, categories={AuditCategory.SECURITY_HYGIENE: 4})

    result = runner.invoke(app, ["metrology", "preempt", "generate", str(tmp_path), "--json"])

    assert result.exit_code == 0, result.output
    text = json.loads(result.output.strip().splitlines()[-1])["text"]
    assert "Security hygiene" in text
    assert "Test debt" not in text


def test_generate_overwrites_existing_fragment(
    cli_store: MetrologyStore, fragment_dir: Path, known_project: None, tmp_path: Path
) -> None:
    _seed_baseline(cli_store)
    runner.invoke(app, ["metrology", "preempt", "generate", str(tmp_path)])
    result = runner.invoke(app, ["metrology", "preempt", "generate", str(tmp_path)])

    assert result.exit_code == 0
    assert len(list(fragment_dir.glob("*.md"))) == 1


def test_generate_without_baseline_exits_1(
    cli_store: MetrologyStore, fragment_dir: Path, known_project: None, tmp_path: Path
) -> None:
    """Nothing to generate from is an error, never an empty fragment."""
    result = runner.invoke(app, ["metrology", "preempt", "generate", str(tmp_path)])

    assert result.exit_code == 1
    assert "no baseline found" in _normalized(result.output)
    assert not fragment_dir.exists() or not list(fragment_dir.glob("*.md"))


# --------------------------------------------------------------------------
# preempt generate --check
# --------------------------------------------------------------------------


def test_check_current_exits_0(
    cli_store: MetrologyStore, fragment_dir: Path, known_project: None, tmp_path: Path
) -> None:
    _seed_baseline(cli_store)
    runner.invoke(app, ["metrology", "preempt", "generate", str(tmp_path)])

    result = runner.invoke(app, ["metrology", "preempt", "generate", str(tmp_path), "--check"])

    assert result.exit_code == 0, result.output
    assert "Current" in _normalized(result.output)


def test_check_stale_exits_1_naming_the_mismatch(
    cli_store: MetrologyStore, fragment_dir: Path, known_project: None, tmp_path: Path
) -> None:
    """A fragment generated under a superseded instrument reports stale."""
    _seed_baseline(cli_store)
    runner.invoke(app, ["metrology", "preempt", "generate", str(tmp_path)])

    # Hand-edit the written fragment's recorded instrument so it no longer
    # matches the stored baseline — the exact condition --check exists for,
    # reached without introducing a second instrument into the store.
    written = next(iter(fragment_dir.glob("*.md")))
    written.write_text(
        written.read_text(encoding="utf-8").replace("b" * 64, "e" * 64), encoding="utf-8"
    )

    result = runner.invoke(app, ["metrology", "preempt", "generate", str(tmp_path), "--check"])

    assert result.exit_code == 1
    output = _normalized(result.output)
    assert "stale" in output
    assert "e" * 12 in output
    assert "b" * 12 in output


def test_check_refuses_when_project_spans_two_instruments(
    cli_store: MetrologyStore, fragment_dir: Path, known_project: None, tmp_path: Path
) -> None:
    """Which audit prompt a fragment rests on is never chosen silently."""
    _seed_baseline(cli_store)
    runner.invoke(app, ["metrology", "preempt", "generate", str(tmp_path)])

    # Re-generate the fragment from a baseline under a *different*
    # instrument, then restore the original as current: the written
    # fragment now trails the instrument the project is measured under.
    cli_store.write_audit_run(
        make_audit_run(
            project_value=_PROJECT,
            run_id="audit-20260727-ffff0000",
            audit_prompt_hash="e" * 64,
            commit_sha="c" * 40,
            measured_at=datetime(2026, 7, 27, tzinfo=UTC),
        )
    )

    # Two instruments now — generation refuses rather than guessing.
    refused = runner.invoke(app, ["metrology", "preempt", "generate", str(tmp_path), "--check"])

    assert refused.exit_code == 1
    assert "more than one audit instrument" in _normalized(refused.output)


def test_check_absent_fragment_exits_1(
    cli_store: MetrologyStore, fragment_dir: Path, known_project: None, tmp_path: Path
) -> None:
    """Absent is reported as absent, never as stale — different fixes."""
    _seed_baseline(cli_store)

    result = runner.invoke(app, ["metrology", "preempt", "generate", str(tmp_path), "--check"])

    assert result.exit_code == 1
    output = _normalized(result.output)
    assert "absent" in output
    assert "stale" not in output


def test_generate_uses_most_recent_commit_under_one_instrument(
    cli_store: MetrologyStore, fragment_dir: Path, known_project: None, tmp_path: Path
) -> None:
    """Several commits, one instrument: the newest measurement is the baseline."""
    _seed_baseline(cli_store, categories={AuditCategory.TEST_DEBT: 2})
    cli_store.write_audit_run(
        make_audit_run(
            project_value=_PROJECT,
            run_id="audit-20260727-ffff0000",
            commit_sha="c" * 40,
            measured_at=datetime(2026, 7, 27, tzinfo=UTC),
            findings=[make_audit_finding(category=AuditCategory.SECURITY_HYGIENE)],
        )
    )

    result = runner.invoke(app, ["metrology", "preempt", "generate", str(tmp_path), "--json"])

    assert result.exit_code == 0, result.output
    text = json.loads(result.output.strip().splitlines()[-1])["text"]
    assert "Security hygiene" in text
    assert "Test debt" not in text


def test_check_json_emits_freshness_result(
    cli_store: MetrologyStore, fragment_dir: Path, known_project: None, tmp_path: Path
) -> None:
    _seed_baseline(cli_store)
    runner.invoke(app, ["metrology", "preempt", "generate", str(tmp_path)])

    result = runner.invoke(
        app, ["metrology", "preempt", "generate", str(tmp_path), "--check", "--json"]
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["is_current"] is True
    assert payload["fragment_audit_prompt_hash"] == payload["current_audit_prompt_hash"]


# --------------------------------------------------------------------------
# audit delta
# --------------------------------------------------------------------------


def _patch_run_audit(store: MetrologyStore, counts: dict[AuditCategory, int]):
    """Return a patch context for run_audit yielding a run with ``counts``."""
    findings = [
        make_audit_finding(finding_id=f"N{category.value}-{index}", category=category)
        for category, count in counts.items()
        for index in range(count)
    ]
    run = make_audit_run(
        project_value=_PROJECT,
        run_id="audit-20260728-newrun01",
        findings=findings,
        measured_at=datetime(2026, 7, 28, tzinfo=UTC),
    )

    async def _fake_run_audit(project_path: Path, **_: object) -> AuditRunResult:
        return AuditRunResult(project_path=project_path, run=run)

    return patch(f"{_MODULE}.run_audit", _fake_run_audit)


def test_delta_renders_counts_floor_and_disclaimer(
    cli_store: MetrologyStore, known_project: None, tmp_path: Path
) -> None:
    _seed_baseline(cli_store)

    with _patch_run_audit(
        cli_store, {AuditCategory.ARCHITECTURAL_DECAY: 2, AuditCategory.TEST_DEBT: 2}
    ):
        result = runner.invoke(app, ["metrology", "audit", "delta", str(tmp_path)])

    assert result.exit_code == 0, result.output
    output = _normalized(result.output)
    # Not the full project id: Rich can wrap it mid-token at a narrow width.
    assert "example-repo" in output
    assert "5 → 4 findings" in output
    assert "-1" in output
    assert "within floor" in output
    assert "Observational only" in output


def test_delta_json_emits_the_report(
    cli_store: MetrologyStore, known_project: None, tmp_path: Path
) -> None:
    _seed_baseline(cli_store)

    with _patch_run_audit(cli_store, {AuditCategory.ARCHITECTURAL_DECAY: 1}):
        result = runner.invoke(app, ["metrology", "audit", "delta", str(tmp_path), "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["baseline_total"] == 5
    assert payload["new_total"] == 1
    assert payload["total_delta"] == -4
    assert payload["disclaimer"]


def test_delta_without_floor_reports_uninterpretable(
    cli_store: MetrologyStore, known_project: None, tmp_path: Path
) -> None:
    """No floor means no reading — never a silent 'significant'."""
    _seed_baseline(cli_store, with_floor=False)

    with _patch_run_audit(cli_store, {AuditCategory.ARCHITECTURAL_DECAY: 30}):
        result = runner.invoke(app, ["metrology", "audit", "delta", str(tmp_path)])

    assert result.exit_code == 0, result.output
    output = _normalized(result.output)
    assert "no floor" in output
    assert "delta not interpretable" in output


def test_delta_without_baseline_exits_1(
    cli_store: MetrologyStore, known_project: None, tmp_path: Path
) -> None:
    result = runner.invoke(app, ["metrology", "audit", "delta", str(tmp_path)])

    assert result.exit_code == 1
    assert "no baseline found" in _normalized(result.output)


def test_delta_failed_run_reports_no_partial_delta(
    cli_store: MetrologyStore, known_project: None, tmp_path: Path
) -> None:
    """A failed run persists nothing, so it must produce no delta at all."""
    _seed_baseline(cli_store)

    async def _failed_run(project_path: Path, **_: object) -> AuditRunResult:
        return AuditRunResult(project_path=project_path, run=None, failure=AuditRunFailure.TIMEOUT)

    with patch(f"{_MODULE}.run_audit", _failed_run):
        result = runner.invoke(app, ["metrology", "audit", "delta", str(tmp_path)])

    assert result.exit_code == 1
    output = _normalized(result.output)
    assert "audit run failed" in output
    assert "Observational only" not in output
