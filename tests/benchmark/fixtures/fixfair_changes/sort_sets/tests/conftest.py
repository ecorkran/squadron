import pytest


@pytest.fixture
def scale():
    return 3


@pytest.fixture
def workdir(tmp_path):
    return tmp_path / "work"


@pytest.fixture
def extra_value():
    return 5
