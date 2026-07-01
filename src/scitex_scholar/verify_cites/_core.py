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
    EXIT_HALLUCINATED,
    EXIT_NO_CITES,
    EXIT_OK,
    EXIT_STUB,
    EXIT_UNVERIFIED,
    HALLUCINATED,
    STUB,
    UNVERIFIED,
    CiteStatus,
)
from ._resolve import ResolverFn, default_resolver
from ._tex import extract_cited_keys, resolve_compiled_bib

DEFAULT_SIDECAR = Path(".scitex/scholar/citation_status.json")


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
                    status=HALLUCINATED,
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
    """Fail-loud exit code, precedence hallucinated > unverified > stub."""
    if not report.statuses:
        return EXIT_NO_CITES
    fail_on = set(fail_on)
    if HALLUCINATED in fail_on and report.by_status(HALLUCINATED):
        return EXIT_HALLUCINATED
    if UNVERIFIED in fail_on and report.by_status(UNVERIFIED):
        return EXIT_UNVERIFIED
    if STUB in fail_on and report.by_status(STUB):
        return EXIT_STUB
    return EXIT_OK


# EOF
