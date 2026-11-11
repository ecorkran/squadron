from fixpkg import exported_function


def test_new_behavior(extra_value):
    assert exported_function(extra_value) == 10
