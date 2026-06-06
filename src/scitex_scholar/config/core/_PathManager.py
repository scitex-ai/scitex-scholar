#!/usr/bin/env python3
# Timestamp: "2025-10-13 05:03:58 (ywatanabe)"
# File: /home/ywatanabe/proj/scitex_repo/src/scitex/scholar/config/core/_PathManager.py
# ----------------------------------------
from __future__ import annotations

import os

__FILE__ = "./src/scitex/scholar/config/core/_PathManager.py"
__DIR__ = os.path.dirname(__FILE__)
# ----------------------------------------

"""
PathManager with complete PATH_STRUCTURE integration.

All directory paths are defined in PATH_STRUCTURE at the top.
All get_ methods use PATH_STRUCTURE consistently.
No direct path concatenation (self.*_dir / "subdir").
"""

from pathlib import Path
from typing import Dict, List, Optional

import scitex_logging as logging

from ._path_helpers import (
    TidinessConstraints,
    cleanup_old_files,
    generate_paper_id,
    sanitize_collection_name as _sanitize_collection_name,
    sanitize_filename as _sanitize_filename,
)

logger = logging.getLogger(__name__)


# Directory structure definition
# All paths are relative to SCHOLAR_DIR (default: ~/.scitex/scholar)
# Only SCITEX_DIR is configurable via environment variable
#
# Regenerable data (cache, logs, workspace, backups, downloads) lives under
# runtime/ per the local-state-directories convention (§4b).
# Tracked/user data (config, library) stays at the root (§4a).
PATH_STRUCTURE = {
    # Base — tracked config
    "config_dir": "config",
    # Regenerable paths under runtime/
    "backup_dir": "runtime/backup",
    "log_dir": "runtime/log",
    # Cache (regenerable)
    "cache_dir": "runtime/cache",
    "cache_auth_dir": "runtime/cache/auth",
    "cache_auth_json": "runtime/cache/auth/{auth_name}.json",
    "cache_auth_json_lock": "runtime/cache/auth/{auth_name}.json.lock",
    "cache_chrome_dir": "runtime/cache/chrome",
    "cache_engine_dir": "runtime/cache/engine",
    "cache_url_dir": "runtime/cache/url",
    "cache_download_dir": "runtime/cache/pdf_downloader",
    # Library — user data (tracked at root, not regenerable)
    "library_dir": "library",
    "library_master_dir": "library/MASTER",  # STORAGE
    "library_project_dir": "library/{project_name}",
    "library_project_info_dir": "library/{project_name}/info",
    "library_project_info_bibtex_dir": "library/{project_name}/info/bibtex",
    "library_project_logs_dir": "library/{project_name}/logs",
    "library_project_screenshots_dir": "library/{project_name}/screenshots",
    "library_master_paper_dir": "library/MASTER/{paper_id}",
    "library_master_paper_screenshots_dir": "library/MASTER/{paper_id}/screenshots",
    # Downloads staging (regenerable — moved under runtime/)
    "library_downloads_dir": "runtime/library/downloads",
    # Individual Entry
    "library_project_entry_dirname": "PDF-{n_pdfs:02d}_CC-{citation_count:06d}_IF-{impact_factor:03d}_{year:04d}_{first_author}_{journal_name}",
    "library_project_entry_dir": "library/{project_name}/{entry_dir_name}",
    "library_project_entry_pdf_fname": "{first_author}-{year:04d}-{journal_name}.pdf",
    "library_project_entry_metadata_json": "library/{project_name}/{entry_dir_name}/metadata.json",
    "library_project_entry_logs_dir": "library/{project_name}/{entry_dir_name}/logs",
    # Workspace (regenerable)
    "workspace_dir": "runtime/workspace",
    "workspace_logs_dir": "runtime/workspace/logs",
    "workspace_screenshots_dir": "runtime/workspace/screenshots",
    "workspace_screenshots_category_dir": "runtime/workspace/screenshots/{category}",
}


