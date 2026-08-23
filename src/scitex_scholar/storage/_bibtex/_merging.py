#!/usr/bin/env python3
# File: src/scitex_scholar/storage/_bibtex/_merging.py
"""Multi-file merge and deduplication for :class:`~..BibTeXHandler.BibTeXHandler`."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import scitex_logging as logging

if TYPE_CHECKING:
    from scitex_scholar.core.Paper import Paper
    from scitex_scholar.core.Papers import Papers

logger = logging.getLogger(__name__)

__all__ = ["BibTeXMergingMixin"]


class BibTeXMergingMixin:
    """Merge several BibTeX files into one, reconciling duplicate papers."""

    def merge_bibtex_files(
        self,
        file_paths: List[Union[str, Path]],
        output_path: Optional[Union[str, Path]] = None,
        dedup_strategy: str = "smart",
        return_details: bool = False,
        validate: bool = True,
    ) -> Union[Papers, Dict[str, Any]]:
        """Merge multiple BibTeX files intelligently handling duplicates.

        Args:
            file_paths: List of BibTeX files to merge
            output_path: Optional path to save merged BibTeX
            dedup_strategy: 'smart' (merge metadata), 'keep_first', 'keep_all'
            return_details: If True, return dict with papers and metadata
            validate: If True, validate all files before merging

        Returns:
            Merged Papers collection, or dict with 'papers', 'file_papers', 'stats'
        """
        from ...core.Papers import Papers

        # Validate all files before merging
        if validate:
            from .._BibTeXValidator import BibTeXValidator

            validator = BibTeXValidator()
            can_merge, results = validator.validate_before_merge(file_paths)

            if not can_merge:
                error_msgs = []
                for result in results:
                    if result.has_errors:
                        for error in result.errors:
                            error_msgs.append(f"{result.file_path}: {error}")
                raise ValueError(
                    "Cannot merge BibTeX files due to validation errors:\n"
                    + "\n".join(error_msgs)
                )

            # Log warnings
            for result in results:
                if result.has_warnings:
                    for warning in result.warnings:
                        logger.warning(f"BibTeX {result.file_path}: {warning}")

        all_papers = []
        file_papers = {}  # Track which papers came from which file
        duplicate_stats = {
            "total_input": 0,
            "duplicates_found": 0,
            "duplicates_merged": 0,
            "unique_papers": 0,
            "files_processed": [],
        }

        # Load all papers from files
        for file_path in file_paths:
            file_path = Path(file_path)
            try:
                papers = self.papers_from_bibtex(file_path)
                all_papers.extend(papers)
                file_papers[file_path.stem] = papers  # Store papers by source file
                duplicate_stats["total_input"] += len(papers)
                duplicate_stats["files_processed"].append(file_path)
                logger.info(f"Loaded {len(papers)} papers from {file_path}")
            except Exception as e:
                logger.warning(f"Failed to load {file_path}: {e}")

        if dedup_strategy == "keep_all":
            merged_papers = Papers(all_papers)
        else:
            # Deduplicate papers
            unique_papers = self._deduplicate_papers(
                all_papers, strategy=dedup_strategy, stats=duplicate_stats
            )
            merged_papers = Papers(unique_papers)

        # Save if output path provided
        if output_path:
            self.papers_to_bibtex_with_sources(
                merged_papers,
                output_path,
                source_files=duplicate_stats["files_processed"],
                file_papers=file_papers,
                stats=duplicate_stats,
            )

        # Log statistics
        logger.info(
            f"Merge complete: {duplicate_stats['unique_papers']} unique papers "
            f"from {duplicate_stats['total_input']} total "
            f"({duplicate_stats['duplicates_found']} duplicates)"
        )

        if return_details:
            return {
                "papers": merged_papers,
                "file_papers": file_papers,
                "stats": duplicate_stats,
            }
        else:
            return merged_papers

    def _deduplicate_papers(
        self,
        papers: List[Paper],
        strategy: str = "smart",
        stats: Optional[Dict] = None,
    ) -> List[Paper]:
        """Deduplicate a list of papers based on strategy.

        Args:
            papers: List of Paper objects
            strategy: 'smart' or 'keep_first'
            stats: Optional dict to track statistics

        Returns:
            List of unique papers
        """
        if not stats:
            stats = {"duplicates_found": 0, "duplicates_merged": 0}

        unique_papers = []
        paper_index = {}  # Track papers by DOI and title

        for paper in papers:
            # Create keys for indexing
            doi = paper.metadata.id.doi
            doi_key = doi.lower() if doi else None
            title = paper.metadata.basic.title
            title_key = self._normalize_title(title) if title else None

            is_duplicate = False
            merge_with = None

            # Check by DOI first (most reliable)
            if doi_key and doi_key in paper_index:
                is_duplicate = True
                merge_with = paper_index[doi_key]

            # Check by title if no DOI match
            elif title_key and title_key in paper_index:
                existing = paper_index[title_key]
                if self._are_same_paper(existing, paper):
                    is_duplicate = True
                    merge_with = existing

            if is_duplicate and merge_with:
                stats["duplicates_found"] += 1

                if strategy == "smart":
                    # Merge metadata from both papers
                    merged = self._merge_paper_metadata(merge_with, paper)
                    # Update the paper in our list
                    idx = unique_papers.index(merge_with)
                    unique_papers[idx] = merged
                    # Update index
                    if doi_key:
                        paper_index[doi_key] = merged
                    if title_key:
                        paper_index[title_key] = merged
                    stats["duplicates_merged"] += 1
                # else: keep_first - do nothing

            else:
                # New unique paper
                unique_papers.append(paper)
                if doi_key:
                    paper_index[doi_key] = paper
                if title_key:
                    paper_index[title_key] = paper

        stats["unique_papers"] = len(unique_papers)
        return unique_papers

    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison."""
        if not title:
            return ""
        # Remove punctuation, lowercase, collapse whitespace
        import re

        normalized = re.sub(r"[^\w\s]", "", title.lower())
        normalized = " ".join(normalized.split())
        return normalized

    def _are_same_paper(self, paper1: Paper, paper2: Paper) -> bool:
        """Determine if two papers are the same based on metadata."""
        # If both have DOIs and they match
        doi1 = paper1.metadata.id.doi
        doi2 = paper2.metadata.id.doi
        if doi1 and doi2:
            return doi1.lower() == doi2.lower()

        # Check title similarity
        title1_raw = paper1.metadata.basic.title
        title2_raw = paper2.metadata.basic.title
        if title1_raw and title2_raw:
            title1 = self._normalize_title(title1_raw)
            title2 = self._normalize_title(title2_raw)

            if title1 == title2:
                # Check year (allow 1 year difference for online vs print)
                year1 = paper1.metadata.basic.year
                year2 = paper2.metadata.basic.year
                if year1 and year2:
                    if abs(year1 - year2) <= 1:
                        return True
                else:
                    # No year to compare, assume same if title matches
                    return True

        return False

    def _merge_paper_metadata(self, paper1: Paper, paper2: Paper) -> Paper:
        """Merge metadata from two papers, keeping the most complete information."""
        from copy import deepcopy

        # Calculate completeness score for each paper
        score1 = sum(
            [
                1
                for field in [
                    paper1.metadata.id.doi,
                    paper1.metadata.basic.abstract,
                    paper1.metadata.publication.journal,
                    paper1.metadata.citation_count.total,
                    paper1.metadata.url.pdfs,
                    paper1.metadata.basic.authors,
                ]
                if field
            ]
        )
        score2 = sum(
            [
                1
                for field in [
                    paper2.metadata.id.doi,
                    paper2.metadata.basic.abstract,
                    paper2.metadata.publication.journal,
                    paper2.metadata.citation_count.total,
                    paper2.metadata.url.pdfs,
                    paper2.metadata.basic.authors,
                ]
                if field
            ]
        )

        # Start with the more complete paper
        if score1 >= score2:
            merged = deepcopy(paper1)
            donor = paper2
        else:
            merged = deepcopy(paper2)
            donor = paper1

        # Fill in missing fields from donor
        if not merged.metadata.id.doi and donor.metadata.id.doi:
            merged.metadata.set_doi(donor.metadata.id.doi)
        if not merged.metadata.basic.abstract and donor.metadata.basic.abstract:
            merged.metadata.basic.abstract = donor.metadata.basic.abstract
        if (
            not merged.metadata.publication.journal
            and donor.metadata.publication.journal
        ):
            merged.metadata.publication.journal = donor.metadata.publication.journal
        if (
            not merged.metadata.publication.publisher
            and donor.metadata.publication.publisher
        ):
            merged.metadata.publication.publisher = donor.metadata.publication.publisher
        if not merged.metadata.publication.volume and donor.metadata.publication.volume:
            merged.metadata.publication.volume = donor.metadata.publication.volume
        if not merged.metadata.publication.issue and donor.metadata.publication.issue:
            merged.metadata.publication.issue = donor.metadata.publication.issue
        if not merged.metadata.publication.pages and donor.metadata.publication.pages:
            merged.metadata.publication.pages = donor.metadata.publication.pages
        # Merge PDF URLs (union)
        for donor_pdf in donor.metadata.url.pdfs:
            if not any(
                p.get("url") == donor_pdf.get("url") for p in merged.metadata.url.pdfs
            ):
                merged.metadata.url.pdfs.append(donor_pdf)
        if not merged.metadata.url.publisher and donor.metadata.url.publisher:
            merged.metadata.url.publisher = donor.metadata.url.publisher

        # Take maximum citation count
        donor_cc = donor.metadata.citation_count.total or 0
        merged_cc = merged.metadata.citation_count.total or 0

        if donor_cc > merged_cc:
            merged.metadata.citation_count.total = donor_cc

        # Merge authors (union, preserving order)
        if donor.metadata.basic.authors and not merged.metadata.basic.authors:
            merged.metadata.basic.authors = donor.metadata.basic.authors
        elif donor.metadata.basic.authors and merged.metadata.basic.authors:
            # Add unique authors from donor
            for author in donor.metadata.basic.authors:
                if author not in merged.metadata.basic.authors:
                    merged.metadata.basic.authors.append(author)

        # Merge keywords (union)
        donor_keywords = donor.metadata.basic.keywords
        merged_keywords = merged.metadata.basic.keywords
        if donor_keywords:
            if merged_keywords:
                all_keywords = list(set(merged_keywords + donor_keywords))
                merged.metadata.basic.keywords = sorted(all_keywords)
            else:
                merged.metadata.basic.keywords = donor_keywords

        return merged


# EOF
