"""Trace plugin, trace mode: patch interception (slice 422 D7).

Real pytest runs (no venv) over ``fixfair_project``. A patch is
``[api, owner_kind, owner_module, target]`` where the owner is the object being modified.
"""

from __future__ import annotations

import sys
import unittest.mock as mock
from pathlib import Path
from typing import Any

import pytest

from tests.benchmark.support import git_tree, run_trace_plugin, trace_plugin_dir

PREFIX = "tests/test_boundary_patches.py::"
MOD = "fixpkg.mod"


def project_module(api: str, target: str) -> list[str]:
    return [api, "project_module", MOD, target]


@pytest.fixture(scope="module")
def run_output(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("trace_patches")
    run = run_trace_plugin(
        git_tree("fixfair_project", root), root / "out", "trace", ["tests/test_boundary_patches.py"]
    )
    assert run.returncode == 0, run.stderr
    return run.output


def patches(run_output: dict[str, Any], name: str) -> list[list[str]]:
    return run_output["nodes"][f"{PREFIX}{name}"]["patches"]


def test_patch_of_a_name_in_a_project_module_is_a_project_module_patch(
    run_output: dict[str, Any],
) -> None:
    """``patch("fixpkg.mod.run")`` modifies fixpkg.mod, though ``run`` came from subprocess."""
    assert patches(run_output, "test_patch_project_module_by_string") == [
        project_module("mock.patch", "fixpkg.mod.run")
    ]


def test_patching_a_foreign_module_is_foreign(run_output: dict[str, Any]) -> None:
    assert patches(run_output, "test_patch_foreign_subprocess_run") == [
        ["mock.patch", "foreign", "subprocess", "subprocess.run"]
    ]


def test_monkeypatch_environment_changes_are_foreign(run_output: dict[str, Any]) -> None:
    recorded = patches(run_output, "test_monkeypatch_env_is_foreign")
    assert [(api, kind) for api, kind, _, _ in recorded] == [
        ("monkeypatch.delitem", "foreign"),
        ("monkeypatch.setitem", "foreign"),
    ]


def test_patch_dict_on_the_environment_is_foreign(run_output: dict[str, Any]) -> None:
    assert patches(run_output, "test_patch_dict_on_os_environ_is_foreign") == [
        ["mock.patch.dict", "foreign", "", "<mapping>"]
    ]


def test_patch_object_on_a_project_class(run_output: dict[str, Any]) -> None:
    assert patches(run_output, "test_patch_object_on_a_project_class") == [
        ["mock.patch", "project_class", "fixpkg.internal", "fixpkg.internal.InternalWidget.run"]
    ]


def test_monkeypatch_setattr_on_an_instance_of_a_project_class(run_output: dict[str, Any]) -> None:
    assert patches(run_output, "test_monkeypatch_setattr_on_a_project_instance") == [
        [
            "monkeypatch.setattr",
            "project_instance",
            "fixpkg.internal",
            "fixpkg.internal.InternalWidget.size",
        ]
    ]


@pytest.mark.parametrize(
    "name",
    ["test_patch_dict_on_a_project_dict_object", "test_patch_dict_on_a_project_dict_by_string"],
)
def test_patch_dict_on_a_project_dict(run_output: dict[str, Any], name: str) -> None:
    assert patches(run_output, name) == [project_module("mock.patch.dict", "fixpkg.mod.REGISTRY")]


def test_monkeypatch_delattr_on_a_project_module_attribute(run_output: dict[str, Any]) -> None:
    assert patches(run_output, "test_monkeypatch_delattr_on_a_project_module_attribute") == [
        project_module("monkeypatch.delattr", "fixpkg.mod.setting")
    ]


def test_monkeypatch_setitem_and_delitem_on_a_project_dict(run_output: dict[str, Any]) -> None:
    assert patches(run_output, "test_monkeypatch_setitem_and_delitem_on_a_project_dict") == [
        project_module("monkeypatch.delitem", "fixpkg.mod.REGISTRY['a']"),
        project_module("monkeypatch.setitem", "fixpkg.mod.REGISTRY['d']"),
    ]


def test_monkeypatch_setattr_by_dotted_string(run_output: dict[str, Any]) -> None:
    assert patches(run_output, "test_monkeypatch_setattr_by_dotted_string") == [
        project_module("monkeypatch.setattr", "fixpkg.mod.run")
    ]


@pytest.mark.parametrize(
    "name", ["test_patch_start_and_stop_is_recorded_once", "test_patch_as_a_decorator"]
)
def test_start_and_decorator_forms_are_recorded_once(run_output: dict[str, Any], name: str) -> None:
    assert patches(run_output, name) == [project_module("mock.patch", "fixpkg.mod.run")]


def test_patch_multiple_records_each_patched_name(run_output: dict[str, Any]) -> None:
    assert patches(run_output, "test_patch_multiple_on_a_project_module") == [
        project_module("mock.patch", "fixpkg.mod.run"),
        project_module("mock.patch", "fixpkg.mod.setting"),
    ]


@pytest.mark.parametrize(
    ("name", "api", "target"),
    [
        ("test_patch_target_whose_module_does_not_exist", "mock.patch", "fixpkg.no_such_module.thing"),
        (
            "test_patch_target_whose_attribute_does_not_exist",
            "mock.patch",
            "fixpkg.mod.no_such_attribute",
        ),
        (
            "test_monkeypatch_dotted_string_that_does_not_resolve",
            "monkeypatch.setattr",
            "fixpkg.no_such_module.thing",
        ),
    ],
)
def test_a_target_that_does_not_resolve_is_unresolved(
    run_output: dict[str, Any], name: str, api: str, target: str
) -> None:
    assert patches(run_output, name) == [[api, "unresolved", "", target]]


def test_wrappers_are_removed_when_the_interceptor_is_uninstalled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.syspath_prepend(str(trace_plugin_dir()))
    import squadron_fixcase_closure  # pyright: ignore[reportMissingImports]
    import squadron_fixcase_patches  # pyright: ignore[reportMissingImports]

    originals = {
        "patch_enter": mock._patch.__enter__,  # type: ignore[attr-defined]
        "dict_enter": mock._patch_dict.__enter__,  # type: ignore[attr-defined]
        "setattr": pytest.MonkeyPatch.setattr,
        "delattr": pytest.MonkeyPatch.delattr,
        "setitem": pytest.MonkeyPatch.setitem,
        "delitem": pytest.MonkeyPatch.delitem,
    }
    interceptor = squadron_fixcase_patches.PatchInterceptor(
        squadron_fixcase_closure.ClosureBuilder(tmp_path, [])
    )
    interceptor.install()
    try:
        assert mock._patch.__enter__ is not originals["patch_enter"]  # type: ignore[attr-defined]
        assert pytest.MonkeyPatch.setattr is not originals["setattr"]
    finally:
        interceptor.uninstall()
    assert mock._patch.__enter__ is originals["patch_enter"]  # type: ignore[attr-defined]
    assert mock._patch_dict.__enter__ is originals["dict_enter"]  # type: ignore[attr-defined]
    assert pytest.MonkeyPatch.setattr is originals["setattr"]
    assert pytest.MonkeyPatch.delattr is originals["delattr"]
    assert pytest.MonkeyPatch.setitem is originals["setitem"]
    assert pytest.MonkeyPatch.delitem is originals["delitem"]
    sys.modules.pop("squadron_fixcase_patches", None)
    sys.modules.pop("squadron_fixcase_closure", None)
