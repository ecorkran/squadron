"""Recorded cf adoption reports (cf 271 D3, D5, D8) for tests."""

import json
from pathlib import Path

_FIXTURE_DIR = Path(__file__).parent


def load_fixture(name: str) -> object:
    """Return the parsed JSON of fixture ``name`` (file name without ``.json``)."""
    return json.loads((_FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))


def fixture_text(name: str) -> str:
    """Return the raw JSON text of fixture ``name``, as cf would print it."""
    return (_FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8")
