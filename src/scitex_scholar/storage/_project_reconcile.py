#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconcile `container.projects` in MASTER metadata against filesystem symlinks.

The library uses two parallel sources of truth for project membership:

1. Filesystem symlinks: ``library/<project>/<readable_name> -> ../MASTER/<id>``
2. Metadata field:      ``MASTER/<id>/metadata.json :: container.projects``

These can drift (e.g. ``_ensure_project_symlink`` historically wrote (1) but
not (2)). The functions here treat (1) as the source of truth and rewrite
(2) to match.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set


@dataclass
class ReconcileReport:
    scanned_master_entries: int = 0
    projects_seen: List[str] = field(default_factory=list)
    updated: List[Dict[str, object]] = field(default_factory=list)
    unchanged: int = 0
    missing_metadata: List[str] = field(default_factory=list)
    broken_symlinks: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "scanned_master_entries": self.scanned_master_entries,
            "projects_seen": self.projects_seen,
            "updated_count": len(self.updated),
            "updated": self.updated,
            "unchanged": self.unchanged,
            "missing_metadata": self.missing_metadata,
            "broken_symlinks": self.broken_symlinks,
        }


def _project_dirs(library_root: Path) -> List[Path]:
    skip = {"MASTER", "MASTER_quarantine", "downloads"}
    return [
        p
        for p in sorted(library_root.iterdir())
        if p.is_dir() and not p.is_symlink() and p.name not in skip
    ]


def build_project_membership(
    library_root: Path,
) -> tuple[Dict[str, Set[str]], List[str]]:
    """Walk symlinks and return ``{master_paper_id: {project, ...}}``.

    Also returns a list of broken symlink paths (for reporting).
    """
    membership: Dict[str, Set[str]] = defaultdict(set)
    broken: List[str] = []

    for proj_dir in _project_dirs(library_root):
        for entry in proj_dir.iterdir():
            if not entry.is_symlink():
                continue
            try:
                target = entry.resolve(strict=False)
            except OSError:
                broken.append(str(entry.relative_to(library_root)))
                continue
            if not target.exists():
                broken.append(str(entry.relative_to(library_root)))
                continue
            # Expect target inside MASTER/
            try:
                rel = target.relative_to(library_root / "MASTER")
            except ValueError:
                continue
            paper_id = rel.parts[0]
            membership[paper_id].add(proj_dir.name)

    return membership, broken


def reconcile_projects(library_root: Path, *, dry_run: bool = False) -> ReconcileReport:
    """Sync MASTER ``container.projects`` to match filesystem symlinks.

    Args:
        library_root: ``~/.scitex/scholar/library``
        dry_run: If True, do not write metadata; only report what would change.
    """
    library_root = Path(library_root).resolve()
    master = library_root / "MASTER"
    report = ReconcileReport()

    membership, broken = build_project_membership(library_root)
    report.broken_symlinks = broken
    report.projects_seen = sorted({p for ps in membership.values() for p in ps})

    if not master.is_dir():
        return report

    for entry_dir in sorted(master.iterdir()):
        if not entry_dir.is_dir():
            continue
        report.scanned_master_entries += 1
        meta_file = entry_dir / "metadata.json"
        if not meta_file.exists():
            report.missing_metadata.append(entry_dir.name)
            continue

        try:
            data = json.loads(meta_file.read_text())
        except (OSError, json.JSONDecodeError):
            report.missing_metadata.append(entry_dir.name)
            continue

        container = data.setdefault("container", {})
        old = sorted(container.get("projects") or [])
        new = sorted(membership.get(entry_dir.name, set()))

        if old == new:
            report.unchanged += 1
            continue

        report.updated.append({"paper_id": entry_dir.name, "from": old, "to": new})

        if dry_run:
            continue

        container["projects"] = new
        meta_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    return report


def add_project_to_master(library_root: Path, paper_id: str, project: str) -> bool:
    """Append ``project`` to ``container.projects`` of ``MASTER/<paper_id>``.

    Returns True if the metadata was modified, False if already present
    or the metadata file is missing/unreadable.
    """
    meta_file = Path(library_root) / "MASTER" / paper_id / "metadata.json"
    if not meta_file.exists():
        return False
    try:
        data = json.loads(meta_file.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    container = data.setdefault("container", {})
    projects = list(container.get("projects") or [])
    if project in projects:
        return False
    projects.append(project)
    container["projects"] = sorted(projects)
    meta_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return True
