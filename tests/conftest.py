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


# ---------------------------------------------------------------------------
# THE PACKAGE UNDER TEST MUST BE THIS CHECKOUT. Fail the SESSION otherwise.
#
# `scitex_scholar` lives under src/, and pytest only prepends the ROOTDIR --
# which holds no importable package. So without `pythonpath = ["src"]`
# (pyproject, [tool.pytest.ini_options]) a bare `pytest` fell through to
# whatever the ambient interpreter had. In this agent container that is a REAL,
# non-editable wheel in /opt/venv-sac/lib/python3.12/site-packages.
#
# MEASURED 2026-08-23, from inside a worktree, relative paths, the careful way:
#     imported  /opt/venv-sac/.../scitex_scholar/__init__.py   1.7.1, 6 routes
#     the tree  .worktrees/<branch>/src/scitex_scholar/...     1.9.0, 7 routes
# I reported "53 passed" as verification of the 1.9.0 release on a run of this
# shape and cannot now establish which tree it imported. The release stands on
# CI; my local number was worth nothing and I did not know it.
#
# THE DIRECTION THAT LOOKS FINE IS THE DANGEROUS ONE. Mine went RED only
# because the installed wheel was OLDER. Had it been equal or newer, the suite
# would have gone GREEN against code the branch does not contain -- and a
# change that merely EDITS existing files leaves no tell at all. (sac hit
# exactly that: a worker got 50/50 PASSED on a package without their PR, caught
# only because their branch ADDED a file and collection raised ImportError.)
#
# CI IS STRUCTURALLY BLIND TO THIS and always was: it installs the branch into
# a fresh environment, so it always resolves the right code. The one gate that
# would catch it cannot. So the guard runs where the bug lives -- the developer
# box -- not in CI.
#
# It compares the MODULE PATH, never __version__. A version string is a fossil:
# the editable install in this repo's own .venv reports 1.5.1 while importing
# 1.9.0 source, and a stale .dist-info reports a number matching nothing on
# disk. Paths cannot lie about where the code came from.
#
# Adopted from scitex-agent-container's pyproject/conftest pair rather than
# reinvented; they hit this first and their reasoning is in their tree.
# ---------------------------------------------------------------------------
def pytest_sessionstart(session) -> None:
    """Abort the run if `import scitex_scholar` is not this checkout."""
    import scitex_scholar

    expected_src = (_PROJECT_ROOT / "src").resolve()
    imported = Path(getattr(scitex_scholar, "__file__", "") or "").resolve()

    if expected_src in imported.parents:
        return

    raise RuntimeError(
        "\n=================== WRONG PACKAGE UNDER TEST ===================\n"
        "`import scitex_scholar` did not resolve to this checkout, so this\n"
        "run would test code you did not write.\n"
        f"\n  imported from : {imported}\n"
        f"  expected under: {expected_src}\n"
        '\nFix: `pythonpath = ["src"]` under [tool.pytest.ini_options].\n'
        "Ad hoc: PYTHONPATH=$PWD/src pytest ...\n"
        "===============================================================\n"
    )


# EOF
