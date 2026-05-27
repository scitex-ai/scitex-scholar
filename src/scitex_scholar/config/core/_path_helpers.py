#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Timestamp: "2025-10-13 05:03:58 (ywatanabe)"
# File: src/scitex/scholar/config/core/_path_helpers.py
# ----------------------------------------

"""
Path helpers extracted from _PathManager.py for line-count compliance.

Contains TidinessConstraints dataclass and sanitization/utility helpers.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import scitex_logging as logging

logger = logging.getLogger(__name__)


@dataclass
class TidinessConstraints:
    """Configuration for directory tidiness constraints."""

    max_filename_length: int = 100
    allowed_filename_chars: str = r"[a-zA-Z0-9._-]"
    forbidden_filename_patterns: List[str] = field(
        default_factory=lambda: [r"^\.", r"^~", r"\s{2,}", r"[<>:\"/\\|?*]"]
    )

    max_cache_size_mb: int = 1000
    max_workspace_size_mb: int = 2000
    max_screenshots_size_mb: int = 500
    max_downloads_size_mb: int = 1000

    cache_retention_days: int = 30
    workspace_retention_days: int = 7
    screenshots_retention_days: int = 14
    downloads_retention_days: int = 3

    max_directory_depth: int = 8
    max_collection_name_length: int = 50
    allowed_collection_chars: str = r"[a-zA-Z0-9_-]"


def sanitize_filename(
    filename: str,
    constraints: TidinessConstraints,
) -> str:
    """Sanitize filename by replacing spaces and dots with hyphens.

    This is the single source of truth for filename normalization.
    Examples:
        "IEEE J. Biomed. Health Inform" -> "IEEE-J-Biomed-Health-Inform"
        "Front. Neurosci" -> "Front-Neurosci"
        "Nature Reviews" -> "Nature-Reviews"
    """
    # Remove forbidden patterns first
    for pattern in constraints.forbidden_filename_patterns:
        filename = re.sub(pattern, "", filename)

    # Replace spaces and dots with hyphens (normalize separators)
    filename = filename.replace(" ", "-").replace(".", "-")

    # Remove any characters not allowed (alphanumeric, dash, underscore)
    filename = re.sub(r"[^a-zA-Z0-9._-]", "", filename)

    # Collapse multiple hyphens/underscores into single ones
    filename = re.sub(r"-{2,}", "-", filename)
    filename = re.sub(r"_{2,}", "_", filename)

    # Truncate if too long
    if len(filename) > constraints.max_filename_length:
        name, ext = os.path.splitext(filename)
        max_name_len = constraints.max_filename_length - len(ext)
        filename = name[:max_name_len] + ext

    # Strip leading/trailing separators
    filename = filename.strip("._-")

    if not filename:
        filename = f"unnamed_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    return filename


def sanitize_collection_name(
    collection_name: str,
    constraints: TidinessConstraints,
) -> str:
    """Sanitize collection/project name."""
    collection_name = re.sub(
        f"[^{constraints.allowed_collection_chars}]",
        "_",
        collection_name,
    )
    collection_name = re.sub(r"_{2,}", "_", collection_name)

    if len(collection_name) > constraints.max_collection_name_length:
        collection_name = collection_name[
            : constraints.max_collection_name_length
        ]

    collection_name = collection_name.strip("_")

    if not collection_name:
        collection_name = f"collection_{datetime.now().strftime('%Y%m%d')}"

    return collection_name


def generate_paper_id(
    doi: Optional[str] = None,
    title: Optional[str] = None,
    authors: Optional[List[str]] = None,
    year: Optional[int] = None,
) -> str:
    """Generate unique 8-digit paper ID."""
    doi = doi.strip() if isinstance(doi, str) and doi else None
    title = title.strip() if isinstance(title, str) and title else ""
    year = str(year) if year else ""

    if doi:
        clean_doi = doi.replace("https://doi.org/", "").replace(
            "http://dx.doi.org/", ""
        )
        content = f"DOI:{clean_doi}"
    else:
        first_author = "unknown"
        if authors and len(authors) > 0:
            author_parts = str(authors[0]).strip().split()
            if author_parts:
                first_author = author_parts[-1].lower()

        title_clean = re.sub(
            r"\b(the|and|of|in|on|at|to|for|with|by)\b", "", title.lower()
        )
        title_clean = re.sub(r"[^\w\s]", "", title_clean)
        title_clean = re.sub(r"\s+", " ", title_clean).strip()

        content = f"META:{title_clean}:{first_author}:{year}"

    hash_obj = hashlib.md5(content.encode("utf-8"))
    paper_id = hash_obj.hexdigest()[:8].upper()
    return sanitize_filename(paper_id, TidinessConstraints())


def cleanup_old_files(directory: Path, retention_days: int) -> int:
    """Clean up files older than retention period."""
    if not directory.exists():
        return 0

    cutoff_date = datetime.now() - timedelta(days=retention_days)
    cleaned_count = 0

    try:
        for file_path in directory.rglob("*"):
            if file_path.is_file():
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_time < cutoff_date:
                    file_path.unlink()
                    cleaned_count += 1
    except (PermissionError, OSError) as e:
        logger.warning(f"Error during cleanup: {e}")

    return cleaned_count


# EOF
