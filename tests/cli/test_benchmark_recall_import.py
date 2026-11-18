"""``sq benchmark recall import`` (slice 430 D10, D8)."""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

from squadron.benchmark.recall.recall_services import RecallServices
from tests.benchmark.recall.committed import REPO_ROOT, RESULTS_DIR, load_committed_sets
from tests.benchmark.recall.support import fake_services, invoke_recall


def _services(tmp_path: Path) -> RecallServices:
    services = dataclasses.replace(fake_services(tmp_path), repo_root=REPO_ROOT)
    load_committed_sets(services.store)
    return services


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    services = _services(tmp_path)
    result = invoke_recall(services, "import", str(RESULTS_DIR), "--set", "real-bugs", "--dry-run")
    assert result.exit_code == 0, result.output
    assert "Review entries: 696" in result.output
    assert "Dry run: nothing written." in result.output
    assert services.store.list_runs() == []
    assert services.store.list_labels() == []


def test_import_then_rerun_reports_no_changes(tmp_path: Path) -> None:
    services = _services(tmp_path)
    first = invoke_recall(services, "import", str(RESULTS_DIR), "--set", "real-bugs")
    assert first.exit_code == 0, first.output
    for line in (
        "Review entries: 696",
        "Comb entries: 480",
        "Run records: 51",
        "Duplicates skipped: 27",
    ):
        assert line in first.output
    assert "Written: 51 run records, 56 label records" in first.output
    runs = services.store.list_runs()
    assert len(runs) == 51
    assert sum(len(r.reviews) for r in runs) == 696
    assert sum(len(r.combs) for r in runs) == 480
    assert all(e.case_set == "real-bugs@v1" for r in runs for e in r.reviews.values())
    entry = next(iter(runs[0].reviews.values()))
    assert entry.raw_ref is not None and services.store.reviews.get(entry.raw_ref)
    again = invoke_recall(services, "import", str(RESULTS_DIR), "--set", "real-bugs")
    assert again.exit_code == 0, again.output
    assert "No changes." in again.output


def test_skipped_file_exits_1(tmp_path: Path) -> None:
    services = _services(tmp_path)
    results = tmp_path / "results"
    grid = results / "20261112-grid2"
    grid.mkdir(parents=True)
    shutil.copy(RESULTS_DIR / "20261112-grid2" / "175-sol-1.json", grid)
    (grid / "175-broken-1.json").write_text("{", encoding="utf-8")
    result = invoke_recall(services, "import", str(results), "--set", "real-bugs")
    assert result.exit_code == 1
    assert "skipped: " in result.output and "175-broken-1.json" in result.output
    assert len(services.store.list_runs()) == 1


def test_unknown_set_is_refused(tmp_path: Path) -> None:
    result = invoke_recall(_services(tmp_path), "import", str(RESULTS_DIR), "--set", "nope")
    assert result.exit_code == 1
    assert "No recall case set" in result.output
