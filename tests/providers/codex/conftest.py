"""Shared fixtures for the Codex provider tests."""

from __future__ import annotations

from collections.abc import Generator

import pytest

from tests.providers.codex.fake_sdk import FakeSdk, installed_fake_sdk


@pytest.fixture()
def fake_sdk() -> Generator[FakeSdk]:
    """Install the fake ``openai_codex`` SDK and resolve the runtime as bundled."""
    with installed_fake_sdk() as sdk:
        yield sdk
