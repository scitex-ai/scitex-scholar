"""Lazy HTTP adapter over the existing Scholar syntax-help implementation."""

from __future__ import annotations


def search_syntax_help(request):
    """Preserve the native GET response and Django's unchanged method refusal."""
    from scitex_scholar._django.views import search_syntax_help as delegate

    return delegate(request)
