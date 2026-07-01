#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: src/scitex_scholar/verify_cites/_model.py
# ----------------------------------------
"""Data model + status/exit-code constants for `verify-cites`."""
from __future__ import annotations

import dataclasses
from typing import Optional

# Local verification statuses (richer than the clew-locked set).
VERIFIED = "verified"
UNVERIFIED = "unverified"
STUB = "stub"
HALLUCINATED = "hallucinated"

LOCAL_STATUSES = (VERIFIED, UNVERIFIED, STUB, HALLUCINATED)

# clew locked its status set to {verified, stub, unverified, unknown}.
# Map the richer local set onto it at the boundary; keep the nuance in the
# sidecar. A hallucinated ref maps to stub (+is_stub) so the writer gate fires.
_CLEW_MAP = {
    VERIFIED: "verified",
    UNVERIFIED: "unverified",
    STUB: "stub",
    HALLUCINATED: "stub",
}

# Exit codes mirror `clew verify`'s fail-loud contract.
EXIT_OK = 0
EXIT_HALLUCINATED = 10
EXIT_UNVERIFIED = 11
EXIT_STUB = 12
EXIT_NO_CITES = 20


@dataclasses.dataclass
class CiteStatus:
    """Verification record for a single cite key."""

    key: str
    status: str
    doi: Optional[str] = None
    resolver_source: Optional[str] = None
    match_confidence: Optional[float] = None
    title_bib: Optional[str] = None
    title_resolver: Optional[str] = None
    resolved_at: Optional[str] = None
    scholar_id: Optional[str] = None
    provenance: str = ""

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def to_clew(self) -> dict:
        """Boundary payload for `clew.add_citation`."""
        return {
            "key": self.key,
            "status": _CLEW_MAP[self.status],
            "doi": self.doi,
            "is_stub": self.status in (STUB, HALLUCINATED),
        }


# EOF
