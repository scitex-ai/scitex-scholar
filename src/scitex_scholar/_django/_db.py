#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Where the GUI reaches the CrossRef corpus.

Scholar does not open crossref-local's data files. It asks crossref-local's
HTTP API, which is the package that owns that corpus. This module resolves
the endpoint ONCE (settings-load time) so `views.py` reads a plain setting
instead of re-probing on every request.

Resolution order: explicit arg, then `SCITEX_SCHOLAR_CROSSREF_LOCAL_API_URL`
(legacy `CROSSREF_LOCAL_API_URL`), then crossref-local's own default
endpoint. Returns None when crossref-local is not installed and no endpoint
was configured -- the GUI then reports the citation-graph routes as
unavailable rather than failing a request at a time.
"""

from __future__ import annotations

from typing import Optional

import scitex_logging as _slog

from .._utils._env import resolve_env

_logger = _slog.getLogger(__name__)


def find_crossref_api_url(api_url: Optional[str] = None) -> Optional[str]:
    """Resolve the crossref-local HTTP endpoint the GUI should query."""
    if api_url:
        return api_url

    env_url = resolve_env(
        "SCITEX_SCHOLAR_CROSSREF_LOCAL_API_URL", legacy="CROSSREF_LOCAL_API_URL"
    )
    if env_url:
        return env_url

    try:
        from crossref_local._core.config import DEFAULT_API_URL

        return DEFAULT_API_URL
    except Exception as exc:
        _logger.debug(
            f"crossref_local default endpoint unavailable "
            f"({type(exc).__name__}: {exc})"
        )

    return None


# EOF
