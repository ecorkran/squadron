import boundary_helpers
import fixpkg.internal
import pytest

from fixpkg import exported_function
from fixpkg.cli import main
from fixpkg.internal import InternalWidget, internal_function


def test_ref_exported_function():
    assert exported_function(2) == 4


def test_ref_internal_function():
    assert internal_function(1) == 101


def test_ref_non_exported_class():
    assert InternalWidget(2).run() == 4


def test_ref_project_module_object():
    assert fixpkg.internal.internal_function(1) == 101


@pytest.fixture
def internal_value():
    return internal_function(2)


def test_fixture_reaches_internal(internal_value):
    assert internal_value == 102


def test_helper_reaches_internal():
    assert boundary_helpers.helper_calls_internal() == 101


def test_drives_the_cli_entry_point():
    assert main([]) == 0


def test_lambda_names_a_project_function():
    assert (lambda: exported_function(1))() == 2


def test_comprehension_names_a_project_function():
    assert [internal_function(n) for n in (1, 2)] == [101, 102]


def test_names_nothing_from_the_project():
    assert 1 + 1 == 2
