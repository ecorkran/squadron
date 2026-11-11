from fixpkg.pricing import apply_discount


def test_discount_is_a_percentage():
    assert apply_discount(200, 10) == 180
