#!/usr/bin/env python3
# File: src/scitex_scholar/_cli/_library_shared.py

"""Helpers shared by the ``library`` command group and its split-out modules.

Lives in its own module so ``library.py`` and ``_library_db.py`` can both use
``_default_library_root()`` without importing each other. See
``GITIGNORED/REFACTORING.md`` for the full split plan.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["default_library_root"]


def default_library_root() -> Path:
    """The home library every ``library`` subcommand falls back to."""
    return Path("~/.scitex/scholar/library").expanduser().resolve()


# EOF
