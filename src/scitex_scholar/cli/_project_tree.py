#!/usr/bin/env python3
"""`scitex scholar link-project-tree` — symlink a project's
`.scitex/scholar/library` to `~/.scitex/scholar/library/`.

See docs/adr/0100-project-tree-link.md.
"""

from __future__ import annotations

import os
from pathlib import Path

import scitex_logging as logging

logger = logging.getLogger(__name__)


def _home_library(library_root: Path | None = None) -> Path:
    """Home ``scholar/library`` dir.

    Explicit ``library_root`` wins (lets multi-user hosts such as
    SciTeX Hub address a unix user's library without switching UID).
    Otherwise ``$SCITEX_DIR/scholar/library`` when ``SCITEX_DIR`` is set,
    else the classic ``~/.scitex/scholar/library``.
    """
    if library_root is not None:
        return Path(library_root).expanduser().resolve()
    scitex_dir = os.getenv("SCITEX_DIR")
    if scitex_dir:
        return (Path(scitex_dir).expanduser() / "scholar" / "library").resolve()
    return Path("~/.scitex/scholar/library").expanduser().resolve()


def link_project_tree(
    project_dir: Path, force: bool = False, library_root: Path | None = None
) -> Path:
    """Create `<project_dir>/.scitex/scholar/library → <library>/`.

    ``library`` defaults to the home library (``$SCITEX_DIR``-aware).
    Pass ``library_root`` to target another unix user's library.

    Idempotent. If a different symlink or a real directory already
    occupies the path, pass ``force=True`` to replace it.

    Returns the link path.
    """
    project_dir = Path(project_dir).resolve()
    if not project_dir.exists():
        raise FileNotFoundError(project_dir)

    target = _home_library(library_root)
    link_parent = project_dir / ".scitex" / "scholar"
    link_parent.mkdir(parents=True, exist_ok=True)
    link = link_parent / "library"

    if link.is_symlink():
        if link.readlink() == target:
            logger.info(f"Link already points to {target}: {link}")
            return link
        if not force:
            raise FileExistsError(
                f"{link} is a symlink to {link.readlink()}; pass --force to replace"
            )
        link.unlink()
    elif link.exists():
        if not force:
            raise FileExistsError(
                f"{link} exists and is not a symlink; pass --force to replace"
            )
        import shutil

        shutil.rmtree(link)

    link.symlink_to(target)
    logger.success(f"Linked {link} → {target}")
    return link


def register_subparser(subparsers) -> None:
    p = subparsers.add_parser(
        "link-project-tree",
        help="Symlink a project's .scitex/scholar/library to the home library",
        description=(
            "Create <dir>/.scitex/scholar/library → ~/.scitex/scholar/library/. "
            "Idempotent. Use --force to replace a differing target."
        ),
    )
    p.add_argument("project_dir", type=Path, help="Project root directory")
    p.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing symlink or directory at the link path",
    )


def run(args) -> int:
    try:
        link_project_tree(args.project_dir, force=args.force)
        return 0
    except (FileNotFoundError, FileExistsError) as exc:
        logger.error(str(exc))
        return 1
