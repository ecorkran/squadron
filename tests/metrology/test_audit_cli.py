"""Audit CLI: rendering, --json, refusals, and honest campaign summaries.

The campaign-summary assertions are the ones that matter operationally. A
12-audit run that quietly exits 0 having lost three runs would leave a floor
built on less evidence than the operator believes — so a failed run must be
visible in the summary *and* in the exit code.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.metrology.audit import AuditRunFailure, AuditRunResult
from squadron.metrology.audit_models import AuditCategory, FloorStat
from squadron.metrology.store import MetrologyStore
from tests.metrology.conftest import make_audit_finding, make_audit_run, make_noise_floor

runner = CliRunner()


def _normalized(output: str) -> str:
    """Collapse Rich line-wrapping so substring assertions survive width."""
    return " ".join(output.split())


@pytest.fixture
def cli_store(tmp_path: Path) -> Iterator[MetrologyStore]:
    """Redirect the CLI's store-dir resolution to a temp path."""
    store_dir = tmp_path / "cli-store"
    with patch("squadron.cli.commands.metrology.resolve_store_dir", return_value=store_dir):
        yield MetrologyStore(store_dir=store_dir)


# --------------------------------------------------------------------------
# audit run
# --------------------------------------------------------------------------


def test_audit_run_persists_and_prints(cli_store: MetrologyStore, tmp_path: Path) -> None:
    run = make_audit_run(project_value="github.com/manta/alpha")

    async def _fake_run_audit(project_path: Path, **_: object) -> AuditRunResult:
        cli_store.write_audit_run(run)
        return AuditRunResult(project_path=project_path, run=run)

    with patch("squadron.cli.commands.metrology.run_audit", _fake_run_audit):
        result = runner.invoke(app, ["metrology", "audit", "run", str(tmp_path)])

    assert result.exit_code == 0
    output = _normalized(result.output)
    assert "github.com/manta/alpha" in output
    assert "1 succeeded" in output
    assert len(cli_store.list_audit_runs()) == 1


