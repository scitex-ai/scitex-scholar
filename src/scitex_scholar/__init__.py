#!/usr/bin/env python3
"""SciTeX Scholar -- scientific paper search, enrichment, and management.

Quick Start:
    from scitex_scholar import Scholar, Paper, Papers

    scholar = Scholar()
    papers = scholar.search("deep learning")
    papers.save("results.bib")

Installation:
    pip install scitex-scholar
"""

from __future__ import annotations

try:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _v

    try:
        __version__ = _v("scitex-scholar")
    except PackageNotFoundError:
        __version__ = "0.0.0+local"
    del _v, PackageNotFoundError
except ImportError:  # pragma: no cover — only on ancient Pythons
    __version__ = "0.0.0+local"
__author__ = "Yusuke Watanabe"

from ._utils.text._TextNormalizer import TextNormalizer as _TextNormalizer
from .auth import ScholarAuthManager
from .browser import ScholarBrowserManager
from .citation_graph import CitationGraphBuilder, plot_citation_graph
from .config import ScholarConfig
from .core.Paper import Paper
from .core.Papers import Papers
from .core.Scholar import Scholar
from .filters import apply_filters
from .formatting import (
    generate_cite_key,
    make_citation_key,
    papers_to_format,
    to_bibtex,
    to_endnote,
    to_ris,
    to_text_citation,
)
from .migration import from_connected_papers, to_connected_papers
from .url_finder import ScholarURLFinder


def clean_abstract(text: str) -> str:
    """Strip HTML/JATS XML tags from a CrossRef-style abstract.

    Handles `<jats:p>`, `<jats:italic>`, `<jats:bold>`, `<jats:sup>`,
    `<jats:sub>` and their plain-HTML counterparts (`<p>`, `<i>`,
    `<b>`, `<em>`, `<strong>`, `<sup>`, `<sub>`), plus common HTML
    entities (`&amp;`, `&lt;`, `&gt;`, `&quot;`, `&apos;`, `&nbsp;`).
    Normalizes whitespace.

    Parameters
    ----------
    text : str
        Raw abstract text from CrossRef API (or similar).

    Returns
    -------
    str
        Abstract with markup removed, safe for display.

    Examples
    --------
    >>> clean_abstract("<jats:p>Objective. <jats:italic>in vitro</jats:italic>.</jats:p>")
    'Objective. in vitro.'
    """
    return _TextNormalizer.strip_html_tags(text)


# Kept as a public flag so downstream shims (scitex.scholar re-export) can
# advertise availability without reaching into each submodule. Always True:
# if any of the imports above had failed, this module would not have loaded.
SCHOLAR_AVAILABLE = True

__all__ = [
    "__version__",
    "Scholar",
    "Paper",
    "Papers",
    "ScholarConfig",
    "ScholarAuthManager",
    "ScholarBrowserManager",
    "ScholarURLFinder",
    "CitationGraphBuilder",
    "plot_citation_graph",
    "to_bibtex",
    "to_ris",
    "to_endnote",
    "to_text_citation",
    "papers_to_format",
    "generate_cite_key",
    "make_citation_key",
    "from_connected_papers",
    "to_connected_papers",
    "apply_filters",
    "clean_abstract",
    "SCHOLAR_AVAILABLE",
]

# EOF
