#!/usr/bin/env python3
"""Read-only library auditor — reports anomalies without raising.

Addresses https://github.com/scitex-ai/scitex-scholar/issues/12:
`db build` raises on duplicate DOIs (correctly), but leaves the user
with no visibility into *all* the problems. `audit()` walks MASTER and
returns a structured report so the user can see everything to fix
before re-running `build`.

Pure filesystem read. No DB writes. No mutations.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AuditReport:
    """Structured audit result."""

    entries_scanned: int = 0
    duplicate_dois: dict[str, list[dict]] = field(default_factory=dict)
    unparseable: list[dict] = field(default_factory=list)
    missing_doi: list[str] = field(default_factory=list)
    missing_pdf: list[dict] = field(default_factory=list)
    orphaned_symlinks: list[dict] = field(default_factory=list)

    @property
    def n_issues(self) -> int:
        return (
            sum(len(v) for v in self.duplicate_dois.values())
            + len(self.unparseable)
            + len(self.missing_pdf)
            + len(self.orphaned_symlinks)
        )

    @property
    def has_issues(self) -> bool:
        return self.n_issues > 0 or bool(self.duplicate_dois)

    def to_dict(self) -> dict:
        return {
            "entries_scanned": self.entries_scanned,
            "duplicate_dois": self.duplicate_dois,
            "unparseable": self.unparseable,
            "missing_doi": self.missing_doi,
            "missing_pdf": self.missing_pdf,
            "orphaned_symlinks": self.orphaned_symlinks,
            "n_issues": self.n_issues,
            "has_issues": self.has_issues,
        }


def audit(library_root: Path) -> AuditReport:
    """Walk `<library_root>/MASTER` and `<library_root>/<project>/*` symlinks,
    reporting anomalies. Never raises for data issues; only raises if
    `library_root/MASTER` doesn't exist.
    """
    library_root = Path(library_root).resolve()
    master = library_root / "MASTER"
    if not master.is_dir():
        raise FileNotFoundError(master)

    report = AuditReport()
    by_doi: dict[str, list[dict]] = defaultdict(list)

    for meta_file in sorted(master.glob("*/metadata.json")):
        report.entries_scanned += 1
        paper_id = meta_file.parent.name
        try:
            md = json.loads(meta_file.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            report.unparseable.append(
                {"paper_id": paper_id, "path": str(meta_file), "error": str(exc)}
            )
            continue

        m = md.get("metadata", {}) or {}
        id_ = m.get("id", {}) or {}
        path = m.get("path", {}) or {}
        doi = id_.get("doi")

        if not doi:
            report.missing_doi.append(paper_id)
        else:
            by_doi[doi.lower()].append(
                {
                    "paper_id": paper_id,
                    "mtime": meta_file.stat().st_mtime,
                    "title": (m.get("basic", {}) or {}).get("title"),
                }
            )

        # PDF presence
        pdfs = path.get("pdfs") or []
        if pdfs:
            missing = [p for p in pdfs if not (meta_file.parent / p).exists()]
            if missing:
                report.missing_pdf.append({"paper_id": paper_id, "missing": missing})
        else:
            # No PDFs listed and no *.pdf in the entry directory
            if not any(meta_file.parent.glob("*.pdf")):
                report.missing_pdf.append(
                    {"paper_id": paper_id, "missing": ["(no PDF referenced)"]}
                )

    for doi, entries in by_doi.items():
        if len(entries) > 1:
            report.duplicate_dois[doi] = entries

    # Orphaned decorated symlinks under <library_root>/<project>/
    for project_dir in library_root.iterdir():
        if not project_dir.is_dir() or project_dir.name == "MASTER":
            continue
        if project_dir.name == "downloads":
            continue
        for entry in project_dir.rglob("*"):
            if entry.is_symlink() and not entry.exists():
                try:
                    target = entry.readlink()
                except OSError:
                    target = None
                report.orphaned_symlinks.append(
                    {
                        "link": str(entry.relative_to(library_root)),
                        "target": str(target) if target else None,
                    }
                )

    return report


def format_report(report: AuditReport) -> str:
    """Human-readable text format, matching the shape of `db build`'s error."""
    lines: list[str] = []
    lines.append(f"Scanned {report.entries_scanned} entries in MASTER.")
    lines.append("")

    if report.duplicate_dois:
        lines.append(f"Duplicate DOIs ({len(report.duplicate_dois)}):")
        for doi, entries in sorted(report.duplicate_dois.items()):
            ids = ", ".join(e["paper_id"] for e in entries)
            lines.append(f"  {doi}: {ids}")
            for e in entries:
                title = e.get("title") or "(untitled)"
                lines.append(f"    - {e['paper_id']}: {title[:80]}")
        lines.append("")

    if report.unparseable:
        lines.append(f"Unparseable metadata.json ({len(report.unparseable)}):")
        for u in report.unparseable:
            lines.append(f"  {u['paper_id']}: {u['error']}")
        lines.append("")

    if report.missing_pdf:
        lines.append(f"Entries without reachable PDF ({len(report.missing_pdf)}):")
        for m in report.missing_pdf[:10]:
            lines.append(f"  {m['paper_id']}: {m['missing']}")
        if len(report.missing_pdf) > 10:
            lines.append(f"  … and {len(report.missing_pdf) - 10} more")
        lines.append("")

    if report.missing_doi:
        lines.append(
            f"Entries without DOI: {len(report.missing_doi)} (not a corruption)"
        )
        lines.append("")

    if report.orphaned_symlinks:
        lines.append(f"Orphaned decorated symlinks ({len(report.orphaned_symlinks)}):")
        for o in report.orphaned_symlinks[:10]:
            lines.append(f"  {o['link']} → {o['target']}")
        if len(report.orphaned_symlinks) > 10:
            lines.append(f"  … and {len(report.orphaned_symlinks) - 10} more")
        lines.append("")

    if not report.has_issues:
        lines.append("No issues found — library is consistent.")

    return "\n".join(lines).rstrip()
