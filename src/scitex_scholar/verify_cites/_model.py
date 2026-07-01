#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: src/scitex_scholar/verify_cites/_model.py
# ----------------------------------------
"""Data model + status/exit-code constants for `verify-cites`.

Exit codes and the clew push payload are aligned to clew's frozen contract
(confirmed 2026-07-01): citation codes are DISTINCT from clew's value-claim
codes (which own 10/11/12), and `clew.add_citation` DERIVES status from
`resolved`/`is_stub`/`doi` — there is no `status=` kwarg.
"""
from __future__ import annotations

import dataclasses
from typing import Optional

# Local (verify-time) statuses — richer than what clew stores. "unknown" and
# "unlinked" are verify-time verdicts, not directly registerable in clew.
VERIFIED = "verified"
UNVERIFIED = "unverified"
STUB = "stub"
HALLUCINATED = "hallucinated"
UNLINKED = "unlinked"  # cited but no entry in the compiled bib (undefined cite)

LOCAL_STATUSES = (VERIFIED, UNVERIFIED, STUB, HALLUCINATED, UNLINKED)

# Exit codes mirror clew's CITATION namespace (distinct from clew's value-claim
# codes UNVERIFIED=10 / SOURCE_MISSING=11 / HASH_MISMATCH=12).
EXIT_OK = 0
EXIT_CITATION_STUB = 14        # stub or hallucinated (placeholder / fabricated)
EXIT_CITATION_UNRESOLVED = 15  # has an identifier but did not resolve
EXIT_CITATION_UNLINKED = 16    # cited but absent from the compiled bib
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
        """kwargs for ``clew.add_citation`` (clew derives its own status).

        Mapping (per clew's frozen API):
          verified   -> resolved=True,  is_stub=False, doi set
          unverified -> resolved=False, is_stub=False
          stub/hallucinated -> is_stub=True
          unlinked   -> resolved=False, is_stub=False (no entry to link)
        The richer local status + provenance travel in ``metadata``.
        """
        is_stub = self.status in (STUB, HALLUCINATED)
        return {
            "cite_key": self.key,
            "doi": self.doi,
            "url": None,
            "source_id": self.scholar_id,
            "is_stub": is_stub,
            "resolved": self.status == VERIFIED,
            "metadata": {
                "local_status": self.status,
                "resolver_source": self.resolver_source,
                "match_confidence": self.match_confidence,
                "provenance": self.provenance,
            },
        }


# EOF
