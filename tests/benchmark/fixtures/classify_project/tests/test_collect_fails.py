import module_that_does_not_exist  # noqa: F401


def test_never_collected() -> None:
    pass
