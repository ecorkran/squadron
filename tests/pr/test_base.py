"""Tests for select_base (D1) — one case per table row, plus the refusal."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from squadron.codehost.models import RepositoryLocator
from squadron.pr.base import (
    BaseSource,
    IntegrationBranchAbsentError,
    select_base,
)

LOCATOR = RepositoryLocator(
    host="github.com", owner="ecorkran", repository="squadron", remote_name="origin"
)


def _host(*, branch_exists: bool = True, default_branch: str = "main") -> MagicMock:
    host = MagicMock()
    host.branch_exists.return_value = branch_exists
    host.default_branch.return_value = default_branch
    return host


def _cf_client(value: str | None) -> MagicMock:
    """A fake cf client whose get_config returns *value*, or raises if None."""
    client = MagicMock()
    if value is None:
        from squadron.integrations.context_forge import ContextForgeNotAvailable

        client.get_config.side_effect = ContextForgeNotAvailable("cf not on PATH")
    else:
        client.get_config.return_value = value
    return client


def test_base_flag_wins_with_no_host_confirmation() -> None:
    host = _host()
    selection = select_base(host, LOCATOR, base_flag="release", cwd=".", cf_client=_cf_client("dev"))
    assert selection.base == "release"
    assert selection.source == BaseSource.FLAG
    host.branch_exists.assert_not_called()


def test_integration_branch_set_and_present_is_used() -> None:
    host = _host(branch_exists=True)
    selection = select_base(host, LOCATOR, base_flag=None, cwd=".", cf_client=_cf_client("dev/erik"))
    assert selection.base == "dev/erik"
    assert selection.source == BaseSource.INTEGRATION_BRANCH


def test_integration_branch_set_and_absent_refuses_naming_it() -> None:
    host = _host(branch_exists=False)
    with pytest.raises(IntegrationBranchAbsentError) as exc_info:
        select_base(host, LOCATOR, base_flag=None, cwd=".", cf_client=_cf_client("dev/does-not-exist"))
    assert "dev/does-not-exist" in str(exc_info.value)
    host.default_branch.assert_not_called()


def test_integration_branch_unset_uses_host_default() -> None:
    host = _host(default_branch="main")
    selection = select_base(host, LOCATOR, base_flag=None, cwd=".", cf_client=_cf_client(""))
    assert selection.base == "main"
    assert selection.source == BaseSource.HOST_DEFAULT


def test_cf_unavailable_uses_host_default_without_raising() -> None:
    host = _host(default_branch="main")
    selection = select_base(host, LOCATOR, base_flag=None, cwd=".", cf_client=_cf_client(None))
    assert selection.base == "main"
    assert selection.source == BaseSource.HOST_DEFAULT


def test_cf_returns_empty_string_uses_host_default() -> None:
    host = _host(default_branch="main")
    selection = select_base(host, LOCATOR, base_flag=None, cwd=".", cf_client=_cf_client("   "))
    assert selection.base == "main"
    assert selection.source == BaseSource.HOST_DEFAULT
