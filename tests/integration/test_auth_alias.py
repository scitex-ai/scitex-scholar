"""Regression test for scitex-scholar#23 — is_authenticated_async alias."""

from __future__ import annotations

import inspect


class TestIsAuthenticatedAsyncAlias:
    def test_openathens_has_both_spellings_hasattr_openathensauthenticator_is_authenticate_async(self):
        # Arrange
        # Act
        from scitex_scholar.auth.providers.OpenAthensAuthenticator import (
            OpenAthensAuthenticator,
        )
        # Act
        # Assert
        assert hasattr(OpenAthensAuthenticator, "is_authenticate_async")

    def test_openathens_has_both_spellings_hasattr_openathensauthenticator_is_authenticated_async(self):
        # Arrange
        # Act
        from scitex_scholar.auth.providers.OpenAthensAuthenticator import (
            OpenAthensAuthenticator,
        )
        # Act
        # Assert
        assert hasattr(OpenAthensAuthenticator, "is_authenticated_async")

    def test_openathens_has_both_spellings_inspect_iscoroutinefunction_openathensauthenticator_is_authe(self):
        # Arrange
        # Act
        from scitex_scholar.auth.providers.OpenAthensAuthenticator import (
            OpenAthensAuthenticator,
        )
        # Act
        # Assert
        assert inspect.iscoroutinefunction(
            OpenAthensAuthenticator.is_authenticated_async
        )


    def test_shibboleth_has_both_spellings_hasattr_shibbolethauthenticator_is_authenticate_async(self):
        # Arrange
        # Act
        from scitex_scholar.auth.providers.ShibbolethAuthenticator import (
            ShibbolethAuthenticator,
        )
        # Act
        # Assert
        assert hasattr(ShibbolethAuthenticator, "is_authenticate_async")

    def test_shibboleth_has_both_spellings_hasattr_shibbolethauthenticator_is_authenticated_async(self):
        # Arrange
        # Act
        from scitex_scholar.auth.providers.ShibbolethAuthenticator import (
            ShibbolethAuthenticator,
        )
        # Act
        # Assert
        assert hasattr(ShibbolethAuthenticator, "is_authenticated_async")


    def test_ezproxy_has_both_spellings_hasattr_ezproxyauthenticator_is_authenticate_async(self):
        # Arrange
        # Act
        from scitex_scholar.auth.providers.EZProxyAuthenticator import (
            EZProxyAuthenticator,
        )
        # Act
        # Assert
        assert hasattr(EZProxyAuthenticator, "is_authenticate_async")

    def test_ezproxy_has_both_spellings_hasattr_ezproxyauthenticator_is_authenticated_async(self):
        # Arrange
        # Act
        from scitex_scholar.auth.providers.EZProxyAuthenticator import (
            EZProxyAuthenticator,
        )
        # Act
        # Assert
        assert hasattr(EZProxyAuthenticator, "is_authenticated_async")



# EOF
