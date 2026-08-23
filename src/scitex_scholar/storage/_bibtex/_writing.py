#!/usr/bin/env python3
# File: src/scitex_scholar/storage/_bibtex/_writing.py
"""Paper -> BibTeX rendering for :class:`~..BibTeXHandler.BibTeXHandler`."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import scitex_logging as logging

from ._comments import sanitize_bibtex_comments

if TYPE_CHECKING:
    from scitex_scholar.core.Paper import Paper
    from scitex_scholar.core.Papers import Papers

logger = logging.getLogger(__name__)

__all__ = ["BibTeXWritingMixin"]


class BibTeXWritingMixin:
    """Render :class:`Paper` objects back out as BibTeX entries and files.

    Every method that emits file content funnels it through
    :func:`sanitize_bibtex_comments`, which is the single place that makes
    ``%`` header lines safe to re-parse.
    """

    def paper_to_bibtex_entry(self, paper: Paper) -> Dict[str, Any]:
        """Convert a Paper object to a BibTeX entry dictionary."""
        # Create entry type based on available data
        entry_type = getattr(paper, "_bibtex_entry_type", "misc")
        if paper.metadata.publication.journal:
            entry_type = "article"
        elif hasattr(paper, "booktitle") and paper.booktitle:
            entry_type = "inproceedings"

        # Create a unique key from authors and year
        authors = paper.metadata.basic.authors
        first_author = authors[0].split()[-1] if authors else "Unknown"
        year = paper.metadata.basic.year or "NoYear"
        key = getattr(paper, "_bibtex_key", f"{first_author}-{year}")

        # Build fields dictionary with all available data
        fields = {}

        # Basic fields
        if paper.metadata.basic.title:
            fields["title"] = paper.metadata.basic.title
        if paper.metadata.basic.authors:
            fields["author"] = " and ".join(paper.metadata.basic.authors)
        if paper.metadata.basic.year:
            fields["year"] = str(paper.metadata.basic.year)
        if paper.metadata.basic.abstract:
            fields["abstract"] = paper.metadata.basic.abstract
        if paper.metadata.basic.keywords:
            fields["keywords"] = ", ".join(paper.metadata.basic.keywords)

        # Identifiers
        if paper.metadata.id.doi:
            fields["doi"] = paper.metadata.id.doi
        if paper.metadata.id.pmid:
            fields["pmid"] = paper.metadata.id.pmid
        if paper.metadata.id.arxiv_id:
            fields["eprint"] = paper.metadata.id.arxiv_id

        # Publication info
        if paper.metadata.publication.journal:
            fields["journal"] = paper.metadata.publication.journal
        if paper.metadata.publication.volume:
            fields["volume"] = paper.metadata.publication.volume
        if paper.metadata.publication.pages:
            fields["pages"] = paper.metadata.publication.pages

        # Metrics
        citation_count_val = paper.metadata.citation_count.total
        if citation_count_val is not None and citation_count_val != 0:
            fields["citation_count"] = str(int(citation_count_val))

        impact_factor_val = paper.metadata.publication.impact_factor
        if impact_factor_val is not None:
            fields["journal_impact_factor"] = str(impact_factor_val)

        # URLs
        if paper.metadata.url.pdfs and len(paper.metadata.url.pdfs) > 0:
            # Use the first PDF URL
            pdf_url = paper.metadata.url.pdfs[0].get("url")
            if pdf_url:
                fields["url"] = pdf_url if isinstance(pdf_url, str) else str(pdf_url)

        # Include original BibTeX fields if they exist
        if hasattr(paper, "_original_bibtex_fields"):
            for k, v in paper._original_bibtex_fields.items():
                if k not in fields:  # Don't override updated fields
                    fields[k] = v

        return {"entry_type": entry_type, "key": key, "fields": fields}

    def papers_to_bibtex(
        self,
        papers: Union[List[Paper], Papers],
        output_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """Convert Papers collection to BibTeX format.

        Args:
            papers: Papers object or list of Paper objects
            output_path: Optional path to save the BibTeX file

        Returns:
            BibTeX content as string
        """
        # Handle Papers object
        if hasattr(papers, "papers"):
            paper_list = papers.papers
        else:
            paper_list = papers

        # Convert each paper to BibTeX entry
        entries = []
        for paper in paper_list:
            entry = self.paper_to_bibtex_entry(paper)
            entries.append(entry)

        # Generate BibTeX content
        bibtex_lines = []
        for entry in entries:
            entry_type = entry["entry_type"]
            key = entry["key"]
            fields = entry["fields"]

            bibtex_lines.append(f"@{entry_type}{{{key},")
            for field, value in fields.items():
                # Escape special characters in BibTeX
                value = str(value).replace("{", "\\{").replace("}", "\\}")
                bibtex_lines.append(f"  {field} = {{{value}}},")
            bibtex_lines.append("}\n")

        bibtex_content = sanitize_bibtex_comments("\n".join(bibtex_lines))

        # Save to file if path provided
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(bibtex_content)
            logger.success(f"Saved BibTeX to {output_path}")

        return bibtex_content

    def papers_to_bibtex_with_sources(
        self,
        papers: Union[List[Paper], Papers],
        output_path: Union[str, Path],
        source_files: List[Path] = None,
        file_papers: Dict[str, List[Paper]] = None,
        stats: Dict = None,
    ) -> str:
        """Save papers to BibTeX with source file comments and SciTeX header.

        Args:
            papers: Papers collection to save
            output_path: Path to save the BibTeX file
            source_files: List of source file paths
            file_papers: Dict mapping source file names to their papers
            stats: Merge statistics

        Returns:
            BibTeX content as string
        """
        from datetime import datetime

        # Handle Papers object
        if hasattr(papers, "papers"):
            paper_list = papers.papers
        else:
            paper_list = papers

        output_path = Path(output_path)

        # Generate header
        bibtex_lines = []
        bibtex_lines.append(
            "% ============================================================"
        )
        bibtex_lines.append("% SciTeX Scholar - Merged BibTeX File")
        bibtex_lines.append(
            f"% Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        bibtex_lines.append("% Author: Yusuke Watanabe")
        bibtex_lines.append(
            "% ============================================================"
        )

        if source_files:
            bibtex_lines.append("%")
            bibtex_lines.append("% Source Files:")
            for i, source_file in enumerate(source_files, 1):
                bibtex_lines.append(f"%   {i}. {source_file.name}")

        if stats:
            bibtex_lines.append("%")
            bibtex_lines.append("% Merge Statistics:")
            bibtex_lines.append(
                f"%   Total entries loaded: {stats.get('total_input', 0)}"
            )
            bibtex_lines.append(
                f"%   Unique entries: {stats.get('unique_papers', len(paper_list))}"
            )
            bibtex_lines.append(
                f"%   Duplicates found: {stats.get('duplicates_found', 0)}"
            )
            if stats.get("duplicates_merged"):
                bibtex_lines.append(
                    f"%   Duplicates merged: {stats['duplicates_merged']}"
                )

        bibtex_lines.append(
            "% ============================================================"
        )
        bibtex_lines.append("")

        # Group papers by source file if available
        if file_papers:
            for source_name, source_papers in file_papers.items():
                # Add section comment
                bibtex_lines.append("")
                bibtex_lines.append(
                    "% ============================================================"
                )
                bibtex_lines.append(f"% Source: {source_name}.bib")
                bibtex_lines.append(f"% Entries: {len(source_papers)}")
                bibtex_lines.append(
                    "% ============================================================"
                )
                bibtex_lines.append("")

                # Add papers from this source
                source_paper_set = set(
                    p.metadata.basic.title
                    for p in source_papers
                    if p.metadata.basic.title
                )
                for paper in paper_list:
                    title = paper.metadata.basic.title
                    if title and title in source_paper_set:
                        entry = self.paper_to_bibtex_entry(paper)
                        bibtex_lines.append(self._format_bibtex_entry(entry))
                        # Remove from set to avoid duplicates
                        source_paper_set.discard(title)

            # Add any papers not assigned to a source (e.g., merged duplicates)
            all_source_titles = set()
            for source_papers in file_papers.values():
                all_source_titles.update(
                    p.metadata.basic.title
                    for p in source_papers
                    if p.metadata.basic.title
                )

            unassigned = [
                p
                for p in paper_list
                if not p.metadata.basic.title
                or p.metadata.basic.title not in all_source_titles
            ]
            if unassigned:
                bibtex_lines.append("")
                bibtex_lines.append(
                    "% ============================================================"
                )
                bibtex_lines.append("% Merged/Unassigned Entries")
                bibtex_lines.append(f"% Entries: {len(unassigned)}")
                bibtex_lines.append(
                    "% ============================================================"
                )
                bibtex_lines.append("")
                for paper in unassigned:
                    entry = self.paper_to_bibtex_entry(paper)
                    bibtex_lines.append(self._format_bibtex_entry(entry))
        else:
            # No source tracking, just convert all papers
            for paper in paper_list:
                entry = self.paper_to_bibtex_entry(paper)
                bibtex_lines.append(self._format_bibtex_entry(entry))

        bibtex_content = sanitize_bibtex_comments("\n".join(bibtex_lines))

        # Save to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(bibtex_content)
        logger.success(f"Saved merged BibTeX to {output_path}")

        return bibtex_content

    def _format_bibtex_entry(self, entry: Dict) -> str:
        """Format a single BibTeX entry."""
        lines = []
        entry_type = entry["entry_type"]
        key = entry["key"]
        fields = entry["fields"]

        lines.append(f"@{entry_type}{{{key},")
        for field, value in fields.items():
            # Escape special characters in BibTeX
            value = str(value).replace("{", "\\{").replace("}", "\\}")
            lines.append(f"  {field} = {{{value}}},")
        lines.append("}\n")

        return "\n".join(lines)


# EOF
