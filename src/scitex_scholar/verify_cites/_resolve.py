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

A lookup that could not be MADE (HTTP 429 rate limiting, 5xx, network error)
is not a miss: the engines swallow those errors and return their "not found"
fallback, which used to surface as a sim=0.0 "weak title match" (DOI path) or
as HALLUCINATED (title-only path). The default resolver watches the HTTP
responses each engine actually received and raises :class:`LookupFailed` when
no source answered and at least one failed, so the caller can report "could not
be checked" instead of a content verdict.
"""

from __future__ import annotations

import dataclasses
import re
from typing import Callable, List, Optional

ResolverFn = Callable[[dict], "Optional[ResolvedRef]"]

_ARXIV_DOI_RE = re.compile(r"^10\.48550/arxiv\.", re.IGNORECASE)
_CORPUSID_RE = re.compile(r"corpus[_ ]?id[:/=]\s*(\d+)", re.IGNORECASE)


class LookupFailed(RuntimeError):
    """No metadata service could be ASKED about an entry (not a miss).

    Raised by :func:`default_resolver` when every source either failed at the
    transport level (HTTP 429 / 5xx / no response) or genuinely missed, and at
    least one failed -- so "not found" cannot be concluded. ``rate_limited``
    is True when any failure was an HTTP 429.
    """

    def __init__(self, source: str, reason: str, *, rate_limited: bool = False):
        super().__init__(f"{source}: {reason}")
        self.source = source
        self.reason = reason
        self.rate_limited = rate_limited


@dataclasses.dataclass
class ResolvedRef:
    title: Optional[str]
    doi: Optional[str]
    source: str  # crossref | openalex | arxiv | semantic_scholar | ...
    # True for a doi/arxiv-id/corpus_id lookup (deterministic: the same query
    # returns the same record). False for a title/author/year fuzzy search
    # (CrossRef/OpenAlex's title index is not stable across calls -- see
    # classify(), which caps this case at UNVERIFIED regardless of
    # title_similarity; scitex-writer, 2026-07-12).
    identifier_based: bool = True


def _authors_list(entry: dict) -> List[str]:
    raw = entry.get("author") or ""
    return [a.strip() for a in re.split(r"\band\b", raw) if a.strip()]


def _std(
    meta: Optional[dict], source: str, *, identifier_based: bool = True
) -> Optional[ResolvedRef]:
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
    # The same fallback for a DOI query echoes the queried DOI with NO title --
    # what a rate-limited / failed DOI lookup returns. A record without a
    # title cannot be title-verified either, so it is never a hit.
    if not (title or "").strip():
        return None
    return ResolvedRef(
        title=title, doi=doi, source=source, identifier_based=identifier_based
    )


def _transport_failure(statuses: List[Optional[int]]) -> Optional[str]:
    """Why a lookup could not be made, from the HTTP statuses it received.

    ``None`` in ``statuses`` marks a request that got no response at all.
    Returns ``None`` when the service answered the query (2xx, 404, other
    4xx): then an empty result is a genuine miss. 401/403 (refused) and 408
    (timed out) mean the query was not answered.
    """
    if not statuses:
        return None
    last = statuses[-1]
    if last is None:
        return "no response (network error or timeout)"
    if last == 429:
        return "rate-limited (HTTP 429)"
    if last in (401, 403):
        return f"access refused (HTTP {last})"
    if last == 408:
        return "request timed out (HTTP 408)"
    if last >= 500:
        return f"service error (HTTP {last})"
    return None


def _lookup(engine, source: str, *, identifier_based: bool = True, **query):
    """Run one engine query; separate a transport failure from a miss.

    Returns the :class:`ResolvedRef` on a hit and ``None`` on a genuine miss.
    Raises :class:`LookupFailed` when the service could not be asked. The
    engines swallow HTTP/network errors, so the responses they actually
    received are recorded with a ``requests`` response hook on their session.
    """
    import requests

    statuses: List[Optional[int]] = []

    def _record(response, *args, **kwargs):
        statuses.append(response.status_code)

    hooks = engine.session.hooks.setdefault("response", [])
    hooks.append(_record)
    try:
        meta = engine.search(**query)
    except requests.RequestException as exc:  # engines that re-raise (tenacity)
        raise LookupFailed(source, f"{type(exc).__name__}: {exc}") from exc
    finally:
        hooks.remove(_record)
    got = _std(meta, source, identifier_based=identifier_based)
    if got is not None:
        return got
    if meta is not None and not statuses:
        # The engine produced its not-found fallback without ANY response:
        # the request itself failed (connection refused, DNS, timeout).
        statuses.append(None)
    reason = _transport_failure(statuses)
    if reason is not None:
        raise LookupFailed(source, reason, rate_limited=statuses[-1] == 429)
    return None


def _default_engines() -> Optional[dict]:
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
    return {
        "arxiv": ArXivEngine(),
        "crossref": CrossRefEngine(),
        "openalex": OpenAlexEngine(),
        "semantic_scholar": SemanticScholarEngine(),
    }


def default_resolver(
    entry: dict, *, offline: bool = False, engines: Optional[dict] = None
) -> Optional[ResolvedRef]:
    """Resolve ``entry``; raise :class:`LookupFailed` if no source could answer.

    ``engines`` maps a source name (``arxiv``, ``crossref``, ``openalex``,
    ``semantic_scholar``) to an engine instance; missing names are skipped.
    Defaults to fresh instances of the real engines.
    """
    if offline:
        return None
    doi = (entry.get("doi") or "").strip()
    url = (entry.get("url") or "").strip()
    eprint = (entry.get("eprint") or "").strip()
    title = entry.get("title")
    year = entry.get("year")
    authors = _authors_list(entry)

    if engines is None:
        engines = _default_engines()
        if engines is None:
            return None

    failures: List[LookupFailed] = []

    def _try(name, *, identifier_based=True, **query):
        engine = engines.get(name)
        if engine is None:
            return None
        try:
            return _lookup(engine, name, identifier_based=identifier_based, **query)
        except LookupFailed as exc:
            failures.append(exc)
            return None

    # 1) arXiv identifiers. A bare `eprint` (BibTeX/BibLaTeX convention:
    # eprint + archivePrefix={arXiv}, what arXiv's own "export citation"
    # produces) IS the arXiv ID -- canonicalize it to an arXiv DOI so it
    # goes through the deterministic id_list lookup below (_search_by_doi),
    # not the keyword-based title search, which can miss a real, findable
    # paper when its title reduces to a couple of generic keywords (e.g.
    # "Attention Is All You Need" -> just "attention"/"need") and falls
    # through to an unreliable CrossRef title-search fallback instead.
    arxiv_doi = (
        doi
        if _ARXIV_DOI_RE.match(doi)
        else (f"10.48550/arxiv.{eprint}" if eprint else None)
    )
    if arxiv_doi:
        got = _try("arxiv", doi=arxiv_doi, title=title)
        if got:
            return got

    # 2) real DOI -> CrossRef then OpenAlex
    if doi and not _ARXIV_DOI_RE.match(doi):
        for name in ("crossref", "openalex"):
            got = _try(name, doi=doi)
            if got:
                return got

    # 3) Semantic Scholar CorpusId (DOI-less-but-real)
    cid = _CORPUSID_RE.search(url) or _CORPUSID_RE.search(entry.get("note") or "")
    if cid:
        got = _try("semantic_scholar", corpus_id=cid.group(1))
        if got:
            return got

    # 4) title/author/year fuzzy search. Not identifier_based: CrossRef/
    # OpenAlex's title index is not stable across calls for the identical
    # query, so classify() must never treat a hit from this step as
    # deterministic evidence -- caps at UNVERIFIED regardless of similarity.
    if title:
        for name in ("crossref", "openalex"):
            got = _try(
                name,
                identifier_based=False,
                title=title,
                year=year,
                authors=authors,
                max_results=1,
            )
            if got:
                return got

    # Nothing resolved. If any source could not be asked, "not found" is not
    # established -- report the lookup failure, never a miss.
    if failures:
        raise LookupFailed(
            ", ".join(sorted({f.source for f in failures})),
            "; ".join(f"{f.source} {f.reason}" for f in failures),
            rate_limited=any(f.rate_limited for f in failures),
        )
    return None


# EOF