class PathManager:
    """PathManager with all paths defined in PATH_STRUCTURE."""

    def __init__(
        self,
        scholar_dir: Optional[Path] = None,
        constraints: Optional[TidinessConstraints] = None,
    ):
        # Root directory (only configurable path)
        if scholar_dir is None:
            scitex_dir = os.getenv("SCITEX_DIR", Path.home() / ".scitex")
            scholar_dir = Path(scitex_dir) / "scholar"
        self.scholar_dir = Path(scholar_dir).expanduser()

        # Build all fixed directory paths from PATH_STRUCTURE
        self.dirs = {}
        for key, relative_path in PATH_STRUCTURE.items():
            if "{" not in relative_path:  # Skip placeholders
                self.dirs[key] = self.scholar_dir / relative_path

        self.constraints = constraints or TidinessConstraints()

    def _ensure_directory(self, path: Path, mode: int = 0o755) -> Path:
        """Helper to ensure directory exists."""
        path.mkdir(parents=True, exist_ok=True, mode=mode)
        return path

    # ========================================
    # Base Directory Properties
    # ========================================
    @property
    def cache_dir(self) -> Path:
        """runtime/cache"""
        return self._ensure_directory(self.dirs["cache_dir"])

    @property
    def config_dir(self) -> Path:
        """config"""
        return self._ensure_directory(self.dirs["config_dir"])

    @property
    def library_dir(self) -> Path:
        """library"""
        return self._ensure_directory(self.dirs["library_dir"])

    @property
    def log_dir(self) -> Path:
        """runtime/log"""
        return self._ensure_directory(self.dirs["log_dir"])

    @property
    def workspace_dir(self) -> Path:
        """runtime/workspace"""
        return self._ensure_directory(self.dirs["workspace_dir"])

    @property
    def backup_dir(self) -> Path:
        """runtime/backup"""
        return self._ensure_directory(self.dirs["backup_dir"])

    # ========================================
    # Cache Directories
    # ========================================
    def get_cache_auth_dir(self) -> Path:
        """runtime/cache/auth"""
        return self._ensure_directory(self.dirs["cache_auth_dir"])

    def get_cache_auth_json(self, auth_name) -> Path:
        """runtime/cache/auth/{auth_name}.json"""
        return self.scholar_dir / PATH_STRUCTURE["cache_auth_json"].format(
            auth_name=auth_name
        )

    def get_cache_auth_json_lock(self, auth_name) -> Path:
        """runtime/cache/auth/{auth_name}.json.lock"""
        return self.scholar_dir / PATH_STRUCTURE["cache_auth_json_lock"].format(
            auth_name=auth_name
        )

    def get_cache_chrome_dir(self, profile_name: str) -> Path:
        """runtime/cache/chrome/{profile_name}"""
        return self._ensure_directory(self.dirs["cache_chrome_dir"] / profile_name)

    def get_cache_engine_dir(self) -> Path:
        """runtime/cache/engine"""
        return self._ensure_directory(self.dirs["cache_engine_dir"])

    def get_cache_url_dir(self) -> Path:
        """runtime/cache/url"""
        return self._ensure_directory(self.dirs["cache_url_dir"])

    def get_cache_download_dir(self) -> Path:
        """runtime/cache/pdf_downloader"""
        return self._ensure_directory(self.dirs["cache_download_dir"])

    # ========================================
    # Library Directories
    # ========================================
    def get_library_master_dir(self) -> Path:
        """library/MASTER - STORAGE for papers"""
        return self._ensure_directory(self.dirs["library_master_dir"])

    def get_library_project_dir(self, project: str) -> Path:
        """library/{project_name}"""
        project = _sanitize_collection_name(project, self.constraints)
        assert project.upper() != "MASTER", "MASTER is reserved"

        path_template = PATH_STRUCTURE["library_project_dir"]
        relative_path = path_template.format(project_name=project)
        return self._ensure_directory(self.scholar_dir / relative_path)

    def get_library_project_info_dir(self, project: str) -> Path:
        """library/{project_name}/info"""
        project = _sanitize_collection_name(project, self.constraints)
        path_template = PATH_STRUCTURE["library_project_info_dir"]
        relative_path = path_template.format(project_name=project)
        return self._ensure_directory(self.scholar_dir / relative_path)

    def get_library_project_info_bibtex_dir(self, project: str) -> Path:
        """library/{project_name}/info/bibtex"""
        project = _sanitize_collection_name(project, self.constraints)
        path_template = PATH_STRUCTURE["library_project_info_bibtex_dir"]
        relative_path = path_template.format(project_name=project)
        return self._ensure_directory(self.scholar_dir / relative_path)

    def get_library_project_logs_dir(self, project: str) -> Path:
        """library/{project_name}/logs"""
        project = _sanitize_collection_name(project, self.constraints)
        path_template = PATH_STRUCTURE["library_project_logs_dir"]
        relative_path = path_template.format(project_name=project)
        return self._ensure_directory(self.scholar_dir / relative_path)

    def get_library_project_screenshots_dir(self, project: str) -> Path:
        """library/{project_name}/screenshots"""
        project = _sanitize_collection_name(project, self.constraints)
        path_template = PATH_STRUCTURE["library_project_screenshots_dir"]
        relative_path = path_template.format(project_name=project)
        return self._ensure_directory(self.scholar_dir / relative_path)

    def get_library_master_paper_dir(self, paper_id: str) -> Path:
        """library/MASTER/{paper_id}"""
        path_template = PATH_STRUCTURE["library_master_paper_dir"]
        relative_path = path_template.format(paper_id=paper_id)
        return self._ensure_directory(self.scholar_dir / relative_path)

    def get_library_master_paper_screenshots_dir(self, paper_id: str) -> Path:
        """library/MASTER/{paper_id}/screenshots"""
        path_template = PATH_STRUCTURE["library_master_paper_screenshots_dir"]
        relative_path = path_template.format(paper_id=paper_id)
        return self._ensure_directory(self.scholar_dir / relative_path)

    def get_library_downloads_dir(self) -> Path:
        """runtime/library/downloads - STAGING for browser downloads"""
        return self._ensure_directory(self.dirs["library_downloads_dir"])

    # ========================================
    # Entry Directories, Paths, and Names
    # ========================================
    def get_library_project_entry_dirname(
        self,
        n_pdfs: int,
        citation_count: int,
        impact_factor: int,
        year: int,
        first_author: str,
        journal_name: str,
    ) -> str:
        """Format entry directory name using PATH_STRUCTURE template."""
        first_author = _sanitize_filename(first_author, self.constraints)
        journal_name = _sanitize_filename(journal_name, self.constraints)
        return PATH_STRUCTURE["library_project_entry_dirname"].format(
            n_pdfs=n_pdfs,
            citation_count=citation_count,
            impact_factor=impact_factor,
            year=year,
            first_author=first_author,
            journal_name=journal_name,
        )

    def get_library_project_entry_pdf_fname(
        self, first_author: str, year: int, journal_name: str
    ) -> str:
        """Format PDF filename using PATH_STRUCTURE template."""
        first_author = _sanitize_filename(first_author, self.constraints)
        journal_name = _sanitize_filename(journal_name, self.constraints)
        return PATH_STRUCTURE["library_project_entry_pdf_fname"].format(
            first_author=first_author,
            year=year,
            journal_name=journal_name,
        )

    def get_library_project_entry_dir(self, project: str, entry_dir_name: str) -> Path:
        """library/{project_name}/{entry_dir_name}"""
        project = _sanitize_collection_name(project, self.constraints)
        path_template = PATH_STRUCTURE["library_project_entry_dir"]
        relative_path = path_template.format(
            project_name=project, entry_dir_name=entry_dir_name
        )
        return self._ensure_directory(self.scholar_dir / relative_path)

    def get_library_project_entry_metadata_json(
        self, project: str, entry_dir_name: str
    ) -> Path:
        """library/{project_name}/{entry_dir_name}/metadata.json"""
        project = _sanitize_collection_name(project, self.constraints)
        path_template = PATH_STRUCTURE["library_project_entry_metadata_json"]
        relative_path = path_template.format(
            project_name=project, entry_dir_name=entry_dir_name
        )
        return self.scholar_dir / relative_path

    def get_library_project_entry_logs_dir(
        self, project: str, entry_dir_name: str
    ) -> Path:
        """library/{project_name}/{entry_dir_name}/logs"""
        project = _sanitize_collection_name(project, self.constraints)
        path_template = PATH_STRUCTURE["library_project_entry_logs_dir"]
        relative_path = path_template.format(
            project_name=project, entry_dir_name=entry_dir_name
        )
        return self._ensure_directory(self.scholar_dir / relative_path)

    # ========================================
    # Workspace Directories
    # ========================================
    def get_workspace_dir(self) -> Path:
        """runtime/workspace - Working directory for temporary operations"""
        return self._ensure_directory(self.dirs["workspace_dir"])

    def get_workspace_logs_dir(self) -> Path:
        """runtime/workspace/logs"""
        return self._ensure_directory(self.dirs["workspace_logs_dir"])

    def get_workspace_screenshots_dir(self, category: Optional[str] = None) -> Path:
        """runtime/workspace/screenshots or runtime/workspace/screenshots/{category}"""
        if category:
            category = _sanitize_filename(category, self.constraints)
            path_template = PATH_STRUCTURE["workspace_screenshots_category_dir"]
            relative_path = path_template.format(category=category)
            return self._ensure_directory(self.scholar_dir / relative_path)
        else:
            return self._ensure_directory(self.dirs["workspace_screenshots_dir"])

    # ========================================
    # Paper Storage Paths
    # ========================================
    def get_paper_storage_paths(
        self,
        doi: Optional[str] = None,
        title: Optional[str] = None,
        authors: Optional[List[str]] = None,
        year: Optional[int] = None,
        journal: Optional[str] = None,
        project: str = "MASTER",
    ) -> tuple:
        """Generate storage paths and metadata for a paper.

        Args:
            doi: DOI identifier
            title: Paper title
            authors: List of authors
            year: Publication year
            journal: Journal name
            project: Project name (default: "MASTER")

        Returns:
            Tuple of (storage_path, readable_name, paper_id)
        """
        # Generate unique paper ID
        paper_id = generate_paper_id(
            doi=doi, title=title, authors=authors, year=year
        )

        # Get storage path (always in MASTER directory)
        storage_path = self.get_library_master_paper_dir(paper_id)

        # Generate readable name
        first_author = "Unknown"
        if authors and len(authors) > 0:
            author_parts = str(authors[0]).strip().split()
            if author_parts:
                first_author = author_parts[-1]

        journal_clean = _sanitize_filename(journal, self.constraints) if journal else "Unknown"
        year_str = str(year) if year else "NoYear"

        readable_name = f"{first_author}-{year_str}-{journal_clean}"

        return (storage_path, readable_name, paper_id)

    # ========================================
    # Maintenance
    # ========================================
    def perform_maintenance(self) -> Dict[str, int]:
        """Perform directory maintenance using get_ methods."""
        results = {
            "cache_cleaned": 0,
            "workspace_cleaned": 0,
            "screenshots_cleaned": 0,
            "downloads_cleaned": 0,
        }

        results["cache_cleaned"] = cleanup_old_files(
            self.cache_dir, self.constraints.cache_retention_days
        )
        results["workspace_cleaned"] = cleanup_old_files(
            self.get_workspace_logs_dir(),
            self.constraints.workspace_retention_days,
        )
        results["screenshots_cleaned"] = cleanup_old_files(
            self.get_workspace_screenshots_dir(),
            self.constraints.screenshots_retention_days,
        )
        results["downloads_cleaned"] = cleanup_old_files(
            self.get_library_downloads_dir(),
            self.constraints.downloads_retention_days,
        )

        return results

    # ========================================
    # Backward-compat migration
    # ========================================
    def migrate_old_paths(self) -> None:
        """Migrate data from old pre-runtime paths to new runtime/ paths.

        Before v1.5, regenerable data lived directly under scholar_dir/
        (e.g. ~/.scitex/scholar/cache/). Now it lives under
        scholar_dir/runtime/ (e.g. ~/.scitex/scholar/runtime/cache/).

        Moves old → new with a one-time deprecation warning. Old paths
        that don't exist are silently skipped.
        """
        import shutil

        old_to_new = {
            "cache":      "runtime/cache",
            "log":        "runtime/log",
            "workspace":  "runtime/workspace",
        }

        for old_rel, new_rel in old_to_new.items():
            old_path = self.scholar_dir / old_rel
            new_path = self.scholar_dir / new_rel
            if old_path.exists() and not old_path.is_symlink():
                if not new_path.exists():
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    old_path.rename(new_path)
                    logger.warning(
                        "Migrated %s → %s (one-time; remove this fallback "
                        "after confirming data is intact)",
                        old_path, new_path,
                    )


# Backward-compat alias — old callers import TidinessConstraints from here
# noinspection PyUnresolvedReferences
from ._path_helpers import TidinessConstraints as _  # noqa: F401, E402


# EOF
