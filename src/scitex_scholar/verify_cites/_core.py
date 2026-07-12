#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: src/scitex_scholar/verify_cites/_core.py
# ----------------------------------------
"""Orchestrate verify-cites: cited-set -> resolve -> classify -> sidecar."""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ._classify import classify
from ._model import (
    EXIT_CITATION_STUB,
    EXIT_CITATION_UNLINKED,
    EXIT_CITATION_UNRESOLVED,
    EXIT_NO_CITES,
    EXIT_OK,
    HALLUCINATED,
    STUB,
    UNLINKED,
    UNVERIFIED,
    CiteStatus,
)
from ._resolve import ResolverFn, default_resolver
from ._tex import extract_cited_keys, resolve_compiled_bib

DEFAULT_SIDECAR = Path(".scitex/scholar/citation_status.json")

# Scholar->clew decoupled seam (operator's acyclic-deps decision, 2026-07-02):
# scholar stays clew-agnostic and never imports scitex_clew. It saves this
# artifact via ``stx.io.save``; clew's io-save observer recognizes it by the
# "schema" marker and ingests it on its own. See scitex_clew._citation._ingest
# for the authoritative contract this shape must match.
CLEW_CITATIONS_SCHEMA = "scitex-clew/citations/v1"
DEFAULT_CLEW_SIDECAR = Path(".scitex/scholar/citations_clew.json")


@dataclasses.dataclass
class VerifyReport:
    bib_path: Optional[str]
    statuses: List[CiteStatus]

    def by_status(self, status: str) -> List[str]:
        return [s.key for s in self.statuses if s.status == status]

    def summary(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for s in self.statuses:
            out[s.status] = out.get(s.status, 0) + 1
        return out

    def to_sidecar(self) -> dict:
        return {s.key: s.to_dict() for s in self.statuses}


def _load_entries(bib_path: Path) -> Dict[str, dict]:
    from .._utils.bibtex._parse_bibtex import parse_bibtex

    entries = parse_bibtex(bib_path) or []
    return {e["ID"]: e for e in entries if e.get("ID")}


def verify_cites(
    manuscript_dir,
    *,
    bib: Optional[Path] = None,
    out: Optional[Path] = None,
    min_confidence: float = 0.8,
    offline: bool = False,
    resolver: Optional[ResolverFn] = None,
    cited_keys: Optional[Iterable[str]] = None,
    entries: Optional[Dict[str, dict]] = None,
    write: bool = True,
) -> VerifyReport:
    """Verify every CITED key against a real source and emit a sidecar.

    ``entries`` / ``cited_keys`` / ``resolver`` are injectable for testing
    without touching the filesystem or the network.
    """
    root = Path(manuscript_dir)
    bib_path = Path(bib) if bib else resolve_compiled_bib(root)

    if entries is None:
        if bib_path is None or not Path(bib_path).exists():
            raise FileNotFoundError(
                "Could not resolve the compiled .bib; pass --bib explicitly."
            )
        entries = _load_entries(Path(bib_path))

    if cited_keys is None:
        cited_keys = extract_cited_keys(root)
    cited = sorted(set(cited_keys))

    if resolver is None:
        resolver = lambda e: default_resolver(e, offline=offline)

    statuses: List[CiteStatus] = []
    for key in cited:
        entry = entries.get(key)
        if entry is None:
            # Cited but absent from the bib bibtex reads => undefined citation.
            statuses.append(
                CiteStatus(
                    key=key,
                    status=UNLINKED,
                    provenance="cited but not present in the compiled bib (undefined citation)",
                )
            )
            continue
        from ._classify import is_stub_entry

        resolved = None if is_stub_entry(entry) else resolver(entry)
        statuses.append(
            classify(key, entry, resolved, min_confidence=min_confidence)
        )

    report = VerifyReport(
        bib_path=(str(bib_path) if bib_path else None), statuses=statuses
    )

    if write:
        out_path = Path(out) if out else (root / DEFAULT_SIDECAR)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report.to_sidecar(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return report


def compute_exit_code(report: VerifyReport, fail_on: Iterable[str]) -> int:
    """Fail-loud exit code in clew's CITATION namespace.

    Precedence stub/hallucinated (14) > unresolved (15) > unlinked (16).
    """
    if not report.statuses:
        return EXIT_NO_CITES
    fail_on = set(fail_on)
    if fail_on & {STUB, HALLUCINATED} and (
        report.by_status(STUB) or report.by_status(HALLUCINATED)
    ):
        return EXIT_CITATION_STUB
    if UNVERIFIED in fail_on and report.by_status(UNVERIFIED):
        return EXIT_CITATION_UNRESOLVED
    if UNLINKED in fail_on and report.by_status(UNLINKED):
        return EXIT_CITATION_UNLINKED
    return EXIT_OK


def build_citations_artifact(report: VerifyReport) -> dict:
    """Build the scholar->clew decoupled sidecar artifact (schema v1).

    Each entry is exactly ``CiteStatus.to_clew()`` -- already shaped to match
    clew's ingest contract per-entry; this just wraps them under the required
    schema marker.
    """
    return {
        "schema": CLEW_CITATIONS_SCHEMA,
        "citations": [st.to_clew() for st in report.statuses],
    }


def push_to_clew(report: VerifyReport, out: Optional[Path] = None) -> int:
    """Save the citation ledger as a clew-ingestible sidecar artifact.

    Writes via ``stx.io.save`` (scholar never imports scitex_clew directly --
    the acyclic-deps seam). Returns the number of citation entries written;
    0 if the report has no statuses.
    """
    artifact = build_citations_artifact(report)
    if not artifact["citations"]:
        return 0
    import scitex_io

    out_path = Path(out) if out else DEFAULT_CLEW_SIDECAR
    scitex_io.save(artifact, str(out_path), verbose=False)
    return len(artifact["citations"])


# EOF
