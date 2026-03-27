"""Tests for ProviderCapabilities dataclass."""

from __future__ import annotations

import pytest

from squadron.providers.base import ProviderCapabilities


class TestDefaults:
    def test_can_read_files_defaults_false(self) -> None:
        assert ProviderCapabilities().can_read_files is False

    def test_supports_system_prompt_defaults_true(self) -> None:
        assert ProviderCapabilities().supports_system_prompt is True

    def test_supports_streaming_defaults_false(self) -> None:
        assert ProviderCapabilities().supports_streaming is False


class TestFrozen:
    def test_assignment_raises(self) -> None:
        caps = ProviderCapabilities()
        with pytest.raises(AttributeError):
            caps.can_read_files = True  # type: ignore[misc]


class TestProviderCapabilities:
    def test_openai_provider_cannot_read_files(self) -> None:
        from squadron.providers.openai.provider import OpenAICompatibleProvider

        assert OpenAICompatibleProvider().capabilities.can_read_files is False

    def test_sdk_provider_can_read_files(self) -> None:
        from squadron.providers.sdk.provider import ClaudeSDKProvider

        assert ClaudeSDKProvider().capabilities.can_read_files is True

    def test_openai_supports_streaming(self) -> None:
        from squadron.providers.openai.provider import OpenAICompatibleProvider

        assert OpenAICompatibleProvider().capabilities.supports_streaming is True

    def test_sdk_supports_streaming(self) -> None:
        from squadron.providers.sdk.provider import ClaudeSDKProvider

        assert ClaudeSDKProvider().capabilities.supports_streaming is True
