from calc import add, sub


def test_add() -> None:
    assert add(2, 3) == 5


def test_add_negative() -> None:
    assert add(-2, -3) == -5


def test_sub() -> None:
    assert sub(5, 3) == 2
