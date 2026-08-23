#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guard the SHAPE of the urlconf, because a consumer authenticates it.

WHY THIS FILE EXISTS
--------------------
scitex-hub mounts `scitex_scholar._django.urls` behind its login by walking our
`urlpatterns` and wrapping every `URLPattern.callback` in `login_required`
(scitex-hub PR #687, `scholar_app/urls/scholar_django.py`).

That technique gates a FLAT list and cannot gate a nested one: decorating a
`URLResolver` wraps the resolver, NOT the views inside it, so any route we nest
behind an `include()` would be published UNAUTHENTICATED under hub. Our views
carry no decorator of their own, so nothing else would stop it.

hub already refuses to mount that shape -- they raise `ImproperlyGatedURLConf`
rather than publish it. This test exists because their check fires in THEIR
deployment, at import time, after our change has already shipped. Ours fires in
OUR pull request, which is the cheap place to find it. Same defect, caught one
hop earlier.

So: if you are adding an `include()` below and this test fails, the test is
doing its job. Do not delete it. Tell hub first so they can gate the inner set
explicitly, then change this test deliberately.
"""

from __future__ import annotations

from django.urls import URLPattern, URLResolver

from scitex_scholar._django import urls as scholar_urls


def test_urlpatterns_are_all_flat_urlpattern_entries():
    # Arrange
    patterns = scholar_urls.urlpatterns
    # Act
    non_flat = [p for p in patterns if not isinstance(p, URLPattern)]
    # Assert
    assert non_flat == [], (
        "scitex-hub gates this urlconf by decorating each URLPattern.callback; "
        f"these entries cannot be gated that way: {non_flat!r}"
    )


def test_urlpatterns_contain_no_nested_resolver():
    # Arrange
    patterns = scholar_urls.urlpatterns
    # Act
    resolvers = [p for p in patterns if isinstance(p, URLResolver)]
    # Assert
    assert resolvers == [], (
        "an include() here would publish the routes inside it unauthenticated "
        "under hub's mount -- see this module's docstring before changing"
    )


def test_every_pattern_exposes_a_callback_to_decorate():
    # Arrange
    patterns = scholar_urls.urlpatterns
    # Act
    missing = [p for p in patterns if getattr(p, "callback", None) is None]
    # Assert
    assert missing == [], f"entries with no callback to wrap: {missing!r}"


def test_control_django_include_would_fail_the_flatness_check():
    """Positive control: prove the checks above CAN fail.

    Without this, all three tests pass trivially if `urlpatterns` were ever
    empty, or if `URLResolver` stopped being what `include()` produces. This
    builds the exact shape the guard is meant to reject and asserts the
    predicate rejects it -- so a green run means the instrument works, not just
    that today's list happens to be clean.
    """
    # Arrange
    from django.urls import include, path

    nested = [path("nested/", include((scholar_urls.urlpatterns, "scholar")))]
    # Act
    resolvers = [p for p in nested if isinstance(p, URLResolver)]
    # Assert
    assert resolvers, "include() no longer yields a URLResolver; the guard above is dead"


# EOF
