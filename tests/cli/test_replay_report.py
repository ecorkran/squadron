"""``sq replay report`` against a real metrology store in a temp directory (slice 177 D7)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.replay_models import JudgeRef, PairOutcome, ReplayOutcome
from squadron.metrology.store import MetrologyStore
from tests.metrology.replay_builders import PROJECT, make_judgment, make_replay

runner = CliRunner()
_T0 = datetime(2026, 11, 1, tzinfo=UTC)
_ORIGINAL = "original:" + "a" * 40
_JUDGE = JudgeRef(alias="judge", model="claude-opus-5-5", prompt_hash="d" * 64)
_WIDE = {"COLUMNS": "220"}
_HEADERS = [
    "config",
    "n",
    "failed",
    "accepted",
    "rounds",
    "cost (priced)",
    "time",
    "BT",
    "W-L-T",
    "pairs",
]


@pytest.fixture
def store(tmp_path: Path) -> Iterator[MetrologyStore]:
    box = MetrologyStore(store_dir=tmp_path / "store")
    with (
        patch(
            "squadron.cli.commands.replay_common.derive_project_id",
            return_value=ProjectId(value=PROJECT, source=ProjectIdSource.REMOTE),
        ),
        patch("squadron.cli.commands.replay_report.resolve_store_dir", return_value=tmp_path / "store"),
        patch("squadron.cli.commands.replay_common.get_typed_config", return_value=3),
        # The global console keeps the width of whichever test created it first.
        patch("squadron.cli.commands.replay_report.get_console", return_value=Console(width=220)),
    ):
        yield box


def _fill(store: MetrologyStore) -> None:
    """Opus and haiku replays on one slice; haiku has too few valid pairs for the floor."""
    ids = {
        name: store.write_replay(
            make_replay(
                alias=alias,
                model=model,
                created_at=_T0 + timedelta(minutes=minutes),
                outcome=outcome,
                rounds=1 if outcome is ReplayOutcome.ACCEPTED else None,
            )
        )
        for name, alias, model, minutes, outcome in [
            ("o1", "opus", "claude-opus-5-5", 1, ReplayOutcome.ACCEPTED),
            ("o2", "opus", "claude-opus-5-5", 2, ReplayOutcome.FAILED),
            ("h1", "haiku", "claude-haiku-5-5", 3, ReplayOutcome.ACCEPTED),
        ]
    }
    for a, b, outcome in [
        (ids["o1"], ids["h1"], PairOutcome.A),
        (ids["o1"], _ORIGINAL, PairOutcome.TIE),
        (ids["h1"], _ORIGINAL, PairOutcome.A),
        (ids["h1"], ids["o1"], PairOutcome.B),
    ]:
        store.write_judgment(make_judgment(judge=_JUDGE, a=a, b=b, outcome=outcome))


def test_an_empty_store_prints_the_message_and_exits_0(store: MetrologyStore) -> None:
    result = runner.invoke(app, ["replay", "report"], env=_WIDE)

    assert result.exit_code == 0 and "No replays recorded" in result.output


def test_an_empty_store_with_json_is_an_empty_report(store: MetrologyStore) -> None:
    result = runner.invoke(app, ["replay", "report", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {"min_n": 3, "tables": []}


def test_the_table_has_every_column_the_original_row_and_the_footer(store: MetrologyStore) -> None:
    _fill(store)

    result = runner.invoke(app, ["replay", "report"], env=_WIDE)

    assert result.exit_code == 0, result.output
    for header in _HEADERS:
        assert header in result.output
    assert "Producer replay - design   reviewer: sonnet   judge: judge (prompt d" in result.output
    assert "original" in result.output
    assert "slices: 176" in result.output and "position consistency" in result.output
    assert "prompt identity: squadron 0.0.0, cf 0.19.13, guide unknown" in result.output
    assert "warning: the judge's model (claude-opus-5-5) is also a contestant's model" in result.output


def test_a_config_under_the_floor_is_marked(store: MetrologyStore) -> None:
    _fill(store)  # min_n is 3; haiku has 3 valid pairs, opus 3, original 3 -> raise the floor
    with patch("squadron.cli.commands.replay_common.get_typed_config", return_value=4):
        result = runner.invoke(app, ["replay", "report"], env=_WIDE)

    assert "below floor" in result.output


def test_json_mirrors_the_table(store: MetrologyStore) -> None:
    _fill(store)

    text = runner.invoke(app, ["replay", "report"], env=_WIDE).output
    data = json.loads(runner.invoke(app, ["replay", "report", "--json"]).output)

    (table,) = data["tables"]
    assert table["slices"] == [176] and table["judge"]["alias"] == "judge"
    by_label = {row["label"]: row for row in table["rows"]}
    assert set(by_label) == {
        "opus (claude-opus-5-5, sdk, effort high)",
        "haiku (claude-haiku-5-5, sdk, effort high)",
        "original",
    }
    opus = by_label["opus (claude-opus-5-5, sdk, effort high)"]
    assert (opus["n"], opus["failed"], opus["accepted"]) == (2, 1, 1)
    assert f"{opus['wins']}-{opus['losses']}-{opus['ties']}" in text
    assert data["min_n"] == 3


def test_the_judge_filter_and_phase_option_are_accepted(store: MetrologyStore) -> None:
    _fill(store)

    other = runner.invoke(app, ["replay", "report", "--judge", "nobody"], env=_WIDE)
    tasks = runner.invoke(app, ["replay", "report", "--phase", "tasks"], env=_WIDE)

    assert "judge: none yet" in other.output
    assert "No replays recorded" in tasks.output


def test_a_non_integer_evidence_floor_exits_1_naming_the_key(store: MetrologyStore) -> None:
    with patch(
        "squadron.cli.commands.replay_common.get_typed_config", side_effect=ValueError("not an int")
    ):
        result = runner.invoke(app, ["replay", "report"])

    assert result.exit_code == 1 and "metrology.min_evidence_n" in result.output
