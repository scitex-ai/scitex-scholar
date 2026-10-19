#!/usr/bin/env python3
"""Per-paper library annotations sidecar (old-direct unification slice 4a).

Hub's Library details panel (reading status, importance stars, tags,
personal notes) is model-backed in hub. The leaf keeps the same user data
in ``MASTER/<library_id>/annotations.json`` -- a sidecar NEXT TO
metadata.json, never inside it, so enrichment rewrites of metadata.json
can never clobber user annotations (same sidecar precedent as the
verify-cites clew sidecar). Reads of a missing/corrupt sidecar degrade to
``{}``; writes merge partial updates and stamp ``updated_at``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

#: Reading statuses hub's details panel offers (hub values verbatim, so a
#: future hub import maps 1:1).
READING_STATUSES = ("to_read", "reading", "read", "referenced", "favorite")

#: Importance stars: 0 clears the rating, 1-5 set it.
MIN_IMPORTANCE = 0
MAX_IMPORTANCE = 5

#: Tags: at most this many, each this long. A tag wall is write
#: amplification per paper (one atomic rewrite each), so the caps stay low.
MAX_TAGS = 50
MAX_TAG_CHARS = 100

#: Personal notes cap: a paper note is prose, not a manuscript; 64k is far
#: past legitimate use and bounds the atomic rewrite per keystroke-save.
MAX_NOTES_CHARS = 65536

SIDECAR_NAME = "annotations.json"


def validate_annotations(data: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Validate a caller-supplied annotations doc (partial updates welcome).

    Returns (clean_dict, None) or (None, fixed_error_message). Unknown keys
    are refused -- the sidecar has a closed schema so a typo cannot park
    dead data no reader will ever show. The raw values are never echoed in
    the error (untrusted-input rule).
    """
    if not isinstance(data, dict):
        return None, "annotations must be an object"
    clean: Dict[str, Any] = {}
    if "reading_status" in data:
        status = data["reading_status"]
        if status is not None:
            if not isinstance(status, str) or status not in READING_STATUSES:
                return None, (
                    "reading_status must be one of: " + ", ".join(READING_STATUSES)
                )
            clean["reading_status"] = status
    if "importance" in data:
        importance = data["importance"]
        if importance is not None:
            if (
                isinstance(importance, bool)
                or not isinstance(importance, int)
                or not MIN_IMPORTANCE <= importance <= MAX_IMPORTANCE
            ):
                return None, (
                    f"importance must be an integer {MIN_IMPORTANCE}-{MAX_IMPORTANCE}"
                )
            clean["importance"] = importance
    if "tags" in data:
        tags = data["tags"]
        if tags is not None:
            if not isinstance(tags, list) or any(
                not isinstance(t, str) for t in tags
            ):
                return None, "tags must be a list of strings"
            stripped = [t.strip() for t in tags]
            if any(not t or len(t) > MAX_TAG_CHARS for t in stripped):
                return None, f"each tag must be 1-{MAX_TAG_CHARS} characters"
            if len(stripped) > MAX_TAGS:
                return None, f"at most {MAX_TAGS} tags"
            # Dedupe, order preserved.
            clean["tags"] = list(dict.fromkeys(stripped))
    if "notes" in data:
        notes = data["notes"]
        if notes is not None:
            if not isinstance(notes, str):
                return None, "notes must be a string"
            if len(notes) > MAX_NOTES_CHARS:
                return None, f"notes must be at most {MAX_NOTES_CHARS} characters"
            clean["notes"] = notes
    for key in data:
        if key not in ("reading_status", "importance", "tags", "notes"):
            return None, "unknown annotation field"
    return clean, None


def sidecar_path(paper_dir: Path) -> Path:
    """The annotations sidecar inside one MASTER/<id>/ paper directory."""
    return Path(paper_dir) / SIDECAR_NAME


def read_annotations(paper_dir: Path) -> Dict[str, Any]:
    """Read the sidecar; missing/corrupt degrades to {} (never raises)."""
    try:
        data = json.loads(sidecar_path(paper_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    # updated_at is system-managed (stamped on write); it is not a user
    # field, so it is stripped before validation rather than refused.
    data = {k: v for k, v in data.items() if k != "updated_at"}
    clean, error = validate_annotations(data)
    if error is not None or clean is None:
        return {}
    return clean


def write_annotations(paper_dir: Path, patch: Dict[str, Any]) -> Dict[str, Any]:
    """Merge a validated patch into the sidecar and return the stored doc.

    ``patch`` must already be ``validate_annotations``-clean. The merge is
    read-modify-write with an atomic replace, the same durability shape as
    the metadata writes (``storage.PaperIO._atomic_write_json``).
    """
    paper_dir = Path(paper_dir)
    merged = read_annotations(paper_dir)
    merged.update(patch)
    merged["updated_at"] = datetime.now(timezone.utc).isoformat()
    tmp_path = paper_dir / (SIDECAR_NAME + ".tmp")
    tmp_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(sidecar_path(paper_dir))
    return merged


# EOF
