#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the standalone GUI launcher's optional-dependency degrade path.

The launcher degrades to bare Django when scitex-app is absent. Two
properties matter, and both were broken by the shape inherited from
scitex-writer's launcher (reported by scitex-dev 2026-07-18):

  1. The guarded `try` must wrap ONLY the import. The old version also
     wrapped `django.setup()`, the migration, and the `run_standalone`
     CALL, so a genuine ImportError from deep inside the app was
     indistinguishable from "scitex-app is not installed".
  2. The degrade must be LOUD -- naming cause and remedy. The old
     `except ImportError: pass` left the user on a shell-less server with
     no indication anything had happened.

Property 1 is checked STRUCTURALLY (via `ast`), and that is deliberate:
it is the actual regression guard. Behaviourally, an over-broad `try`
still ends up raising -- the fallback path calls `django.setup()` a
second time and dies there -- so a "does it raise?" test would pass on
the buggy version too. What the old shape destroyed was the DISTINCTION
between the two causes, which lives in the code's shape, not its output.

Reality is substituted, never patched: the degrade is exercised by
running the launcher in a real subprocess against a real stub package on
`PYTHONPATH`.
"""

from __future__ import annotations

import ast
import inspect
import subprocess
import sys
import textwrap

import pytest

from scitex_scholar._django import _server


def _guarded_try_nodes():
    """Every `try` statement inside `run()`, as AST nodes."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(_server)))
    run = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "run"
    )
    return [n for n in ast.walk(run) if isinstance(n, ast.Try)]


@pytest.fixture
def degraded_run(tmp_path):
    """Run the launcher for real with scitex_app unimportable.

    A stub `scitex_app` package that raises on import stands in for an
    absent one, and a deliberately broken settings module halts the run
    right after the degrade notice -- before anything binds a port.
    """
    (tmp_path / "scitex_app").mkdir()
    (tmp_path / "scitex_app" / "__init__.py").write_text(
        "raise ImportError(\"No module named 'scitex_app'\")\n"
    )
    (tmp_path / "halt_settings.py").write_text("import a_module_that_does_not_exist\n")
    script = textwrap.dedent(
        """
        from scitex_scholar._django import _server
        _server.run(open_browser=False)
        """
    )
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
        env={
            "PATH": "/usr/bin:/bin",
            "PYTHONPATH": f"{tmp_path}:{':'.join(sys.path)}",
            "DJANGO_SETTINGS_MODULE": "halt_settings",
        },
    )


def test_run_guards_exactly_one_try_block():
    # Arrange
    tries = _guarded_try_nodes()
    # Act
    count = len(tries)
    # Assert
    assert count == 1


def test_guarded_try_body_is_only_an_import():
    """Widening this `try` re-merges 'dep absent' with 'the app is broken'."""
    # Arrange
    (guarded,) = _guarded_try_nodes()
    # Act
    body_types = {type(stmt) for stmt in guarded.body}
    # Assert
    assert body_types == {ast.ImportFrom}


def test_degraded_path_names_the_cause(degraded_run):
    # Arrange
    # (the fixture ran the launcher with scitex_app unimportable)
    # Act
    out = degraded_run.stdout
    # Assert
    assert "scitex-app is not installed" in out


def test_degraded_path_names_the_remedy(degraded_run):
    """A degrade notice the user cannot act on is only half a fix."""
    # Arrange
    # (the fixture ran the launcher with scitex_app unimportable)
    # Act
    out = degraded_run.stdout
    # Assert
    assert "pip install 'scitex-scholar[server]'" in out


# EOF


# ---------------------------------------------------------------------------
# _hosts_to_allow: what a --host bind contributes to ALLOWED_HOSTS.
#
# The 0.0.0.0 case is the one that makes DEBUG=False a safe DEFAULT. Measured
# 2026-09-02 on the published 1.9.0 wheel: `--host 0.0.0.0` under
# DJANGO_DEBUG=false answered 400 to every real interface address, because
# "0.0.0.0" in ALLOWED_HOSTS never matches a Host header.
# ---------------------------------------------------------------------------
def test_hosts_to_allow_loopback_contributes_nothing():
    # Arrange
    from scitex_scholar._django._server import _hosts_to_allow

    # Act
    contributed = _hosts_to_allow("127.0.0.1")
    # Assert
    assert contributed == []


def test_hosts_to_allow_specific_address_contributes_itself():
    # Arrange
    from scitex_scholar._django._server import _hosts_to_allow

    # Act
    contributed = _hosts_to_allow("100.64.0.4")
    # Assert
    assert contributed == ["100.64.0.4"]


def test_hosts_to_allow_bind_all_contributes_this_machines_hostname():
    # Arrange
    import socket

    from scitex_scholar._django._server import _hosts_to_allow

    # Act
    contributed = _hosts_to_allow("0.0.0.0")
    # Assert
    assert socket.gethostname() in contributed


def test_hosts_to_allow_bind_all_never_contributes_the_literal_wildcard():
    """Control: bind-all must widen to THIS machine, never to everything."""
    # Arrange
    from scitex_scholar._django._server import _hosts_to_allow

    # Act
    contributed = _hosts_to_allow("0.0.0.0")
    # Assert
    assert "*" not in contributed and "0.0.0.0" not in contributed


# EOF


def test_hosts_to_allow_bind_all_contributes_a_real_interface_address():
    """The test that the first implementation could NOT fail.

    It used getaddrinfo(gethostname()), passed the hostname assertion above,
    and still answered 400 to the real LAN address in a live check. Derive the
    expected address by an INDEPENDENT method -- the UDP-connect trick reads
    the kernel's chosen source address without sending a packet -- so the
    assertion is not the implementation checking itself.
    """
    # Arrange
    import socket

    from scitex_scholar._django._server import _hosts_to_allow

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("10.255.255.255", 1))  # no packet is sent for UDP connect
        expected = s.getsockname()[0]
    # Act
    contributed = _hosts_to_allow("0.0.0.0")
    # Assert
    assert expected in contributed, f"{expected!r} not in {contributed!r}"


# EOF
