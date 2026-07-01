#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: src/scitex_scholar/verify_cites/__init__.py
# ----------------------------------------
"""Resolve every cited key to a real source; classify + gate on it.

Public API:
    verify_cites(manuscript_dir, ...) -> VerifyReport
    compute_exit_code(report, fail_on) -> int
"""
from ._classify import classify, is_stub_entry, title_similarity
from ._core import (
    DEFAULT_SIDECAR,
    VerifyReport,
    compute_exit_code,
    verify_cites,
)
from ._model import (
    HALLUCINATED,
    STUB,
    UNVERIFIED,
    VERIFIED,
    CiteStatus,
)
from ._resolve import ResolvedRef, default_resolver
from ._tex import extract_cited_keys, resolve_compiled_bib

__all__ = [
    "verify_cites",
    "compute_exit_code",
    "VerifyReport",
    "CiteStatus",
    "ResolvedRef",
    "default_resolver",
    "classify",
    "is_stub_entry",
    "title_similarity",
    "extract_cited_keys",
    "resolve_compiled_bib",
    "DEFAULT_SIDECAR",
    "VERIFIED",
    "UNVERIFIED",
    "STUB",
    "HALLUCINATED",
]

# EOF
