"""Isolation for the e2e layer (PS-212).

Same contract as the smoke layer: the real CLI runs in a subprocess
against a real (temporary) library, and it must never see the operator's
real `~/.scitex` tree. No `monkeypatch` (PA-306): explicit save/restore.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _isolated_scitex_dir(tmp_path):
    # Arrange — save the operator's environment.
    previous = os.environ.get("SCITEX_DIR")
    os.environ["SCITEX_DIR"] = str(tmp_path / ".scitex")
    try:
        yield
    finally:
        # Restore exactly.
        if previous is None:
            os.environ.pop("SCITEX_DIR", None)
        else:
            os.environ["SCITEX_DIR"] = previous


# EOF
