"""A test helper: matches test_*.py, so it counts as test code, not project source."""


def raise_in_helper() -> None:
    raise ValueError("raised in a test helper")
