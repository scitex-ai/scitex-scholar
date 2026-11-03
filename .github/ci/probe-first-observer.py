"""Stdlib-first validation of Scholar's explicit owned store boundary."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def private_root():
    root = Path(os.environ["TMPDIR"])
    info = root.lstat()
    if (
        root.is_symlink()
        or root.resolve() != root
        or not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise RuntimeError("Scholar release temporary root is not exclusively owned")
    return root


def early_boundary():
    root = private_root()
    dsn = os.environ.get("SCITEX_STORE_DSN", "")
    target = urlsplit(dsn)
    query = parse_qs(target.query)
    if (
        target.scheme != "postgresql"
        or target.hostname is not None
        or target.password is not None
        or query != {"host": [str(root / "unavailable-store")]}
        or os.environ.get("SCITEX_CARDS_DB") != dsn
    ):
        raise RuntimeError(
            "Earliest observer does not have its explicit unavailable store"
        )
    allowed = {"PGPASSFILE"}
    if any(
        key.startswith(("APPTAINERENV_PG", "SINGULARITYENV_PG"))
        or (key.startswith("PG") and key not in allowed)
        for key in os.environ
    ):
        raise RuntimeError("Inherited PostgreSQL routing reached the earliest observer")
    password = Path(os.environ["PGPASSFILE"])
    s = password.lstat()
    if (
        password.parent != root
        or password.is_symlink()
        or not stat.S_ISREG(s.st_mode)
        or s.st_uid != os.getuid()
        or stat.S_IMODE(s.st_mode) != 0o600
        or s.st_size
    ):
        raise RuntimeError("Earliest observer password file is not owned and empty")
    if any(name == "scitex" or name.startswith("scitex_") for name in sys.modules):
        raise RuntimeError("A product was imported before the boundary proof")
    return {
        "earliest_stdlib_observer": True,
        "explicit_unavailable_store": True,
        "inherited_pg_absent": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--early", action="store_true")
    args = parser.parse_args()
    if not args.early:
        raise SystemExit("Only the explicit earliest-observer proof is supported")
    print(json.dumps(early_boundary()))


if __name__ == "__main__":
    main()
