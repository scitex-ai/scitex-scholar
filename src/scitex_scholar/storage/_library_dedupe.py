#!/usr/bin/env python3
"""Resolve duplicate-DOI entries in the primary store.

Strategy:
1. Detect all duplicate DOIs (case-insensitive).
2. For each collision group, pick a **winner** by a scored rubric:
   - +10 if the entry has a reachable PDF (or any *.pdf in the entry dir)
   - +1 per populated `basic.*` field (title, authors, abstract, year)
   - +1 per populated `id.*` field beyond the shared DOI
     (arxiv_id, pmid, corpus_id, semantic_id, ...)
   - +min(5, log(1 + citation_count))
   - +mtime / 1e12     (secondary tiebreaker: prefer newer on ties)
3. Move the **losers** to `<library_root>/MASTER_quarantine/<paper_id>/`.
   Reversible by moving them back. No deletion by default.

`--apply` executes; default is dry-run so the user can preview the plan.
`--hard-delete` is available but off-by-default — only the user opts in.

This sits next to `audit` (read-only) and `build` (strict-raise): the user's
flow becomes `audit` → `dedupe --dry-run` → review → `dedupe --apply` → `build`.
"""

from __future__ import annotations

import json
import math
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────────────────────────────────

BASIC_FIELDS = ("title", "authors", "abstract", "year", "keywords")
ID_FIELDS = (
    "arxiv_id",
    "pmid",
    "corpus_id",
    "semantic_id",
    "ieee_id",
    "scholar_id",
)


def _has_pdf(entry_dir: Path, metadata: dict) -> bool:
    pdfs = (metadata.get("path") or {}).get("pdfs") or []
    for p in pdfs:
        if (entry_dir / p).exists():
            return True
    return any(entry_dir.glob("*.pdf"))


def _score_entry(entry_dir: Path, metadata: dict) -> tuple[float, dict]:
    """Return (score, breakdown_dict) for a single candidate."""
    m = metadata.get("metadata") or {}
    basic = m.get("basic") or {}
    id_ = m.get("id") or {}
    citation = m.get("citation_count") or {}

    score = 0.0
    breakdown: dict = {}

    if _has_pdf(entry_dir, m):
        score += 10.0
        breakdown["pdf"] = 10.0

    populated_basic = sum(1 for k in BASIC_FIELDS if basic.get(k))
    score += populated_basic
    breakdown["basic_fields"] = populated_basic

    populated_ids = sum(1 for k in ID_FIELDS if id_.get(k))
    score += populated_ids
    breakdown["other_ids"] = populated_ids

    cites = citation.get("total") or 0
    if cites:
        cite_pts = min(5.0, math.log(1 + cites))
        score += cite_pts
        breakdown["citation_count"] = {"total": cites, "points": round(cite_pts, 2)}

    try:
        mtime = (entry_dir / "metadata.json").stat().st_mtime
        score += mtime / 1e12
    except OSError:
        mtime = 0.0
    breakdown["mtime"] = mtime

    return score, breakdown


# ─────────────────────────────────────────────────────────────────────────
# Plan
# ─────────────────────────────────────────────────────────────────────────


@dataclass
class Decision:
    doi: str
    winner_paper_id: str
    winner_score: float
    losers: list[dict] = field(default_factory=list)  # [{paper_id, score, breakdown}]
    winner_breakdown: dict = field(default_factory=dict)


@dataclass
class DedupePlan:
    decisions: list[Decision] = field(default_factory=list)
    quarantined_count: int = 0
    dry_run: bool = True

    @property
    def loser_paper_ids(self) -> list[str]:
        return [lo["paper_id"] for d in self.decisions for lo in d.losers]


# ─────────────────────────────────────────────────────────────────────────
# Main algorithm
# ─────────────────────────────────────────────────────────────────────────


