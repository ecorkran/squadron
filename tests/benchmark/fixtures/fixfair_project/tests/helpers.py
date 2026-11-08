"""Test-side helpers, reached from tests two calls deep."""

LIMIT = 10


def inner_helper(value):
    return value + 1


def outer_helper(value):
    return inner_helper(value) * 2
