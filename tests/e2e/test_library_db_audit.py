"""End-to-end `library db audit` against a real temp library (PS-212 layer).

Offline (loopback only, no network): builds a real `<root>/MASTER` tree on
a tmp dir and drives the real CLI in a subprocess through the live auditor
codepath. Gated by `RUN_E2E=1`, skipped by default. One assert per test
(PA-307).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        os.environ.get("RUN_E2E") != "1",
        reason="e2e runs only with RUN_E2E=1",
    ),
]

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = str(_PROJECT_ROOT / "src")


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the checkout's CLI in a subprocess with an explicit env."""
    env = dict(os.environ, PYTHONPATH=_SRC + os.pathsep + os.environ.get("PYTHONPATH", ""))
    return subprocess.run(
        [sys.executable, "-m", "scitex_scholar", *args],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )


def test_db_audit_clean_library_exits_zero_result_returncode_equals_n_0(tmp_path):
    # Arrange — a real library_root with an empty primary-store subdir.
    (tmp_path / "MASTER").mkdir()
    args = ["library", "db", "audit", "--library-root", str(tmp_path), "--json"]
    # Act
    proc = _run_cli(*args)
    # Assert
    assert proc.returncode == 0


def test_db_audit_clean_library_reports_no_issues_result_has_issues_is_false(tmp_path):
    # Arrange — a real library_root with an empty primary-store subdir.
    (tmp_path / "MASTER").mkdir()
    args = ["library", "db", "audit", "--library-root", str(tmp_path), "--json"]
    # Act
    proc = _run_cli(*args)
    # Assert
    assert json.loads(proc.stdout)["has_issues"] is False


# EOF