def plan_dedupe(library_root: Path) -> DedupePlan:
    """Compute a dedupe plan without touching the filesystem."""
    library_root = Path(library_root).resolve()
    master = library_root / "MASTER"
    if not master.is_dir():
        raise FileNotFoundError(master)

    by_doi: dict[str, list[tuple[str, Path, dict]]] = defaultdict(list)

    for meta_file in master.glob("*/metadata.json"):
        paper_id = meta_file.parent.name
        try:
            md = json.loads(meta_file.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        doi = ((md.get("metadata") or {}).get("id") or {}).get("doi")
        if not doi:
            continue
        by_doi[doi.lower()].append((paper_id, meta_file.parent, md))

    plan = DedupePlan(dry_run=True)
    for doi, entries in by_doi.items():
        if len(entries) < 2:
            continue
        scored = [
            (*_score_entry(entry_dir, md), paper_id, entry_dir)
            for (paper_id, entry_dir, md) in entries
        ]
        scored.sort(key=lambda t: t[0], reverse=True)
        winner_score, winner_br, winner_pid, _ = scored[0]
        losers = [
            {"paper_id": pid, "score": round(score, 2), "breakdown": br}
            for (score, br, pid, _) in scored[1:]
        ]
        plan.decisions.append(
            Decision(
                doi=doi,
                winner_paper_id=winner_pid,
                winner_score=round(winner_score, 2),
                winner_breakdown=winner_br,
                losers=losers,
            )
        )
    return plan


def apply_plan(library_root: Path, plan: DedupePlan, hard_delete: bool = False) -> int:
    """Execute the plan: move losers to quarantine (or delete if ``hard_delete``).

    Returns the count of entries moved/deleted. Idempotent — re-running on an
    already-deduped library does nothing.
    """
    library_root = Path(library_root).resolve()
    master = library_root / "MASTER"
    quarantine = library_root / "MASTER_quarantine"
    if not hard_delete:
        quarantine.mkdir(exist_ok=True)

    moved = 0
    for decision in plan.decisions:
        for loser in decision.losers:
            src = master / loser["paper_id"]
            if not src.exists():
                continue
            if hard_delete:
                shutil.rmtree(src)
            else:
                dst = quarantine / loser["paper_id"]
                if dst.exists():
                    # Already quarantined in a prior run — clean up old copy.
                    shutil.rmtree(dst)
                shutil.move(str(src), str(dst))
            moved += 1
    plan.quarantined_count = moved
    plan.dry_run = False
    return moved


# ─────────────────────────────────────────────────────────────────────────
# Human-readable formatting
# ─────────────────────────────────────────────────────────────────────────


def format_plan(plan: DedupePlan) -> str:
    if not plan.decisions:
        return "No duplicate DOIs found. Nothing to do."

    lines: list[str] = []
    mode = "DRY RUN" if plan.dry_run else "APPLIED"
    lines.append(f"[{mode}] {len(plan.decisions)} duplicate DOI group(s) found.")
    lines.append("")
    for d in plan.decisions:
        lines.append(f"DOI: {d.doi}")
        lines.append(
            f"  winner: {d.winner_paper_id}  (score {d.winner_score}, "
            f"pdf={'yes' if d.winner_breakdown.get('pdf') else 'no'}, "
            f"basic={d.winner_breakdown.get('basic_fields', 0)}, "
            f"ids={d.winner_breakdown.get('other_ids', 0)}, "
            f"cites={(d.winner_breakdown.get('citation_count') or {}).get('total', 0)})"
        )
        for lo in d.losers:
            br = lo["breakdown"]
            lines.append(
                f"  loser : {lo['paper_id']}  (score {lo['score']}, "
                f"pdf={'yes' if br.get('pdf') else 'no'}, "
                f"basic={br.get('basic_fields', 0)}, "
                f"ids={br.get('other_ids', 0)}, "
                f"cites={(br.get('citation_count') or {}).get('total', 0)})"
            )
        lines.append("")

    if plan.dry_run:
        lines.append("Re-run with --apply to quarantine the losers.")
    else:
        lines.append(f"Moved {plan.quarantined_count} entries to MASTER_quarantine/.")
    return "\n".join(lines).rstrip()
