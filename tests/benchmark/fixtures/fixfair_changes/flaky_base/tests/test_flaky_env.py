"""Alternates between passing and failing on every run, through a state file beside it."""

from pathlib import Path

STATE = Path(__file__).parent / ".flaky_state"


def test_alternates():
    count = int(STATE.read_text()) + 1 if STATE.exists() else 1
    STATE.write_text(str(count))
    assert count % 2 == 1
