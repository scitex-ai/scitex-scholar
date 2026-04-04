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

__version__ = "0.2.0"

from .core.Scholar import Scholar
from .core.Paper import Paper
from .core.Papers import Papers
from .config import ScholarConfig
from .formatting import (
    generate_cite_key,
    make_citation_key,
    papers_to_format,
    to_bibtex,
    to_endnote,
    to_ris,
    to_text_citation,
)
from .filters import apply_filters

try:
    from .citation_graph import CitationGraphBuilder, plot_citation_graph
except ImportError:
    CitationGraphBuilder = None
    plot_citation_graph = None

try:
    from .migration import from_connected_papers, to_connected_papers
except ImportError:
    from_connected_papers = None
    to_connected_papers = None

SCHOLAR_AVAILABLE = True

__all__ = [
    "Scholar",
    "Paper",
    "Papers",
    "ScholarConfig",
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
    "SCHOLAR_AVAILABLE",
]

# EOF
