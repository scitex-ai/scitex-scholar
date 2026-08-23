#!/usr/bin/env python3
# File: src/scitex_scholar/storage/_bibtex/_projects.py
"""Project bibliography management for :class:`~..BibTeXHandler.BibTeXHandler`."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

import scitex_logging as logging

from ._comments import sanitize_bibtex_comments

logger = logging.getLogger(__name__)

__all__ = ["BibTeXProjectsMixin"]


class BibTeXProjectsMixin:
    """Maintain a project's ``info/bibliography/`` directory and exports."""

    def setup_project_bibliography(
        self,
        project: str,
        bibtex_files: Optional[List[Union[str, Path]]] = None,
    ) -> Optional[Path]:
        """Setup info/bibliography directory structure for a project.

        Creates:
            - info/bibliography/
            - info/bibliography/*.bib (symlinks to source files)
            - info/bibliography/combined.bib (merged unique entries)
            - info/{project}.bib -> bibliography/combined.bib

        Args:
            project: Project name
            bibtex_files: Optional list of BibTeX files to include

        Returns:
            Path to combined.bib file
        """
        if not self.config:
            raise ValueError("Config required for project bibliography management")

        # Get project directory
        project_dir = self.config.path_manager.get_library_project_dir(project)
        bib_dir = project_dir / "info" / "bibliography"
        bib_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Setting up bibliography for project: {project}")

        # Link provided BibTeX files
        if bibtex_files:
            for bib_file in bibtex_files:
                bib_file = Path(bib_file)
                if bib_file.exists():
                    link_name = bib_dir / f"{bib_file.stem}.bib"
                    if not link_name.exists():
                        link_name.symlink_to(bib_file.absolute())
                        logger.info(f"Linked: {link_name.name} -> {bib_file}")

        # Merge all BibTeX files in bibliography directory
        combined_path = self.update_combined_bibliography(project)

        # Create convenience symlink at project root
        project_bib_link = project_dir / "info" / f"{project}.bib"
        if project_bib_link.exists() or project_bib_link.is_symlink():
            project_bib_link.unlink()
        project_bib_link.symlink_to("bibliography/combined.bib")
        logger.success(f"Created {project}.bib -> bibliography/combined.bib")

        return combined_path

    def update_combined_bibliography(self, project: str) -> Optional[Path]:
        """Update combined.bib with all BibTeX files in bibliography directory.

        Args:
            project: Project name

        Returns:
            Path to updated combined.bib
        """
        if not self.config:
            raise ValueError("Config required for project bibliography management")

        project_dir = self.config.path_manager.get_library_project_dir(project)
        bib_dir = project_dir / "info" / "bibliography"

        if not bib_dir.exists():
            logger.warning(f"Bibliography directory not found: {bib_dir}")
            return None

        # Find all BibTeX files (excluding combined.bib itself)
        bib_files = [
            f
            for f in bib_dir.glob("*.bib")
            if f.name not in ["combined.bib", "merged.bib"]
        ]

        if not bib_files:
            logger.warning("No BibTeX files found in bibliography directory")
            return None

        logger.info(f"Merging {len(bib_files)} BibTeX files...")

        # Merge files
        combined_path = bib_dir / "combined.bib"
        merged_papers = self.merge_bibtex_files(
            bib_files, output_path=combined_path, dedup_strategy="smart"
        )

        logger.success(
            f"Updated combined.bib: {len(merged_papers)} unique papers "
            f"from {len(bib_files)} files"
        )

        return combined_path

    def export_project_bibliography(
        self,
        project: str,
        output_path: Optional[Union[str, Path]] = None,
        include_all_entries: bool = True,
    ) -> Optional[Path]:
        """Export all papers from project library to BibTeX file.

        This creates a BibTeX file from ALL papers in the project library,
        not just from existing BibTeX files. Useful for exporting the complete
        project bibliography after downloads and enrichment.

        Args:
            project: Project name
            output_path: Optional output path (default: info/bibliography/library_export.bib)
            include_all_entries: If True, export all papers; if False, only papers with PDFs

        Returns:
            Path to exported BibTeX file
        """
        if not self.config:
            raise ValueError("Config required for project bibliography export")

        project_dir = self.config.path_manager.get_library_project_dir(project)
        self.config.path_manager.get_library_master_dir()

        # Default output path
        if output_path is None:
            bib_dir = project_dir / "info" / "bibliography"
            bib_dir.mkdir(parents=True, exist_ok=True)
            output_path = bib_dir / "library_export.bib"
        else:
            output_path = Path(output_path)

        logger.info(f"Exporting project bibliography: {project}")

        # Collect all papers from project symlinks
        from ...core.Paper import Paper

        papers = []

        for item in project_dir.iterdir():
            if not item.is_symlink():
                continue

            # Resolve symlink to master directory
            try:
                master_path = item.resolve()
                if not master_path.exists():
                    logger.warning(f"Broken symlink: {item.name}")
                    continue

                # Load metadata.json
                metadata_file = master_path / "metadata.json"
                if not metadata_file.exists():
                    logger.warning(f"No metadata: {master_path.name}")
                    continue

                # Check for PDF if filtering
                if not include_all_entries:
                    pdf_files = list(master_path.glob("*.pdf"))
                    if not pdf_files:
                        continue

                # Load paper
                paper = Paper.from_file(metadata_file)
                if paper:
                    papers.append(paper)

            except Exception as e:
                logger.warning(f"Error loading {item.name}: {e}")
                continue

        logger.info(f"Found {len(papers)} papers in project library")

        if not papers:
            logger.warning("No papers found to export")
            return None

        # Convert to BibTeX
        from datetime import datetime

        from ...core.Papers import Papers

        Papers(papers, project=project)

        # Save with project info header
        bibtex_content = []
        bibtex_content.append(
            "% ============================================================"
        )
        bibtex_content.append("% SciTeX Scholar - Project Library Export")
        bibtex_content.append(f"% Project: {project}")
        bibtex_content.append(
            f"% Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        bibtex_content.append(f"% Entries: {len(papers)}")
        bibtex_content.append(
            f"% Filter: {'All papers' if include_all_entries else 'Papers with PDFs only'}"
        )
        bibtex_content.append(
            "% ============================================================"
        )
        bibtex_content.append("")

        # Add papers
        for paper in papers:
            entry = self.paper_to_bibtex_entry(paper)
            bibtex_content.append(self._format_bibtex_entry(entry))

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(sanitize_bibtex_comments("\n".join(bibtex_content)))

        logger.success(f"Exported {len(papers)} papers to: {output_path}")

        # Update combined.bib to include this export
        self.update_combined_bibliography(project)

        return Path(output_path) if output_path is not None else None


# EOF
