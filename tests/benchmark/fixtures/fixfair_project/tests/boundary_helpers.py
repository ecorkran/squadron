"""A test-side helper that reaches project internals on the test's behalf."""

from fixpkg.internal import internal_function


def helper_calls_internal():
    return internal_function(1)
