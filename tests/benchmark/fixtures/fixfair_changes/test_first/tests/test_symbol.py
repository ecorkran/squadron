import fixpkg.api as api


def test_uses_added_symbol():
    assert api.added_by_fix(2) == 6
