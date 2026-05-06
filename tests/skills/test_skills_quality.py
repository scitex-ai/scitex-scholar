"""Enforces SciTeX skills quality checklist §1–§4.

Canonical: ~/.claude/skills/scitex/general/03_interface_04_skills/12_quality-checklist.md.

The helper that drives this test (``make_skill_quality_tests``) lives in
``scitex_dev``. Its module path moved between v0.11.1 (top-level
``scitex_dev._skills_quality_pytest``) and the post-0.11.1 refactor
(``scitex_dev._ecosystem._skills.skills_quality_pytest``). Probe both so the
test works against either.
"""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from scitex_dev._skills_quality_pytest import make_skill_quality_tests
except ImportError:
    try:
        from scitex_dev._ecosystem._skills.skills_quality_pytest import (
            make_skill_quality_tests,
        )
    except ImportError:  # pragma: no cover — depends on which scitex-dev is installed
        pytest.skip(
            "scitex-dev does not expose make_skill_quality_tests at any known "
            "path; skipping (install scitex-dev>=0.11.1 to enable).",
            allow_module_level=True,
        )

test_skills_quality = make_skill_quality_tests(
    package_root=Path(__file__).resolve().parents[1]
)
