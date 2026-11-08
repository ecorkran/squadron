from fixpkg import exported_function


def test_none_input_returns_zero():
    assert exported_function(None) == 0
