"""The recorded cf adoption fixtures parse and carry the report version."""

from pathlib import Path

import pytest

from tests.fixtures.cf_adoption import load_fixture

_FIXTURE_DIR = Path(__file__).parent / "cf_adoption"
_REPORT_FIXTURES = sorted(
    p.stem for p in _FIXTURE_DIR.glob("*.json") if p.stem.startswith(("detect-", "init-"))
)


@pytest.mark.parametrize("name", sorted(p.stem for p in _FIXTURE_DIR.glob("*.json")))
def test_fixture_parses(name: str) -> None:
    load_fixture(name)


@pytest.mark.parametrize("name", _REPORT_FIXTURES)
def test_report_fixture_has_report_version(name: str) -> None:
    data = load_fixture(name)
    assert isinstance(data, dict)
    assert data["reportVersion"] == 1
