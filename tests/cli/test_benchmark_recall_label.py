"""``sq benchmark recall label`` (slice 430 D3) on hand-built records."""

from __future__ import annotations

from pathlib import Path

from squadron.benchmark.recall.recall_services import RecallServices
from squadron.benchmark.recall.recipe_dirs import RECIPES_DIR
from tests.benchmark.recall.scoring_support import finding, make_case, make_run, review
from tests.benchmark.recall.support import fake_services, invoke_recall

CASE = make_case()  # B1 in src/a.py, B2 in src/b.py
OPEN = finding(1, None, text="no path cited")  # candidate for both bugs
ELSEWHERE = finding(2, "src/zzz.py")  # decided miss for both


def _services(tmp_path: Path) -> RecallServices:
    services = fake_services(tmp_path)
    services.store.write_case(CASE)
    services.store.write_case_set("s", [CASE.case_id])
    services.store.put_run(make_run(CASE, 1, review("rev", (OPEN, ELSEWHERE), case_set="s@v1")))
    return services


def _recipe(tmp_path: Path) -> str:
    path = tmp_path / "rev.yaml"
    path.write_text("name: rev\nreviewers: [rev]\n", encoding="utf-8")
    return str(path)


def test_listing_shows_each_undecided_candidate(tmp_path: Path) -> None:
    result = invoke_recall(_services(tmp_path), "label", "--set", "s")
    assert result.exit_code == 0, result.output
    assert "2 undecided candidates" in result.output
    assert "demo-1 B1: wrong thing" in result.output and "demo-1 B2: wrong thing" in result.output
    assert "bug files: src/a.py" in result.output
    assert f"finding {OPEN.content_key}  [CONCERN] (no location)" in result.output
    assert "affects: (stored reviews) run 1" in result.output
    assert ELSEWHERE.content_key not in result.output
    with_recipe = invoke_recall(
        _services(tmp_path / "r"), "label", "--set", "s", "--recipe", _recipe(tmp_path)
    )
    assert "affects: rev run 1" in with_recipe.output


def test_recording_a_label_removes_it_and_drops_the_report_undecided_count(tmp_path: Path) -> None:
    services = _services(tmp_path)
    before = invoke_recall(services, "report", "--set", "s", "--recipe", _recipe(tmp_path))
    assert "| rev | 1 | 1 | 0–2/2 | 0–100% |" in before.output
    for bug, verdict in (("B1", "HIT"), ("B2", "MISS")):
        recorded = invoke_recall(
            services, "label", "--set", "s", "--hit", OPEN.content_key, bug, verdict, "--by", "pm"
        )
        assert recorded.exit_code == 0, recorded.output
        assert f"recorded {verdict} for {OPEN.content_key} {bug} as person:pm" in recorded.output
    listing = invoke_recall(services, "label", "--set", "s")
    assert "0 undecided candidates" in listing.output
    after = invoke_recall(services, "report", "--set", "s", "--recipe", _recipe(tmp_path))
    assert "| rev | 1 | 1 | 1/2 | 50% | 1/2 | 1/1 | 0 | 0 |" in after.output
    labels = services.store.get_labels(CASE.case_id, "person:pm")
    assert labels is not None and set(labels.hits[OPEN.content_key]) == {"B1", "B2"}


def test_unknown_key_or_bug_is_refused(tmp_path: Path) -> None:
    services = _services(tmp_path)
    bad_key = invoke_recall(services, "label", "--set", "s", "--hit", "nope", "B1", "HIT", "--by", "pm")
    assert bad_key.exit_code == 1 and "no stored finding has content key" in bad_key.output
    bad_bug = invoke_recall(
        services, "label", "--set", "s", "--hit", OPEN.content_key, "B9", "HIT", "--by", "pm"
    )
    assert bad_bug.exit_code == 1 and "no bug 'B9'" in bad_bug.output
    no_person = invoke_recall(services, "label", "--set", "s", "--hit", OPEN.content_key, "B1", "HIT")
    assert no_person.exit_code == 1 and "--by" in no_person.output
    assert services.store.list_labels() == []


def test_recipe_named_without_path_is_found_in_the_benchmark_dir(tmp_path: Path) -> None:
    services = _services(tmp_path)
    bench_dir = tmp_path / RECIPES_DIR
    bench_dir.mkdir(parents=True)
    (bench_dir / "rev.yaml").write_text("name: rev\nreviewers: [rev]\n", encoding="utf-8")
    result = invoke_recall(services, "label", "--set", "s", "--recipe", "rev")
    assert result.exit_code == 0, result.output
    assert "affects: rev run 1" in result.output
