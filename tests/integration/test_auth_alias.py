"""Regression test for scitex-scholar#23 — is_authenticated_async alias."""

from __future__ import annotations

import inspect


class TestIsAuthenticatedAsyncAlias:
    def test_openathens_has_both_spellings(self):
        """Past-tense `is_authenticated_async` and verb `is_authenticate_async`
        must both be attributes on every Authenticator subclass, since the
        codebase has callers using both."""
        from scitex_scholar.auth.providers.OpenAthensAuthenticator import (
            OpenAthensAuthenticator,
        )

        assert hasattr(OpenAthensAuthenticator, "is_authenticate_async")
        assert hasattr(OpenAthensAuthenticator, "is_authenticated_async")
        # Both should be coroutine-compatible
        assert inspect.iscoroutinefunction(
            OpenAthensAuthenticator.is_authenticated_async
        )

    def test_shibboleth_has_both_spellings(self):
        from scitex_scholar.auth.providers.ShibbolethAuthenticator import (
            ShibbolethAuthenticator,
        )

        assert hasattr(ShibbolethAuthenticator, "is_authenticate_async")
        assert hasattr(ShibbolethAuthenticator, "is_authenticated_async")

    def test_ezproxy_has_both_spellings(self):
        from scitex_scholar.auth.providers.EZProxyAuthenticator import (
            EZProxyAuthenticator,
        )

        assert hasattr(EZProxyAuthenticator, "is_authenticate_async")
        assert hasattr(EZProxyAuthenticator, "is_authenticated_async")


# EOF
