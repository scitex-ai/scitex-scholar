"""Behavioral tests for scitex_scholar.auth.ScholarAuthManager."""

import asyncio

import pytest

from scitex_scholar.auth.providers.BaseAuthenticator import BaseAuthenticator


def test_import_ScholarAuthManager_module_loads_via_importorskip():
    """Module loads via ``pytest.importorskip`` and reports its declared name.

    The import itself is the production behaviour under test (a
    missing dependency is reported as a skip, not a pass). The
    single assertion verifies the loaded module's ``__name__``
    matches the requested dotted path — catches accidental aliasing
    and packaging-path drift, which a bare import does not.
    """
    # Arrange
    name = "scitex_scholar.auth.ScholarAuthManager"
    # Act
    mod = pytest.importorskip(name)
    # Assert
    assert mod.__name__ == name


class _FakeFailingAuthenticator(BaseAuthenticator):
    """Real (non-mock) authenticator stand-in whose authentication always fails."""

    async def is_authenticate_async(self, verify_live: bool = False) -> bool:
        return False

    async def authenticate_async(self, **kwargs) -> dict:
        return {}

    async def get_auth_headers_async(self) -> dict:
        return {}

    async def get_auth_cookies_async(self) -> list:
        return []

    async def logout_async(self) -> None:
        return None

    async def get_session_info_async(self) -> dict:
        return {}


class TestEnsureAuthenticateAsyncNoProvidersConfigured:
    """Regression: open-access-only usage must not hard-fail (#scholar-ai-for-science)."""

    def test_ensure_authenticate_returns_false_when_no_providers_configured(self):
        # Arrange
        from scitex_scholar.auth.ScholarAuthManager import ScholarAuthManager

        manager = ScholarAuthManager(
            email_openathens=None, email_ezproxy=None, email_shibboleth=None
        )
        # Act
        result = asyncio.run(manager.ensure_authenticate_async())
        # Assert
        assert result is False

    def test_authenticate_async_still_raises_when_no_providers_configured(self):
        """authenticate_async itself is unchanged: calling it directly with
        no providers is still an explicit error, distinct from the
        ensure_authenticate_async anonymous-fallback path."""
        # Arrange
        from scitex_logging import AuthenticationError
        from scitex_scholar.auth.ScholarAuthManager import ScholarAuthManager

        manager = ScholarAuthManager(
            email_openathens=None, email_ezproxy=None, email_shibboleth=None
        )
        # Act
        # Assert
        with pytest.raises(AuthenticationError):
            asyncio.run(manager.authenticate_async())

    def test_ensure_authenticate_raises_when_provider_configured_but_fails(self):
        """When a provider IS configured, a failed authentication attempt
        must still surface as an error (no silent fallback for a genuinely
        broken/expired institutional login)."""
        # Arrange
        from scitex_logging import AuthenticationError
        from scitex_scholar.auth.ScholarAuthManager import ScholarAuthManager

        manager = ScholarAuthManager(
            email_openathens=None, email_ezproxy=None, email_shibboleth=None
        )
        manager._register_provider("fake", _FakeFailingAuthenticator())
        # Act
        # Assert
        with pytest.raises(AuthenticationError):
            asyncio.run(manager.ensure_authenticate_async())

# EOF