def test_audit_run_json_emits_the_model(cli_store: MetrologyStore, tmp_path: Path) -> None:
    run = make_audit_run(findings=[make_audit_finding(), make_audit_finding(finding_id="F002")])

    async def _fake_run_audit(project_path: Path, **_: object) -> AuditRunResult:
        return AuditRunResult(project_path=project_path, run=run)

    with patch("squadron.cli.commands.metrology.run_audit", _fake_run_audit):
        result = runner.invoke(app, ["metrology", "audit", "run", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["run_id"] == run.run_id
    assert len(payload["findings"]) == 2


def test_audit_run_reports_failure_and_exits_nonzero(cli_store: MetrologyStore, tmp_path: Path) -> None:
    """A failed run must not be reported as a successful campaign."""

    async def _fake_run_audit(project_path: Path, **_: object) -> AuditRunResult:
        return AuditRunResult(
            project_path=project_path,
            failure=AuditRunFailure.BLOCK_MISSING,
            detail="no findings block",
        )

    with patch("squadron.cli.commands.metrology.run_audit", _fake_run_audit):
        result = runner.invoke(app, ["metrology", "audit", "run", str(tmp_path)])

    assert result.exit_code == 1
    output = _normalized(result.output)
    assert "failed" in output
    assert "block_missing" in output
    assert cli_store.list_audit_runs() == []


def test_campaign_summary_is_honest_about_partial_failure(
    cli_store: MetrologyStore, tmp_path: Path
) -> None:
    """One failure in a three-project campaign is visible and non-zero exit.

    The dangerous failure mode is a campaign that loses runs and still exits
    0 — the operator would build a floor on thinner evidence than they think.
    """
    calls: list[Path] = []

    async def _fake_run_audit(project_path: Path, **_: object) -> AuditRunResult:
        calls.append(project_path)
        if len(calls) == 2:
            return AuditRunResult(
                project_path=project_path,
                failure=AuditRunFailure.TIMEOUT,
                detail="exceeded metrology.audit_timeout_s (3600s)",
            )
        run = make_audit_run(run_id=f"audit-2026072{len(calls)}-aaaaaaaa")
        cli_store.write_audit_run(run)
        return AuditRunResult(project_path=project_path, run=run)

    projects = [str(tmp_path / name) for name in ("a", "b", "c")]
    for path in projects:
        Path(path).mkdir()

    with patch("squadron.cli.commands.metrology.run_audit", _fake_run_audit):
        result = runner.invoke(app, ["metrology", "audit", "run", *projects])

    assert result.exit_code == 1, "a campaign that lost a run must not exit 0"
    output = _normalized(result.output)
    assert "2 succeeded" in output
    assert "1 failed" in output
    assert len(calls) == 3, "a mid-campaign failure must not abort the rest"


# --------------------------------------------------------------------------
# audit variance
# --------------------------------------------------------------------------


def test_audit_variance_refuses_a_dirty_worktree(cli_store: MetrologyStore, audited_repo: Path) -> None:
    """The refusal is a pre-flight check, so it costs nothing."""
    (audited_repo / "scratch.tmp").write_text("uncommitted", encoding="utf-8")

    result = runner.invoke(
        app,
        ["metrology", "audit", "variance", str(audited_repo), "--runs", "2"],
    )

    assert result.exit_code == 1
    output = _normalized(result.output)
    assert "dirty" in output.lower()
    assert cli_store.list_noise_floors() == []


def test_audit_variance_writes_a_floor(cli_store: MetrologyStore, tmp_path: Path) -> None:
    counter = {"n": 0}

    async def _fake_run_audit(project_path: Path, **_: object) -> AuditRunResult:
        counter["n"] += 1
        run = make_audit_run(
            run_id=f"audit-20260726-{counter['n']:08d}",
            findings=[make_audit_finding(finding_id=f"F{i:03d}") for i in range(counter["n"] + 2)],
        )
        cli_store.write_audit_run(run)
        return AuditRunResult(project_path=project_path, run=run)

    with patch("squadron.cli.commands.metrology.run_audit", _fake_run_audit):
        result = runner.invoke(app, ["metrology", "audit", "variance", str(tmp_path), "--runs", "3"])

    assert result.exit_code == 0
    floors = cli_store.list_noise_floors()
    assert len(floors) == 1
    assert floors[0][1].n_runs == 3
    assert "floor" in _normalized(result.output)


def test_full_series_succeeds_when_each_run_writes_its_own_audit_file(
    cli_store: MetrologyStore, audited_repo: Path
) -> None:
    """Regression: a variance series must not refuse itself.

    Each run writes ``analysis/nnn-analysis.*.md`` into the target repo, as
    the real skill does. Before the artifact exemption, run 1 dirtied the
    tree and runs 2-3 were refused, so **no floor was written for any
    project** — a whole campaign's spend for nothing. This asserts all three
    runs land and a floor results.
    """
    counter = {"n": 0}

    async def _fake_run_audit(project_path: Path, **kwargs: object) -> AuditRunResult:
        from squadron.metrology.audit import preflight_project

        counter["n"] += 1
        # Real pre-flight, so the dirty-worktree logic is genuinely exercised.
        preflight = preflight_project(
            project_path,
            require_clean=bool(kwargs.get("require_clean")),
            expected_sha=kwargs.get("expected_sha"),  # pyright: ignore[reportArgumentType]
        )
        # Then write the artifact the skill would write.
        analysis = project_path / "analysis"
        analysis.mkdir(exist_ok=True)
        (analysis / f"94{counter['n']}-analysis.example-repo.md").write_text(
            "# audit\n", encoding="utf-8"
        )
        run = make_audit_run(
            run_id=f"audit-20260726-{counter['n']:08d}",
            commit_sha=preflight.commit_sha,
            findings=[make_audit_finding(finding_id=f"F{i:03d}") for i in range(counter["n"] + 3)],
        )
        cli_store.write_audit_run(run)
        return AuditRunResult(project_path=project_path, run=run)

    with patch("squadron.cli.commands.metrology.run_audit", _fake_run_audit):
        result = runner.invoke(
            app, ["metrology", "audit", "variance", str(audited_repo), "--runs", "3"]
        )

    assert result.exit_code == 0, f"series should complete; got: {_normalized(result.output)}"
    assert counter["n"] == 3, "all three runs must execute, not just the first"
    floors = cli_store.list_noise_floors()
    assert len(floors) == 1, "a floor must be written"
    assert floors[0][1].n_runs == 3


def test_variance_with_too_few_usable_runs_keeps_them_and_writes_no_floor(
    cli_store: MetrologyStore, tmp_path: Path
) -> None:
    """A short series is reported, not discarded — it can be reduced later."""
    counter = {"n": 0}

    async def _fake_run_audit(project_path: Path, **_: object) -> AuditRunResult:
        counter["n"] += 1
        if counter["n"] > 1:
            return AuditRunResult(
                project_path=project_path, failure=AuditRunFailure.STREAM_ERROR, detail="boom"
            )
        run = make_audit_run(run_id="audit-20260726-00000001")
        cli_store.write_audit_run(run)
        return AuditRunResult(project_path=project_path, run=run)

    with patch("squadron.cli.commands.metrology.run_audit", _fake_run_audit):
        result = runner.invoke(app, ["metrology", "audit", "variance", str(tmp_path), "--runs", "3"])

    assert result.exit_code == 1
    assert cli_store.list_noise_floors() == [], "no floor from a single usable run"
    assert len(cli_store.list_audit_runs()) == 1, "the usable run is kept for later reduction"
    assert "only 1 usable run" in _normalized(result.output)


# --------------------------------------------------------------------------
# report baseline
# --------------------------------------------------------------------------


def test_report_baseline_renders_floor_present_and_absent(
    cli_store: MetrologyStore,
) -> None:
    cli_store.write_audit_run(
        make_audit_run(
            run_id="audit-1",
            project_value="github.com/manta/measured",
            findings=[make_audit_finding(category=AuditCategory.TEST_DEBT)],
        )
    )
    cli_store.write_audit_run(
        make_audit_run(
            run_id="audit-2",
            project_value="github.com/manta/unmeasured",
            findings=[make_audit_finding(category=AuditCategory.TEST_DEBT)],
        )
    )
    cli_store.write_noise_floor(
        make_noise_floor(
            project_value="github.com/manta/measured",
            total=FloorStat(min=1, max=3, mean=2.0, stddev=1.0),
            per_category={AuditCategory.TEST_DEBT: FloorStat(min=1, max=3, mean=2.0, stddev=1.0)},
        )
    )

    result = runner.invoke(app, ["metrology", "report", "baseline"])

    assert result.exit_code == 0
    output = _normalized(result.output)
    assert "github.com/manta/measured" in output
    assert "floor 1-3" in output
    assert "no floor measured" in output


def test_report_baseline_json_parses_as_the_model(cli_store: MetrologyStore) -> None:
    cli_store.write_audit_run(make_audit_run(project_value="github.com/manta/alpha"))

    result = runner.invoke(app, ["metrology", "report", "baseline", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["projects"][0]["project_id"]["value"] == "github.com/manta/alpha"
    assert "excluded" in payload


def test_report_baseline_empty_store_exits_zero(cli_store: MetrologyStore) -> None:
    """An empty result is a normal outcome, not an error."""
    result = runner.invoke(app, ["metrology", "report", "baseline"])

    assert result.exit_code == 0
    assert "No audit data." in result.output


def test_report_baseline_rejects_an_unknown_category(cli_store: MetrologyStore) -> None:
    result = runner.invoke(app, ["metrology", "report", "baseline", "--category", "not-a-category"])

    assert result.exit_code != 0
    assert "not-a-category" in _normalized(result.output)


def test_report_baseline_filters_by_category(cli_store: MetrologyStore) -> None:
    cli_store.write_audit_run(
        make_audit_run(
            project_value="github.com/manta/alpha",
            findings=[
                make_audit_finding(finding_id="F001", category=AuditCategory.TEST_DEBT),
                make_audit_finding(finding_id="F002", category=AuditCategory.SECURITY_HYGIENE),
            ],
        )
    )

    result = runner.invoke(
        app, ["metrology", "report", "baseline", "--category", "test-debt", "--json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    cells = payload["projects"][0]["cells"]
    assert len(cells) == 1
    assert cells[0]["category"] == "test-debt"
