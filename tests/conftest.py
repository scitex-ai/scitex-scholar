"""Pytest fixtures and rootdir marker for this package.

An empty conftest.py at tests/ is the canonical SciTeX
convention (audit-project PS208) — it pins the pytest
rootdir and gives downstream fixtures a home.

Also wires module-import-time subprocess-coverage support
(general/05_development_06_subprocess-coverage.md). Child
Python interpreters launched by tests (e.g. `python -m
<demo>` smoke tests, `jupyter nbconvert --execute`, or
pytest-xdist workers) must inherit a writable
`COVERAGE_PROCESS_START` + `COVERAGE_FILE`; otherwise their
`.coverage.*` shards land in a tmp dir that
`coverage combine` never sees and the Codecov number drops
silently.

`os.environ.setdefault` would be a no-op here because
pytest-cov has already set `COVERAGE_FILE` to a tmp path by
the time this conftest is imported — so force-set, not
setdefault.
"""

from __future__ import annotations

import os
import sysconfig
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Force-set (NOT setdefault — pytest-cov has already populated COVERAGE_FILE).
os.environ["COVERAGE_PROCESS_START"] = str(_PROJECT_ROOT / "pyproject.toml")
os.environ["COVERAGE_FILE"] = str(_PROJECT_ROOT / ".coverage")


def _ensure_subprocess_coverage_shim() -> None:
    """Drop an idempotent `.pth` file in site-packages that auto-starts
    coverage in every child Python interpreter via
    `coverage.process_startup()`.
    """
    purelib = Path(sysconfig.get_paths()["purelib"])
    pth = purelib / "_scitex_scholar_subprocess_coverage.pth"
    shim = (
        "import os, coverage\n"
        "if os.environ.get('COVERAGE_PROCESS_START'):\n"
        "    coverage.process_startup()\n"
    )
    try:
        if not pth.exists() or pth.read_text() != shim:
            pth.write_text(shim)
    except OSError:
        # site-packages may be read-only (e.g. system Python); silently
        # skip — local dev venvs are writable and that's where this matters.
        pass


_ensure_subprocess_coverage_shim()
