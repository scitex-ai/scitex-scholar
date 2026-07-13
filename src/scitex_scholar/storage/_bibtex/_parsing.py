#!/usr/bin/env python3
# File: src/scitex_scholar/storage/_bibtex/_parsing.py
"""BibTeX -> Paper parsing for :class:`~..BibTeXHandler.BibTeXHandler`."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import scitex_logging as logging

if TYPE_CHECKING:
    from scitex_scholar.core.Paper import Paper

logger = logging.getLogger(__name__)

__all__ = ["BibTeXParsingMixin"]


class BibTeXParsingMixin:
    """Read BibTeX files/text and convert entries into :class:`Paper` objects."""

    def _extract_primitive(self, value):
        """Extract primitive value from DotDict or nested structure."""
        from scitex_dict import DotDict

        if value is None:
            return None
        if isinstance(value, DotDict):
            # Convert DotDict to plain dict first
            value = dict(value)
        if isinstance(value, dict):
            # For nested dict structures, return as-is
            return value
        # Return primitive types as-is
        return value

    def papers_from_bibtex(self, bibtex_input: Union[str, Path]) -> List[Paper]:
        """Create Papers from BibTeX file or content."""
        is_path = False
        input_str = str(bibtex_input)

        if len(input_str) < 500:
            if (
                input_str.endswith(".bib")
                or input_str.endswith(".bibtex")
                or "/" in input_str
                or "\\" in input_str
                or input_str.startswith("~")
                or input_str.startswith(".")
                or os.path.exists(os.path.expanduser(input_str))
            ):
                is_path = True

        if "\n@" in input_str or input_str.strip().startswith("@"):
            is_path = False

        if is_path:
            return self._papers_from_bibtex_file(input_str)
        else:
            return self._papers_from_bibtex_text(input_str)

    def _papers_from_bibtex_file(
        self, file_path: Union[str, Path], validate: bool = True
    ) -> List[Paper]:
        """Create Papers from a BibTeX file.

        Args:
            file_path: Path to BibTeX file
            validate: If True, validate BibTeX syntax before loading
        """
        bibtex_path = Path(os.path.expanduser(str(file_path)))
        if not bibtex_path.exists():
            raise ValueError(f"BibTeX file not found: {bibtex_path}")

        # Validate BibTeX file before loading
        if validate:
            from .._BibTeXValidator import validate_bibtex_file

            result = validate_bibtex_file(bibtex_path)
            if not result.is_valid:
                error_msgs = [str(e) for e in result.errors]
                raise ValueError(
                    f"Invalid BibTeX file: {bibtex_path}\n" + "\n".join(error_msgs)
                )
            if result.has_warnings:
                for warning in result.warnings:
                    logger.warning(f"BibTeX: {warning}")

        from scitex_io import load

        entries = load(str(bibtex_path))

        papers = []
        for entry in entries:
            paper = self.paper_from_bibtex_entry(entry)
            if paper:
                papers.append(paper)

        logger.info(f"Created {len(papers)} papers from BibTeX file")
        return papers

    def _papers_from_bibtex_text(self, bibtex_content: str) -> List[Paper]:
        """Create Papers from BibTeX content string."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
            f.write(bibtex_content)
            temp_path = f.name

        try:
            from scitex_io import load

            entries = load(temp_path)
        finally:
            os.unlink(temp_path)

        papers = []
        for entry in entries:
            paper = self.paper_from_bibtex_entry(entry)
            if paper:
                papers.append(paper)

        logger.info(f"Created {len(papers)} papers from BibTeX text")
        return papers

    def paper_from_bibtex_entry(self, entry: Dict[str, Any]) -> Optional[Paper]:
        """Convert BibTeX entry to Paper."""
        from ...core.Paper import Paper

        fields = entry.get("fields", {})
        title = fields.get("title", "")
        if not title:
            return None

        author_str = fields.get("author", "")
        authors = []
        if author_str:
            authors = [a.strip() for a in author_str.split(" and ")]

        basic_data = {
            "title": title,
            "title_source": "input",
            "authors": authors,
            "authors_source": "input" if authors else None,
            "abstract": fields.get("abstract", ""),
            "abstract_source": "input" if fields.get("abstract") else None,
            "year": int(fields.get("year")) if fields.get("year") else None,
            "year_source": "input" if fields.get("year") else None,
            "keywords": (
                fields.get("keywords", "").split(", ") if fields.get("keywords") else []
            ),
        }

        # Extract corpus_id from URL if present
        corpus_id = None
        url_field = fields.get("url", "")
        if url_field and "CorpusId" in url_field:
            import re

            match = re.search(r"CorpusId:(\d+)", url_field)
            if match:
                corpus_id = match.group(1)

        # Extract arXiv ID from volume field if present (e.g., "abs/2503.04921")
        arxiv_id = fields.get("eprint")
        arxiv_id_source = "input" if arxiv_id else None

        if not arxiv_id:
            volume_field = fields.get("volume", "")
            if volume_field:
                import re

                # Match patterns like "abs/2503.04921" or "2503.04921"
                match = re.search(r"(?:abs/)?(\d{4}\.\d+)", volume_field)
                if match:
                    arxiv_id = match.group(1)
                    arxiv_id_source = "volume"

        id_data = {
            "doi": fields.get("doi"),
            "doi_source": "input" if fields.get("doi") else None,
            "pmid": fields.get("pmid"),
            "pmid_source": "input" if fields.get("pmid") else None,
            "arxiv_id": arxiv_id,
            "arxiv_id_source": arxiv_id_source,
            "corpus_id": corpus_id,
            "corpus_id_source": "url" if corpus_id else None,
        }

        publication_data = {
            "journal": fields.get("journal"),
            "journal_source": "input" if fields.get("journal") else None,
        }

        # Parse citation count
        citation_count_data = None
        if "citation_count" in fields:
            import json

            try:
                # Try parsing as JSON first (for enriched BibTeX files)
                cc_raw = fields["citation_count"]
                if isinstance(cc_raw, str) and cc_raw.strip().startswith("{"):
                    citation_count_data = json.loads(cc_raw)
                    # Add source if not present
                    if "total_source" not in citation_count_data:
                        citation_count_data["total_source"] = "input"
                else:
                    # Simple integer format
                    citation_count_data = {
                        "total": int(cc_raw),
                        "total_source": "input",
                    }
            except (ValueError, TypeError, json.JSONDecodeError):
                pass

        url_data = {
            "pdf": fields.get("url"),
        }

        # Create Paper with Pydantic structure
        paper = Paper()

        # Set basic metadata
        paper.metadata.basic.title = basic_data.get("title", "")
        paper.metadata.basic.authors = basic_data.get("authors")
        paper.metadata.basic.abstract = basic_data.get("abstract")
        paper.metadata.basic.year = basic_data.get("year")
        paper.metadata.basic.keywords = basic_data.get("keywords")

        # Set ID metadata
        if id_data.get("doi"):
            paper.metadata.set_doi(id_data["doi"])
        paper.metadata.id.pmid = id_data.get("pmid")
        if id_data.get("arxiv_id"):
            paper.metadata.id.arxiv_id = id_data["arxiv_id"]
            paper.metadata.id.arxiv_id_engines = [
                id_data.get("arxiv_id_source", "input")
            ]
        if id_data.get("corpus_id"):
            paper.metadata.id.corpus_id = id_data["corpus_id"]
            paper.metadata.id.corpus_id_engines = ["url"]

        # Set publication metadata
        paper.metadata.publication.journal = publication_data.get("journal")
        paper.metadata.publication.volume = publication_data.get("volume")
        paper.metadata.publication.issue = publication_data.get("issue")
        paper.metadata.publication.publisher = publication_data.get("publisher")

        # Set citation count
        if citation_count_data and citation_count_data.get("total") is not None:
            paper.metadata.citation_count.total = citation_count_data["total"]

        # Set impact factor
        if "journal_impact_factor" in fields:
            impact_str = str(fields["journal_impact_factor"])
            if impact_str.replace(".", "").isdigit():
                paper.metadata.publication.impact_factor = float(impact_str)

        # Set URL metadata
        if url_data.get("pdf"):
            paper.metadata.url.pdfs.append({"url": url_data["pdf"], "source": "bibtex"})

        # Set container metadata
        paper.container.projects = [self.project] if self.project else []

        # Set BibTeX metadata as special fields
        paper._original_bibtex_fields = fields.copy()
        paper._bibtex_entry_type = entry.get("entry_type", "misc")
        paper._bibtex_key = entry.get("key", "")

        self._handle_enriched_metadata(paper, fields)

        return paper

    def _handle_enriched_metadata(self, paper: Paper, fields: Dict[str, Any]) -> None:
        """Handle enriched metadata from BibTeX fields."""
        if "citation_count" in fields:
            try:
                citation_str = str(fields["citation_count"]).replace(",", "")
                paper.citation_count.total = int(citation_str)
                paper.citation_count.total_engines = fields.get(
                    "citation_count_source", "bibtex"
                )
            except (ValueError, AttributeError):
                pass

        for field_name in fields:
            if "impact_factor" in field_name and "JCR" in field_name:
                try:
                    paper.publication.impact_factor = float(fields[field_name])
                    paper.publication.impact_factor_engines = fields.get(
                        "impact_factor_source", "bibtex"
                    )
                    break
                except (ValueError, AttributeError):
                    pass

        for field_name in fields:
            if "quartile" in field_name and "JCR" in field_name:
                try:
                    # Store in system or publication section
                    paper.publication["journal_quartile"] = fields[field_name]
                    break
                except AttributeError:
                    pass

        if "volume" in fields:
            try:
                paper.publication.volume = fields["volume"]
            except AttributeError:
                pass
        if "pages" in fields:
            try:
                # Split pages into first_page and last_page
                pages = fields["pages"]
                if pages and "-" in str(pages):
                    first, last = str(pages).split("-", 1)
                    paper.publication.first_page = first.strip()
                    paper.publication.last_page = last.strip()
                else:
                    paper.publication.first_page = pages
            except AttributeError:
                pass


# EOF
