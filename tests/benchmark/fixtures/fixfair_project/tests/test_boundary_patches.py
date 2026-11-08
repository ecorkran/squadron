import os
from unittest import mock
from unittest.mock import patch

import fixpkg.mod
import pytest

from fixpkg.internal import InternalWidget


def test_patch_project_module_by_string():
    with patch("fixpkg.mod.run") as fake:
        fixpkg.mod.execute(["echo"])
    assert fake.called


def test_patch_foreign_subprocess_run():
    with patch("subprocess.run") as fake:
        fake.return_value = None
    assert fake is not None


def test_monkeypatch_env_is_foreign(monkeypatch):
    monkeypatch.setenv("FIXFAIR_VALUE", "1")
    monkeypatch.delenv("FIXFAIR_VALUE")
    assert "FIXFAIR_VALUE" not in os.environ


def test_patch_dict_on_os_environ_is_foreign():
    with patch.dict(os.environ, {"FIXFAIR_OTHER": "x"}):
        assert os.environ["FIXFAIR_OTHER"] == "x"


def test_patch_object_on_a_project_class():
    with patch.object(InternalWidget, "run", return_value=0) as fake:
        assert InternalWidget(1).run() == 0
    assert fake.called


def test_monkeypatch_setattr_on_a_project_instance(monkeypatch):
    widget = InternalWidget(1)
    monkeypatch.setattr(widget, "size", 9)
    assert widget.run() == 18


def test_patch_dict_on_a_project_dict_object():
    with patch.dict(fixpkg.mod.REGISTRY, {"b": 2}):
        assert fixpkg.mod.REGISTRY["b"] == 2


def test_patch_dict_on_a_project_dict_by_string():
    with patch.dict("fixpkg.mod.REGISTRY", {"c": 3}):
        assert fixpkg.mod.REGISTRY["c"] == 3


def test_monkeypatch_delattr_on_a_project_module_attribute(monkeypatch):
    monkeypatch.delattr(fixpkg.mod, "setting")
    assert not hasattr(fixpkg.mod, "setting")


def test_monkeypatch_setitem_and_delitem_on_a_project_dict(monkeypatch):
    monkeypatch.setitem(fixpkg.mod.REGISTRY, "d", 4)
    monkeypatch.delitem(fixpkg.mod.REGISTRY, "a")
    assert "a" not in fixpkg.mod.REGISTRY


def test_monkeypatch_setattr_by_dotted_string(monkeypatch):
    monkeypatch.setattr("fixpkg.mod.run", lambda *args, **kwargs: None)
    assert fixpkg.mod.execute(["echo"]) is None


def test_patch_start_and_stop_is_recorded_once():
    patcher = patch("fixpkg.mod.run")
    patcher.start()
    patcher.stop()


@patch("fixpkg.mod.run")
def test_patch_as_a_decorator(fake):
    fixpkg.mod.execute(["echo"])
    assert fake.called


def test_patch_multiple_on_a_project_module():
    with mock.patch.multiple("fixpkg.mod", run=mock.DEFAULT, setting=5):
        assert fixpkg.mod.setting == 5


def test_patch_target_whose_module_does_not_exist():
    # Which of the two mock raises depends on the Python version.
    with pytest.raises((ImportError, AttributeError)):
        patch("fixpkg.no_such_module.thing").start()


def test_patch_target_whose_attribute_does_not_exist():
    with pytest.raises(AttributeError):
        patch("fixpkg.mod.no_such_attribute").start()


def test_monkeypatch_dotted_string_that_does_not_resolve(monkeypatch):
    with pytest.raises(ImportError):
        monkeypatch.setattr("fixpkg.no_such_module.thing", 1)
