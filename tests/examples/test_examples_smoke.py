"""Smoke tests: every example script must run to completion.

Split from a single multi-assert function into:

- ``test_examples_directory_has_at_least_one_script`` — the
  collection-time invariant (TQ001 + TQ007 both clear),
- a parametrized ``test_example_script_runs_to_completion`` — one row
  per example, one assertion per row, so a failure points at the exact
  script that broke (was previously buried mid-loop with the rest
  silently skipped).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


# Repo `examples/` directory (top-level), NOT the test-package mirror
# `tests/examples/` directory the test file itself lives in. The previous
# `parent.parent.joinpath("examples")` resolved to `tests/examples/`,
# which inadvertently re-ran `tests/examples/test_quickstart.py` as a
# script and tripped its broken `if __name__ == "__main__":` shim
# (the auto-fix renamed `test_quickstart_compiles` but left the bottom
# of the file pointing at the old name).
_REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = sorted((_REPO_ROOT / "examples").glob("*.py"))


def test_examples_directory_has_at_least_one_script():
    # Arrange
    # Act
    count = len(EXAMPLES)
    # Assert
    assert count > 0, "no example scripts found under tests/../examples/"


@pytest.mark.parametrize("example", EXAMPLES, ids=[p.name for p in EXAMPLES])
def test_example_script_runs_to_completion_with_zero_exit(example, tmp_path):
    # Arrange
    cmd = [sys.executable, str(example)]
    # Act
    r = subprocess.run(
        cmd,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    # Assert
    assert r.returncode == 0, f"{example.name} failed: {r.stderr}"
