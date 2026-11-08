import helpers
import pytest

from fixpkg import exported_function

EXPECTED_DOUBLE = 6


def test_direct_body():
    assert exported_function(3) == EXPECTED_DOUBLE
    assert exported_function(0) == 0


def test_uses_conftest_fixture(scale):
    assert exported_function(scale) == EXPECTED_DOUBLE


def test_uses_helper_chain():
    assert helpers.outer_helper(1) == 4


@pytest.mark.parametrize("n", [1, 2], ids=["one", "two"])
def test_parametrized(n):
    assert exported_function(n) == n * 2


@pytest.mark.parametrize("label", ["a[b]"])
def test_bracket_id(label):
    assert label


def test_workdir_fixture(workdir):
    assert workdir.name == "work"
