"""Subprocess-driven CLI happy-path (PS-211 smoke layer).

Fast (<60s total): `--help` / `--version` prove the installed entry point
imports the checkout's package and parses, without touching the network.
One assert per test (PA-307).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.smoke

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = str(_PROJECT_ROOT / "src")


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the checkout's CLI in a subprocess with an explicit env."""
    env = dict(os.environ, PYTHONPATH=_SRC + os.pathsep + os.environ.get("PYTHONPATH", ""))
    return subprocess.run(
        [sys.executable, "-m", "scitex_scholar", *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def test_help_exits_zero_result_returncode_equals_n_0():
    # Arrange
    args = ["--help"]
    # Act
    proc = _run_cli(*args)
    # Assert
    assert proc.returncode == 0


def test_version_reports_semver_result_stdout_matches_version_d_d_d():
    # Arrange
    args = ["--version"]
    # Act
    proc = _run_cli(*args)
    # Assert
    assert re.search(r"version \d+\.\d+\.\d+", proc.stdout)


def test_library_help_exits_zero_result_returncode_equals_n_0():
    # Arrange
    args = ["library", "--help"]
    # Act
    proc = _run_cli(*args)
    # Assert
    assert proc.returncode == 0


# EOF
