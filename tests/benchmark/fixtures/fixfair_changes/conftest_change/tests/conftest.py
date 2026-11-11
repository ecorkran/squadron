import pytest


@pytest.fixture
def scale():
    return 4


@pytest.fixture
def workdir(tmp_path):
    return tmp_path / "work"
