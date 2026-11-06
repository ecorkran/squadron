"""CredentialGrant and the auth carryover table."""

from __future__ import annotations

import pytest

from squadron.benchmark.auth_carryover import AUTH_CARRYOVER_FILES
from squadron.benchmark.scrubbed_env import CredentialGrant
from squadron.providers.base import ProfileName
from squadron.providers.profiles import get_profile


def test_every_profile_has_an_explicit_table_entry() -> None:
    assert set(AUTH_CARRYOVER_FILES) == set(ProfileName)


def test_none_grants_nothing() -> None:
    grant = CredentialGrant.none()
    assert grant.variables == ()
    assert grant.carryover_files == ()


@pytest.mark.parametrize("name", [ProfileName.OPENAI, ProfileName.GEMINI])
def test_api_key_profile_grants_exactly_its_variable(name: ProfileName) -> None:
    grant = CredentialGrant.for_profiles([name])
    assert grant.variables == (get_profile(name).api_key_env,)
    assert grant.carryover_files == ()


@pytest.mark.parametrize("name", [ProfileName.SDK, ProfileName.OPENAI_OAUTH])
def test_session_profile_grants_file_and_no_variable(name: ProfileName) -> None:
    grant = CredentialGrant.for_profiles([name])
    assert grant.variables == ()
    assert grant.carryover_files == AUTH_CARRYOVER_FILES[name]
    assert len(grant.carryover_files) == 1
