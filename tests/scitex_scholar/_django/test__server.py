#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the standalone GUI launcher's wiring.

The launcher used to degrade to bare Django when scitex-app was absent, and
this file guarded the SHAPE of that degrade (an `ast` check that the `try`
wrapped only the import). That path was retired 2026-09-03: scitex-app is a
hard member of the `[server]` extra, `hosts_to_allow` now lives there with a
public name, and a fallback that silently dropped both the shell and the
ALLOWED_HOSTS derivation was a quieter way to break, not a kindness.

What remains: scholar must bind scitex-app's PUBLIC helper, and must not carry
a private copy that could drift from it.
"""

from __future__ import annotations



from scitex_scholar._django import _server


# ---------------------------------------------------------------------------
# hosts_to_allow is scitex-app's now (public name since 0.11.0). Scholar wrote
# the first implementation (#137); it was copied into scitex-app verbatim and
# became the fleet's single one. The behaviour tests went with it. What stays
# here is the WIRING: scholar must use the public name, and must not carry a
# second implementation that could drift from it.
# ---------------------------------------------------------------------------
def test_server_binds_scitex_apps_public_hosts_helper():
    # Arrange
    import scitex_app

    from scitex_scholar._django import _server

    # Act
    bound = _server.hosts_to_allow
    # Assert
    assert bound is scitex_app.hosts_to_allow


def test_server_carries_no_private_hosts_helper_copy():
    """The retirement card closes when the private helper name is gone from this repo,
    so this test must not itself contain that name as a substring."""
    # Arrange
    from pathlib import Path

    src = Path(__file__).resolve().parents[3] / "src" / "scitex_scholar" / "_django" / "_server.py"
    # Act
    text = src.read_text()
    # Assert
    assert "def _hosts" not in text and "def _interface_ipv4" not in text


# EOF
