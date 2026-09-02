#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DEBUG defaults to False, and the standalone launcher still serves /static/.

These two facts are ONE change and must be tested together: flipping the
default without the static route breaks the GUI silently (page 200, every
asset 404 -- measured 2026-09-02 on the 1.9.0 wheel), and adding the route
without flipping the default leaves ALLOWED_HOSTS="*" as the default branch
on an app with no authentication.

The env-var tests reload the REAL settings module against the REAL process
environment; the fixture below sets and restores `os.environ` itself rather
than rewriting production internals.
"""

from __future__ import annotations

import importlib
import os

import pytest

from django.test import Client, override_settings

_ENV_KEY = "DJANGO_DEBUG"


@pytest.fixture
def django_debug_env():
    """Yield a setter for DJANGO_DEBUG; restore the original value on teardown."""
    original = os.environ.get(_ENV_KEY)

    def _set(value):
        if value is None:
            os.environ.pop(_ENV_KEY, None)
        else:
            os.environ[_ENV_KEY] = value
        import scitex_scholar._django.settings as s

        return importlib.reload(s)

    yield _set
    if original is None:
        os.environ.pop(_ENV_KEY, None)
    else:
        os.environ[_ENV_KEY] = original
    import scitex_scholar._django.settings as s

    importlib.reload(s)


def test_debug_defaults_to_false_when_env_unset(django_debug_env):
    # Arrange
    set_env = django_debug_env
    # Act
    s = set_env(None)
    # Assert
    assert s.DEBUG is False


def test_debug_default_puts_loopback_not_wildcard_in_allowed_hosts(django_debug_env):
    # Arrange
    set_env = django_debug_env
    # Act
    s = set_env(None)
    # Assert
    assert "*" not in s.ALLOWED_HOSTS and "127.0.0.1" in s.ALLOWED_HOSTS


def test_debug_true_is_still_an_explicit_opt_in(django_debug_env):
    """Control: the env var still works, so the flip did not remove the switch."""
    # Arrange
    set_env = django_debug_env
    # Act
    s = set_env("true")
    # Assert
    assert s.DEBUG is True and s.ALLOWED_HOSTS == ["*"]


@override_settings(DEBUG=False, ROOT_URLCONF="scitex_scholar._django._standalone_urls")
def test_standalone_urlconf_serves_static_with_debug_false():
    # Arrange
    client = Client()
    # Act
    resp = client.get("/static/scholar/css/scholar.css")
    # Assert
    assert resp.status_code == 200


@override_settings(DEBUG=False, ROOT_URLCONF="scitex_scholar._django._standalone_urls")
def test_standalone_urlconf_serves_shell_static_with_debug_false():
    """The shell's assets come from a DIFFERENT package (scitex_ui) via finders."""
    # Arrange
    client = Client()
    # Act
    resp = client.get("/static/scitex_ui/img/scitex-favicon.svg")
    # Assert
    assert resp.status_code == 200


@override_settings(DEBUG=False, ROOT_URLCONF="scitex_scholar._django._standalone_urls")
def test_standalone_static_route_still_404s_for_a_missing_asset():
    """Negative control: the route resolves through finders, not a catch-all."""
    # Arrange
    client = Client()
    # Act
    resp = client.get("/static/scholar/css/does-not-exist.css")
    # Assert
    assert resp.status_code == 404


@override_settings(DEBUG=False, ROOT_URLCONF="scitex_scholar._django.urls")
def test_mounted_urlconf_does_not_grow_a_static_route():
    """hub mounts urls.py, not the standalone file; it must stay static-free."""
    # Arrange
    client = Client()
    # Act
    resp = client.get("/static/scholar/css/scholar.css")
    # Assert
    assert resp.status_code == 404


# EOF
