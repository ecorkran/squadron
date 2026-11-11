import contextlib
import sys

import pytest

from fixpkg import exported_function
from fixpkg.internal import InternalWidget, internal_function


def test_cross_exported_function():
    assert exported_function(2) == 4


def test_cross_internal_function():
    assert internal_function(1) == 101


def test_cross_constructor_and_method():
    widget = InternalWidget(3)
    assert widget.run() == 6


def test_cross_callback_run_by_exitstack():
    # internal_function is called by contextlib's frame, not by this test.
    with contextlib.ExitStack() as stack:
        stack.callback(internal_function, 1)


def test_cross_second_independent_test():
    assert exported_function(5) == 10


@pytest.fixture
def widget():
    return InternalWidget(4)


def test_cross_through_a_fixture_and_a_method(widget):
    assert widget.run() == 8


def test_cross_nested_function_is_a_function():
    def local():
        return exported_function(1)

    assert local() == 2


def test_cross_restores_a_profiler_the_test_replaced():
    previous = sys.getprofile()
    sys.setprofile(lambda frame, event, arg: None)
    try:
        assert exported_function(1) == 2
    finally:
        sys.setprofile(previous)


def test_cross_leaves_its_own_profiler_installed():
    sys.setprofile(lambda frame, event, arg: None)
    assert exported_function(1) == 2


def test_cross_after_a_test_that_left_a_profiler():
    assert exported_function(7) == 14
