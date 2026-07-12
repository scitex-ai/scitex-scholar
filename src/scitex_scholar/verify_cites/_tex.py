#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: src/scitex_scholar/verify_cites/_tex.py
# ----------------------------------------
"""Locate the ACTUAL compiled .bib and the set of cited keys.

The load-bearing lesson (neurovista, 2026-07-01): never trust the "source"
bib tree. A manuscript's ``\\bibliography{...}`` often points through a
symlink chain to a different file than the one agents edit. Always
``realpath`` the target so we verify the entries bibtex truly reads.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Set

# \cite, \citep, \citet, \citealt, \parencite, \textcite, \autocite, ... with
# optional [..] option args, capturing the {key,key2} payload.
_CITE_RE = re.compile(r"\\[a-zA-Z]*cite[a-zA-Z]*\*?\s*(?:\[[^\]]*\]\s*)*\{([^}]*)\}")
_BIB_RE = re.compile(r"\\(?:bibliography|addbibresource)\s*\{([^}]*)\}")
_AUX_CITATION_RE = re.compile(r"\\citation\{([^}]*)\}")


def _split_keys(payload: str) -> List[str]:
    return [k.strip() for k in payload.split(",") if k.strip()]


def find_tex_files(root: Path) -> List[Path]:
    root = Path(root)
    if root.is_file():
        return [root]
    # Skip build/backup dirs so we read the live sources, not artifacts.
    skip = {"logs", "export", "_minted", ".git"}
    out = []
    for p in sorted(root.rglob("*.tex")):
        if any(part in skip for part in p.parts):
            continue
        if p.name.endswith("_diff.tex"):
            continue
        out.append(p)
    return out


def extract_cited_keys(root: Path) -> Set[str]:
    """Union of \\cite keys across the manuscript's .tex files."""
    keys: Set[str] = set()
    for tex in find_tex_files(Path(root)):
        try:
            text = tex.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in _CITE_RE.finditer(text):
            keys.update(_split_keys(m.group(1)))
    return keys


def extract_cited_keys_from_aux(aux_path: Path) -> Set[str]:
    keys: Set[str] = set()
    text = Path(aux_path).read_text(encoding="utf-8", errors="replace")
    for m in _AUX_CITATION_RE.finditer(text):
        keys.update(_split_keys(m.group(1)))
    return keys


def resolve_compiled_bib(root: Path) -> Optional[Path]:
    """Find the .bib the manuscript compiles against, following symlinks.

    Reads ``\\bibliography{}``/``\\addbibresource{}`` from the .tex sources,
    resolves the referenced path relative to the declaring file, appends
    ``.bib`` if needed, and returns its ``realpath``.
    """
    root = Path(root)
    for tex in find_tex_files(root):
        try:
            text = tex.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = _BIB_RE.search(text)
        if not m:
            continue
        # \bibliography may list several comma-separated bases; take the first
        # that resolves to an existing file.
        base_dir = tex.parent
        search_root = root if root.is_dir() else root.parent
        for ref in _split_keys(m.group(1)):
            for cand in (base_dir / ref, search_root / ref):
                p = cand if cand.suffix == ".bib" else cand.with_suffix(".bib")
                if p.exists():
                    return p.resolve()
    return None


# EOF
