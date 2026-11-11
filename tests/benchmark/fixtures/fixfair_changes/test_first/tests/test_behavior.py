from fixpkg import exported_function


def test_negative_is_clamped():
    assert exported_function(-1) == 0
