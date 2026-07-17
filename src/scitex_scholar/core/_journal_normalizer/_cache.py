#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Journal normalizer cache file I/O and freshness.

Freshness is advisory, not a gate. A stale cache is still good data --
journal names and ISSN-Ls change on the scale of years -- so callers read
what is on disk and refresh out of band. See this package's README for why
that matters.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import scitex_logging as logging

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 86400  # 1 day
CACHE_FILENAME = "journal_normalizer_cache.json"


def default_cache_dir() -> Path:
    """Get default cache directory via PathManager (runtime/cache)."""
    from scitex_scholar.config import ScholarConfig

    return ScholarConfig().path_manager.cache_dir


def cache_file(cache_dir: Path) -> Path:
    """Resolve the cache file inside a cache directory."""
    return cache_dir / CACHE_FILENAME


def load_cache(path: Path) -> Optional[Dict[str, Any]]:
    """Read the cache file, or None if absent/unreadable/corrupt."""
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load journal normalizer cache: {e}")
        return None


def save_cache(path: Path, payload: Dict[str, Any]) -> None:
    """Write the cache file, stamping it with the current time."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {**payload, "timestamp": time.time()}
        with open(path, "w") as f:
            json.dump(payload, f)
        logger.info(f"Saved {payload.get('journal_count', 0)} journals to cache")
    except OSError as e:
        logger.warning(f"Failed to save journal normalizer cache: {e}")


def is_fresh(timestamp: float) -> bool:
    """Whether a cache timestamp is within the TTL.

    Advisory only: staleness means "a refresh is due", never "unusable".
    """
    return (time.time() - timestamp) < CACHE_TTL_SECONDS


# EOF
