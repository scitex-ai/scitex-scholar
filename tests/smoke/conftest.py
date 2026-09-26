"""Isolation for the smoke layer (PS-211).

Every smoke test drives the real CLI in a subprocess. The CLI must never
see the operator's real `~/.scitex` tree, so `SCITEX_DIR` points at a fresh
tmp dir for the whole layer. No key blanking is needed: the happy-path
commands (`--help`, `--version`) never touch the network or credentials.

No `monkeypatch` (PA-306): explicit save/restore.
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
        # Restore exactly (a deleted var stays deleted; dotenv must not
        # repopulate it from the real shell behind our back — we never
        # delete, we only overwrite, and we put the old value back).
        if previous is None:
            os.environ.pop("SCITEX_DIR", None)
        else:
            os.environ["SCITEX_DIR"] = previous


# EOF
