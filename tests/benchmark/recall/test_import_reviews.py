"""Import part 1 on the real committed hand-run review outputs (slice 430 D10, D8)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import pytest

from squadron.benchmark.recall.hand_run_import import build_import_plan
from squadron.benchmark.recall.import_plan import ImportPlan
from squadron.metrology.recall_run_models import UNKNOWN_MARKER, RecallLeakVerdict
from tests.benchmark.recall.committed import RESULTS_DIR, committed_cases

SET_LABEL = "real-bugs@v1"


@pytest.fixture(scope="module")
def real_plan() -> ImportPlan:
    return build_import_plan(RESULTS_DIR, committed_cases().values(), SET_LABEL)


def test_real_files_give_696_entries_in_51_runs(real_plan: ImportPlan) -> None:
    assert real_plan.review_entries == 696
    assert len(real_plan.runs) == 51
    findings = sum(len(e.findings) for r in real_plan.runs.values() for e in r.reviews.values())
    assert findings == 3619


def test_all_grid1_files_are_listed_duplicates(real_plan: ImportPlan) -> None:
    assert len(real_plan.duplicates) == 27
    assert all("20261112-grid1" in line.split(" (")[0] for line in real_plan.duplicates)


def test_imported_entries_carry_d10_markers(real_plan: ImportPlan) -> None:
    entries = [e for r in real_plan.runs.values() for e in r.reviews.values()]
    assert all(e.effort_sent is None for e in entries)
    assert all(e.leak is RecallLeakVerdict.NOT_SCANNED for e in entries)
    assert all(str(e.config.template_hash).startswith(f"{UNKNOWN_MARKER}:code@") for e in entries)
    assert all(e.raw_ref in real_plan.raw_outputs for e in entries)
    sonnet = {e.config.tool_use for e in entries if e.alias in {"sonnet", "sonnet_notools"}}
    assert sonnet == {True, False}


def test_unknown_counts_present(real_plan: ImportPlan) -> None:
    assert real_plan.unknown_counts["template_hash"] == 696
    assert real_plan.unknown_counts["tool_use"] > 0


def _small_results(tmp_path: Path) -> Path:
    root = tmp_path / "results"
    grid = root / "20261112-grid2"
    grid.mkdir(parents=True)
    shutil.copy(RESULTS_DIR / "20261112-grid2" / "175-sol-1.json", grid)
    return root


def test_bad_files_are_skipped_with_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    root = _small_results(tmp_path)
    grid = root / "20261112-grid2"
    (grid / "175-broken-1.json").write_text("{not json", encoding="utf-8")
    (grid / "175-nofields-1.json").write_text('{"findings": []}', encoding="utf-8")
    (grid / "175-dir-1.json").mkdir()  # read_bytes raises: unreadable
    with caplog.at_level(logging.WARNING):
        plan = build_import_plan(root, committed_cases().values(), SET_LABEL)
    assert plan.review_entries == 1
    reasons = {Path(item.item).name: item.reason for item in plan.skipped}
    assert set(reasons) == {"175-broken-1.json", "175-nofields-1.json", "175-dir-1.json"}
    assert "not valid JSON" in reasons["175-broken-1.json"]
    assert "missing field" in reasons["175-nofields-1.json"]
    assert "unreadable" in reasons["175-dir-1.json"]
    warned = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len([m for m in warned if "import skipped" in m]) == 3


def test_file_with_no_case_is_skipped(tmp_path: Path) -> None:
    root = _small_results(tmp_path)
    source = root / "20261112-grid2" / "175-sol-1.json"
    # One extra byte, so the copy is not a duplicate of the 175 file.
    (root / "20261112-grid2" / "zz9-sol-1.json").write_bytes(source.read_bytes() + b"\n")
    plan = build_import_plan(root, committed_cases().values(), SET_LABEL)
    assert [Path(s.item).name for s in plan.skipped] == ["zz9-sol-1.json"]
