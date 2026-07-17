#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure string normalization helpers for journal names and ISSNs.

No I/O, no network: matching rules only.
"""

from __future__ import annotations


def normalize_name(name: str) -> str:
    """
    Basic string normalization for matching.

    - Lowercase
    - Remove extra whitespace
    - Normalize punctuation
    """
    if not name:
        return ""
    # Lowercase
    name = name.lower()
    # Normalize whitespace
    name = " ".join(name.split())
    # Remove common punctuation variations
    name = name.replace(".", "").replace(",", "").replace(":", "")
    # Normalize ampersand
    name = name.replace(" & ", " and ")
    return name.strip()


def normalize_issn(issn: str) -> str:
    """Normalize ISSN format to XXXX-XXXX."""
    if not issn:
        return ""
    issn = issn.upper().replace("-", "").replace(" ", "")
    if len(issn) == 8:
        return f"{issn[:4]}-{issn[4:]}"
    return issn


# EOF
