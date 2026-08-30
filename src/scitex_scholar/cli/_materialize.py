#!/usr/bin/env python3
"""`scitex scholar materialize` / `dematerialize` — replace a
library-symlink with a bib-filtered real directory, and the inverse.

Generic: the command takes an arbitrary symlink path. It does not
assume or mention any particular downstream consumer. The symlink is
expected to point at a scholar library (either the home library or a
previously materialized subtree).

See docs/adr/0100-project-tree-link.md.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Iterable

import scitex_logging as logging

logger = logging.getLogger(__name__)


_DOI_KEY_RE = re.compile(r"doi\s*=\s*[{\"]([^}\"]+)", re.IGNORECASE)


def _iter_bib_dois(bib_path: Path) -> Iterable[str]:
    text = bib_path.read_text(errors="replace")
    for m in _DOI_KEY_RE.finditer(text):
        doi = m.group(1).strip().rstrip(",").strip()
        if doi:
            yield doi


def _resolve_paper_ids_by_doi(library_root: Path, dois: set[str]) -> dict[str, str]:
    """Return {doi: paper_id} for DOIs found in `<library_root>/MASTER/*/metadata.json`."""
    master = library_root / "MASTER"
    if not master.is_dir():
        return {}
    wanted = {d.lower() for d in dois}
    found: dict[str, str] = {}
    for meta_file in master.glob("*/metadata.json"):
        try:
            md = json.loads(meta_file.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        doi = (md.get("metadata", {}).get("id", {}) or {}).get("doi")
        if not doi:
            continue
        doi_lc = doi.lower()
        if doi_lc in wanted and doi_lc not in found:
            found[doi_lc] = meta_file.parent.name
    return found


def materialize(link_path: Path, bib_path: Path) -> tuple[int, Path]:
    """Replace symlink at ``link_path`` with a real directory containing
    ``MASTER/<paper_id>/`` subtrees for papers cited in ``bib_path``.

    Returns ``(n_copied, materialized_path)``.
    """
    link_path = Path(link_path)
    bib_path = Path(bib_path)
    if not link_path.is_symlink():
        raise FileExistsError(f"{link_path} is not a symlink")
    if not bib_path.is_file():
        raise FileNotFoundError(bib_path)

    source = link_path.resolve(strict=True)
    dois = set(_iter_bib_dois(bib_path))
    if not dois:
        logger.warning(f"No DOIs found in {bib_path}")

    mapping = _resolve_paper_ids_by_doi(source, dois)
    logger.info(f"Resolved {len(mapping)}/{len(dois)} DOIs to paper_ids from {source}")

    # Swap symlink → real directory
    staging = link_path.with_name(link_path.name + ".materializing")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    (staging / "MASTER").mkdir()

    for paper_id in mapping.values():
        src_entry = source / "MASTER" / paper_id
        dst_entry = staging / "MASTER" / paper_id
        shutil.copytree(src_entry, dst_entry, symlinks=False)

    link_path.unlink()
    staging.rename(link_path)
    logger.success(f"Materialized {len(mapping)} papers at {link_path}")
    return len(mapping), link_path


def dematerialize(materialized_path: Path, target: Path | None = None) -> Path:
    """Replace real directory at ``materialized_path`` with a symlink to
    ``target`` (defaults to ``~/.scitex/scholar/library``). The original
    real directory is deleted.
    """
    materialized_path = Path(materialized_path)
    if materialized_path.is_symlink():
        raise FileExistsError(f"{materialized_path} is already a symlink")
    if not materialized_path.is_dir():
        raise FileNotFoundError(materialized_path)

    if target is None:
        target = Path("~/.scitex/scholar/library").expanduser().resolve()
    else:
        target = Path(target).expanduser().resolve()

    shutil.rmtree(materialized_path)
    materialized_path.symlink_to(target)
    logger.success(f"Dematerialized {materialized_path} → {target}")
    return materialized_path


def register_subparsers(subparsers) -> None:
    m = subparsers.add_parser(
        "materialize",
        help="Replace a library-symlink with a bib-filtered real directory",
        description=(
            "Replace the symlink at <link_path> with a real directory "
            "containing MASTER/<paper_id>/ subtrees for each DOI cited "
            "in <bib>. Useful for shipping a self-contained project tarball."
        ),
    )
    m.add_argument("link_path", type=Path, help="Path to the library symlink")
    m.add_argument(
        "--bib",
        type=Path,
        required=True,
        help="BibTeX file whose DOIs select the papers to copy",
    )

    d = subparsers.add_parser(
        "dematerialize",
        help="Replace a materialized library directory with a symlink",
        description=(
            "Delete the real directory at <path> and replace it with a "
            "symlink to the user's home library (or --target)."
        ),
    )
    d.add_argument("path", type=Path, help="Path to the materialized directory")
    d.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Symlink target (default: ~/.scitex/scholar/library)",
    )


def run_materialize(args) -> int:
    try:
        n, _ = materialize(args.link_path, args.bib)
        return 0 if n > 0 else 1
    except (FileNotFoundError, FileExistsError) as exc:
        logger.error(str(exc))
        return 1


def run_dematerialize(args) -> int:
    try:
        dematerialize(args.path, target=args.target)
        return 0
    except (FileNotFoundError, FileExistsError) as exc:
        logger.error(str(exc))
        return 1
