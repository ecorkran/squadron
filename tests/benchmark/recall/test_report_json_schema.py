"""The ``report --json`` schema is fixed for slice 433."""

from __future__ import annotations

from squadron.benchmark.recall.report_json import RecallReportJson

EXPECTED_TOP = {
    "category", "case_set", "case_set_version", "n_cases", "known_bugs", "run_indexes",
    "newest_entry", "rows", "paired",
}  # fmt: skip
EXPECTED_ROW = {
    "label", "key", "recipe", "flagged", "source", "cases", "runs", "pairs", "bug_hits",
    "bug_slots", "recall", "bugs_found", "bugs_total", "runs_with_hit", "adjacent", "undecided",
    "findings_per_run", "matched_nothing", "real_share", "graded", "passes", "person_checked",
    "person_agree", "cost_per_run", "cost_bases", "leaks", "dropped", "left_out",
    "other_set_entries",
}  # fmt: skip
EXPECTED_PAIRED = {"a", "b", "metric", "n", "mean", "low", "high", "verdict", "left_out_undecided"}


def test_report_json_schema_is_fixed() -> None:
    schema = RecallReportJson.model_json_schema()
    assert set(schema["properties"]) == EXPECTED_TOP
    assert set(schema["required"]) == EXPECTED_TOP
    defs = schema["$defs"]
    assert set(defs["RowJson"]["properties"]) == EXPECTED_ROW
    assert set(defs["PairedJson"]["properties"]) == EXPECTED_PAIRED
    assert set(defs["BoundsJson"]["properties"]) == {"low", "high"}
