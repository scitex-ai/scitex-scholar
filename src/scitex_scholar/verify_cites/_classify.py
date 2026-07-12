#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: src/scitex_scholar/verify_cites/_classify.py
# ----------------------------------------
"""Stub detection, title similarity, and status classification."""
from __future__ import annotations

import datetime as _dt
import difflib
import re
from typing import Optional

from ._model import (
    HALLUCINATED,
    STUB,
    UNVERIFIED,
    VERIFIED,
    CiteStatus,
)
from ._resolve import ResolvedRef

# Markers auto-writers leave on placeholder entries.
_STUB_JOURNAL = "pending scitex-scholar"
_STUB_NOTE = "auto-generated stub"
_STUB_TITLE = "[stub]"


def normalize_title(title: Optional[str]) -> str:
    if not title:
        return ""
    # Strip simple LaTeX braces/commands, punctuation, and collapse whitespace.
    t = re.sub(r"\\[a-zA-Z]+", " ", title)
    t = t.replace("{", "").replace("}", "")
    t = re.sub(r"[^\w\s]", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def title_similarity(a: Optional[str], b: Optional[str]) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    return round(difflib.SequenceMatcher(None, na, nb).ratio(), 3)


def is_stub_entry(entry: dict) -> bool:
    """True if the bib entry is an auto-generated placeholder."""
    journal = (entry.get("journal") or "").lower()
    note = (entry.get("note") or "").lower()
    title = (entry.get("title") or "").lower()
    has_source = bool(
        (entry.get("doi") or "").strip()
        or (entry.get("url") or "").strip()
        or (entry.get("eprint") or "").strip()
    )
    if _STUB_JOURNAL in journal or _STUB_NOTE in note or title.startswith(_STUB_TITLE):
        return True
    # No title AND no resolvable identifier => nothing to verify against.
    if not (entry.get("title") or "").strip() and not has_source:
        return True
    return False


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def classify(
    key: str,
    entry: dict,
    resolved: Optional[ResolvedRef],
    *,
    min_confidence: float = 0.8,
) -> CiteStatus:
    """Assign a verification status to one cite key.

    - stub          : placeholder entry (no real metadata to check)
    - verified      : resolver hit AND title matches >= min_confidence
    - unverified    : has an identifier but resolver missed / weak title match
    - hallucinated  : searched by title+author+year, nothing plausible found
    """
    bib_title = entry.get("title")
    if is_stub_entry(entry):
        return CiteStatus(
            key=key,
            status=STUB,
            doi=(entry.get("doi") or None),
            title_bib=bib_title,
            provenance="placeholder entry (pending/auto-generated stub)",
        )

    if resolved is not None:
        sim = title_similarity(bib_title, resolved.title)
        status = VERIFIED if sim >= min_confidence else UNVERIFIED
        return CiteStatus(
            key=key,
            status=status,
            doi=(resolved.doi or entry.get("doi") or None),
            resolver_source=resolved.source,
            match_confidence=sim,
            title_bib=bib_title,
            title_resolver=resolved.title,
            resolved_at=_now(),
            provenance=(
                f"{resolved.source} match (title_sim={sim})"
                if status == VERIFIED
                else f"{resolved.source} hit but weak title match (sim={sim} < {min_confidence})"
            ),
        )

    # Not resolved. If the entry carried an identifier, it's unverified
    # (identifier didn't resolve — could be transient / arXiv-not-in-crossref).
    # If it had ONLY title+author+year and nothing matched anywhere, it is a
    # candidate fabrication.
    has_id = bool(
        (entry.get("doi") or "").strip()
        or (entry.get("url") or "").strip()
        or (entry.get("eprint") or "").strip()
    )
    if has_id:
        return CiteStatus(
            key=key,
            status=UNVERIFIED,
            doi=(entry.get("doi") or None),
            title_bib=bib_title,
            resolved_at=_now(),
            provenance="identifier present but did not resolve (retry / alt resolver)",
        )
    return CiteStatus(
        key=key,
        status=HALLUCINATED,
        title_bib=bib_title,
        resolved_at=_now(),
        provenance="no identifier and no resolver match by title/author/year",
    )


# EOF
