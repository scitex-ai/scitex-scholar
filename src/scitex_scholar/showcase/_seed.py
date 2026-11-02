"""Explicit additive admission into Scholar's primary-file library."""

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from ._catalog import catalog, identifier, identity, paper_payload
from ._files import ShowcaseConflict, checked, entries, locked, publish_json, read_json


def _targets(library_root, project):
    root = Path(library_root)
    if not root.is_absolute() or root.is_symlink() or root.resolve() != root:
        raise ShowcaseConflict("Supply a canonical, authorized absolute library root")
    if not isinstance(project, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", project
    ):
        raise ShowcaseConflict("Supply a project slug, never a path")
    from scitex_scholar._library_names import RESERVED_LIBRARY_DIRS

    if project in RESERVED_LIBRARY_DIRS:
        raise ShowcaseConflict("Project slug is reserved for library storage")
    checked(root, root, directory=True)
    master = checked(root / "MASTER", root, directory=True)
    pdir = checked(root / project, root, directory=True)
    return root, master, pdir


def _existing(master, root):
    known, titles = {}, {}
    for directory in entries(master):
        checked(directory, root, directory=True)
        path = checked(directory / "metadata.json", root)
        if not path.exists():
            continue
        data = read_json(path)
        meta = data.get("metadata")
        if not isinstance(meta, dict) or any(
            not isinstance(meta.get(k, {}), dict) for k in ["id", "basic"]
        ):
            raise ShowcaseConflict(
                "Existing primary metadata has an incompatible schema"
            )
        doi = meta.get("id", {}).get("doi")
        title = meta.get("basic", {}).get("title")
        if any(x is not None and not isinstance(x, str) for x in [doi, title]):
            raise ShowcaseConflict("Existing bibliographic identities must be strings")
        key = identity(meta)
        if not key[1]:
            # Unresolved user records have no identity matching this catalog.
            continue
        if key in known:
            raise ShowcaseConflict(
                "Existing library has ambiguous duplicate identities"
            )
        known[key] = directory.name
        if not doi and title:
            titles[" ".join(title.split()).casefold()] = directory.name
    return known, titles


def _membership(pdir, paper_id, root):
    expected = root / "MASTER" / paper_id
    for item in entries(pdir):
        if item.is_symlink():
            # Match standard project links lexically; never follow an unrelated
            # user's link onto an external mount while planning this example.
            destination = Path(os.path.abspath(item.parent / item.readlink()))
            if destination == expected:
                return True
    destination = pdir / paper_id
    if destination.exists() or destination.is_symlink():
        raise ShowcaseConflict("Existing project entry must be preserved")
    return False


def _plan(root, master, pdir):
    data = catalog()
    known, titles = _existing(master, root)
    rows = []
    for ref in data["references"]:
        meta = paper_payload(ref, "", pdir.name)["metadata"]
        paper_id = known.get(identity(meta)) or titles.get(
            identity({"basic": meta["basic"]})[1]
        )
        existing = paper_id is not None
        paper_id = paper_id or identifier(ref)
        target = checked(master / paper_id, root, directory=True)
        if not existing and target.exists():
            raise ShowcaseConflict("A generated example ID collides with existing data")
        rows.append(
            {
                "ref": ref,
                "paper_id": paper_id,
                "existing": existing,
                "filed": _membership(pdir, paper_id, root),
            }
        )
    digest = hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    manifest = {
        "schema": "scitex-scholar.showcase-admission/v1",
        "example": "mnist",
        "catalog_sha256": digest,
        "project": pdir.name,
        "papers": [
            {
                "key": r["ref"]["key"],
                "library_id": r["paper_id"],
                "primary_sources": r["ref"]["sources"],
            }
            for r in rows
        ],
        "scope": data["scope"],
        "artifacts": data["artifacts"],
    }
    path = checked(pdir / ".mnist-showcase-v1.json", root)
    if path.exists() and read_json(path) != manifest:
        raise ShowcaseConflict("Existing example provenance must be preserved")
    return rows, manifest


def _publish_paper(root, master, row, project):
    from scitex_scholar.core.Paper import Paper
    from scitex_scholar.storage.PaperIO import PaperIO

    paper = Paper.from_dict(paper_payload(row["ref"], row["paper_id"], project))
    # Canonical serialization in a private stage; no index/store constructor.
    with tempfile.TemporaryDirectory(prefix=".mnist-stage-", dir=master) as stage:
        source = PaperIO(paper, base_dir=Path(stage)).save_metadata()
        target = checked(master / row["paper_id"], root, directory=True)
        target.mkdir(exist_ok=False)
        try:
            os.link(source, target / "metadata.json")
        except BaseException:
            # Remove only the empty directory this call just created.
            try:
                target.rmdir()
            except OSError:
                pass
            raise


def seed_mnist_library(library_root, *, project, dry_run=True):
    """Plan or explicitly admit four real MNIST references without replacement.

    Parameters
    ----------
    library_root : pathlib.Path or str
        Canonical absolute user library root authorized by the caller. Mounted
        hosts must resolve their authenticated user-home capability first.
    project : str
        Host-authorized project slug. Owner/path identifiers are refused.
    dry_run : bool, default True
        True only reads packaged data and existing primary files. False adds
        missing metadata and project symlinks, preserving existing record bytes.

    Returns
    -------
    dict
        Counts and opaque paper IDs; no server paths or user metadata bodies.

    Raises
    ------
    ValueError
        The target, project, existing metadata or provenance is incompatible.
    TimeoutError
        Another explicit example job retains the library lock.
    OSError
        Filesystem publication failed; valid earlier additions are preserved.

    Notes
    -----
    This POSIX-only explicit job uses flock, symlinks and no-overwrite hardlinks.
    It never fetches papers, opens the derived PostgreSQL index, executes models,
    or modifies a project bibliography. New records carry canonical Paper data;
    existing records retain their bytes and gain only missing filesystem links.
    Each publication is atomic, not the whole batch: interrupted jobs can leave
    valid additions. Rerun to finish; incomplete or conflicting entries require
    operator review. No rollback deletes user data.
    """
    if not isinstance(dry_run, bool):
        raise ValueError("dry_run must be a boolean")
    root, master, pdir = _targets(library_root, project)
    rows, manifest = _plan(root, master, pdir)

    def report(items):
        return {
            "example": "mnist",
            "dry_run": dry_run,
            "references": len(items),
            "new_papers": sum(not r["existing"] for r in items),
            "new_memberships": sum(not r["filed"] for r in items),
            "paper_ids": [r["paper_id"] for r in items],
        }

    if dry_run:
        return report(rows)
    root.mkdir(parents=True, exist_ok=True)
    with locked(root):
        rows, manifest = _plan(root, master, pdir)
        master.mkdir(exist_ok=True)
        pdir.mkdir(exist_ok=True)
        for row in rows:
            if not row["existing"]:
                _publish_paper(root, master, row, project)
            if not row["filed"]:
                os.symlink(
                    Path("..") / "MASTER" / row["paper_id"], pdir / row["paper_id"]
                )
        path = pdir / ".mnist-showcase-v1.json"
        if not path.exists():
            publish_json(path, manifest, root)
        return report(rows)
