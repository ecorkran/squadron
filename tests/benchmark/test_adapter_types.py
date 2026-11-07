"""Adapter seam types: identity digest behavior."""

from __future__ import annotations

import pytest

from squadron.benchmark.adapter import EnvironmentIdentity, SuiteSelection
from squadron.metrology.snapshot_models import SourceLanguage


def identity(**overrides: object) -> EnvironmentIdentity:
    fields: dict[str, object] = {
        "language": SourceLanguage.PYTHON,
        "lockfile_path": "uv.lock",
        "lockfile_sha256": "a" * 64,
        "interpreter_version": "Python 3.12.1",
        "installer_version": "uv 0.5.0",
        "platform": "darwin-arm64",
        "scrub_spec_version": 1,
    }
    fields.update(overrides)
    return EnvironmentIdentity.model_validate(fields)


CHANGES: dict[str, object] = {
    "language": SourceLanguage.TYPESCRIPT,
    "lockfile_path": "other.lock",
    "lockfile_sha256": "b" * 64,
    "interpreter_version": "Python 3.13.0",
    "installer_version": "uv 0.6.0",
    "platform": "linux-x86_64",
    "scrub_spec_version": 2,
}


@pytest.mark.parametrize("field", sorted(CHANGES))
def test_digest_changes_with_every_field(field: str) -> None:
    assert identity(**{field: CHANGES[field]}).identity_digest != identity().identity_digest


def test_digest_is_stable_and_in_dump() -> None:
    assert identity().identity_digest == identity().identity_digest
    assert identity().model_dump()["identity_digest"] == identity().identity_digest


def test_selection_constructors() -> None:
    assert SuiteSelection.all_tests().node_ids is None
    selection = SuiteSelection.nodes(("a::b",), deselect=("c::d",))
    assert selection.node_ids == ("a::b",)
    assert selection.deselect == ("c::d",)
