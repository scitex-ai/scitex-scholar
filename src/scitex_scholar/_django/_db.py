#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CrossRef DB path resolution -- ported verbatim from the Flask-era
`scitex_scholar.gui._app._find_crossref_db`.

Resolution order: explicit arg, then `CROSSREF_DB_PATH` env var, then a
few candidate filesystem paths, then an optional `crossref_local` module
probe.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import scitex_logging as _slog

_logger = _slog.getLogger(__name__)


def find_crossref_db(db_path: Optional[str] = None) -> Optional[str]:
    """Auto-detect CrossRef database path."""
    if db_path and Path(db_path).exists():
        return db_path

    # Check environment variable (Docker / explicit config)
    env_path = os.environ.get("CROSSREF_DB_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    # Candidates: first the config-resolved location (honours SCITEX_DIR),
    # then common dev-local checkout paths as fallback.
    from scitex_scholar.config import ScholarConfig

    candidates = [
        ScholarConfig().path_manager.scholar_dir / "crossref.db",
        Path.home() / "proj" / "crossref_local" / "data" / "crossref.db",
        Path.home() / "proj" / "crossref-local" / "data" / "crossref.db",
        Path.home() / ".proj" / "crossref_local" / "data" / "crossref.db",
    ]
    for p in candidates:
        if p.exists():
            return str(p)

    # Try crossref_local module info as last resort
    try:
        import crossref_local

        info = crossref_local.info()
        p = info.get("db_path")
        if p and Path(p).exists():
            return str(p)
    except Exception as exc:
        _logger.debug(
            f"crossref_local.info() probe failed ({type(exc).__name__}: {exc})"
        )

    return None


# EOF
