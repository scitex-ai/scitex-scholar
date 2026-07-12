#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: src/scitex_scholar/verify_cites/_resolve.py
# ----------------------------------------
"""Resolve a bib entry to a real source across metadata engines.

The resolver is a plain callable ``(entry: dict) -> Optional[ResolvedRef]`` so
callers (and tests) can inject a fake. The default routes by identifier:

  * ``10.48550/arxiv.*`` / eprint   -> ArXiv  (CrossRef 404s on arXiv DOIs)
  * other DOI                        -> CrossRef, then OpenAlex
  * SemanticScholar CorpusId (url)   -> Semantic Scholar (DOI-less but real)
  * title+author+year only           -> CrossRef/OpenAlex title search
"""
from __future__ import annotations

import dataclasses
import re
from typing import Callable, List, Optional

ResolverFn = Callable[[dict], "Optional[ResolvedRef]"]

_ARXIV_DOI_RE = re.compile(r"^10\.48550/arxiv\.", re.IGNORECASE)
_CORPUSID_RE = re.compile(r"corpus[_ ]?id[:/=]\s*(\d+)", re.IGNORECASE)


@dataclasses.dataclass
class ResolvedRef:
    title: Optional[str]
    doi: Optional[str]
    source: str  # crossref | openalex | arxiv | semantic_scholar | ...


def _authors_list(entry: dict) -> List[str]:
    raw = entry.get("author") or ""
    return [a.strip() for a in re.split(r"\band\b", raw) if a.strip()]


def _std(meta: Optional[dict], source: str) -> Optional[ResolvedRef]:
    if not meta:
        return None
    basic = meta.get("basic") or {}
    id_ = meta.get("id") or {}
    doi = id_.get("doi") or (meta.get("externalIds") or {}).get("DOI")
    title = basic.get("title")
    # CrossRef/OpenAlex/ArXiv's "not found" fallback (_create_minimal_metadata,
    # see _BaseDOIEngine) echoes the query's own title/year/authors back into
    # `basic.*` with no DOI -- structurally indistinguishable from a genuine
    # match's extracted title. Without a DOI, a title from one of these three
    # engines is more likely an echoed miss than a resolved hit, so require
    # one. Semantic Scholar's CorpusId lookup is exempt: it returns bare None
    # on a miss (never reaches this echo shape), so a title-without-DOI hit
    # there is genuinely DOI-less-but-real, matching its search comment above.
    if source in ("crossref", "openalex", "arxiv") and not doi:
        return None
    return ResolvedRef(title=title, doi=doi, source=source)


def default_resolver(entry: dict, *, offline: bool = False) -> Optional[ResolvedRef]:
    if offline:
        return None
    doi = (entry.get("doi") or "").strip()
    url = (entry.get("url") or "").strip()
    eprint = (entry.get("eprint") or "").strip()
    title = entry.get("title")
    year = entry.get("year")
    authors = _authors_list(entry)

    # Lazy imports: the metadata engines pull heavy/optional deps and network.
    try:
        from ..metadata_engines.individual.ArXivEngine import ArXivEngine
        from ..metadata_engines.individual.CrossRefEngine import CrossRefEngine
        from ..metadata_engines.individual.OpenAlexEngine import OpenAlexEngine
        from ..metadata_engines.individual.SemanticScholarEngine import (
            SemanticScholarEngine,
        )
    except Exception:
        return None

    # 1) arXiv identifiers. A bare `eprint` (BibTeX/BibLaTeX convention:
    # eprint + archivePrefix={arXiv}, what arXiv's own "export citation"
    # produces) IS the arXiv ID -- canonicalize it to an arXiv DOI so it
    # goes through the deterministic id_list lookup below (_search_by_doi),
    # not the keyword-based title search, which can miss a real, findable
    # paper when its title reduces to a couple of generic keywords (e.g.
    # "Attention Is All You Need" -> just "attention"/"need") and falls
    # through to an unreliable CrossRef title-search fallback instead.
    arxiv_doi = doi if _ARXIV_DOI_RE.match(doi) else (
        f"10.48550/arxiv.{eprint}" if eprint else None
    )
    if arxiv_doi:
        got = _std(ArXivEngine().search(doi=arxiv_doi, title=title), "arxiv")
        if got:
            return got

    # 2) real DOI -> CrossRef then OpenAlex
    if doi and not _ARXIV_DOI_RE.match(doi):
        for eng, name in ((CrossRefEngine, "crossref"), (OpenAlexEngine, "openalex")):
            got = _std(eng().search(doi=doi), name)
            if got:
                return got

    # 3) Semantic Scholar CorpusId (DOI-less-but-real)
    cid = _CORPUSID_RE.search(url) or _CORPUSID_RE.search(entry.get("note") or "")
    if cid:
        got = _std(
            SemanticScholarEngine().search(corpus_id=cid.group(1)), "semantic_scholar"
        )
        if got:
            return got

    # 4) title/author/year fuzzy search
    if title:
        for eng, name in ((CrossRefEngine, "crossref"), (OpenAlexEngine, "openalex")):
            got = _std(
                eng().search(title=title, year=year, authors=authors, max_results=1),
                name,
            )
            if got:
                return got
    return None


# EOF
