#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the standalone GUI launcher's wiring.

The launcher used to degrade to bare Django when scitex-app was absent, and
this file guarded the SHAPE of that degrade (an `ast` check that the `try`
wrapped only the import). That path was retired 2026-09-03. The optional
`[all]` GUI stack now exposes the shared `hosts_to_allow` helper through the
public `scitex_sdk.app` namespace used by the launcher.

What remains: scholar must bind the public SDK helper, and must not carry a
private copy that could drift from it.
"""

from __future__ import annotations



from scitex_scholar._django import _server


# ---------------------------------------------------------------------------
# Scholar wrote the first hosts_to_allow implementation (#137); it was copied
# into scitex-app and became the fleet's shared helper. The behaviour tests
# went with it. The launcher now consumes the public scitex_sdk.app facade, so
# this WIRING assertion compares against that same public export. Scholar must
# not carry a second implementation that could drift from it.
# ---------------------------------------------------------------------------
def test_server_binds_public_sdk_hosts_helper():
    # Arrange
    from scitex_sdk import app as sdk_app

    from scitex_scholar._django import _server

    # Act
    bound = _server.hosts_to_allow
    # Assert
    assert bound is sdk_app.hosts_to_allow


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
