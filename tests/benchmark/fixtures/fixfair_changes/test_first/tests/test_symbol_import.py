from fixpkg.api import added_by_fix


def test_imports_added_symbol():
    assert added_by_fix(1) == 3
