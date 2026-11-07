from unittest import mock

import pytest

import test_support


def test_assertion() -> None:
    assert 1 == 2


def test_project_crash() -> None:
    from pkg import core

    core.explode()


def test_missing_import() -> None:
    from pkg.core import absent  # noqa: F401


def test_module_attribute_error() -> None:
    import pkg.core

    pkg.core.absent()  # type: ignore[attr-defined]


def test_mock_patch_missing_target() -> None:
    with mock.patch("pkg.core.absent"):
        pass


def test_exception_in_test_code() -> None:
    raise TypeError("raised in the test")


def test_exception_in_helper() -> None:
    test_support.raise_in_helper()


def test_passes(plain_fixture: int) -> None:
    assert plain_fixture == 7


@pytest.mark.skip(reason="skipped on purpose")
def test_skipped() -> None:
    raise AssertionError


@pytest.mark.xfail(reason="expected")
def test_expected_failure() -> None:
    assert False


@pytest.mark.parametrize("value", ["a[1]", "b"])
def test_bracketed_id(value: str) -> None:
    assert value
