"""Regression test: importing tests/conftest.py must not touch site-packages."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CONFTEST_PATH = Path(__file__).resolve().parents[1] / "conftest.py"

_CHILD_CODE = (
    "import os\n"
    "import runpy\n"
    "import site\n"
    f"conftest = {str(CONFTEST_PATH)!r}\n"
    "os.environ['COVERAGE_PROCESS_START'] = 'sentinel-process-start'\n"
    "os.environ['COVERAGE_FILE'] = 'sentinel-coverage-file'\n"
    "dirs = []\n"
    "try:\n"
    "    dirs.extend(site.getsitepackages())\n"
    "except Exception:\n"
    "    pass\n"
    "try:\n"
    "    usersite = site.getusersitepackages()\n"
    "    if isinstance(usersite, str):\n"
    "        dirs.append(usersite)\n"
    "except Exception:\n"
    "    pass\n"
    "before = {}\n"
    "for d in dirs:\n"
    "    try:\n"
    "        before[d] = set(os.listdir(d))\n"
    "    except OSError:\n"
    "        pass\n"
    "runpy.run_path(conftest, run_name='test_conftest_import')\n"
    "for d, names in before.items():\n"
    "    assert set(os.listdir(d)) == names, f'site-packages modified: {d}'\n"
    "for d in dirs:\n"
    "    try:\n"
    "        current = set(os.listdir(d))\n"
    "    except OSError:\n"
    "        continue\n"
    "    assert not (current - before.get(d, set())), f'new files in {d}'\n"
    "assert os.environ.get('COVERAGE_PROCESS_START') == 'sentinel-process-start'\n"
    "assert os.environ.get('COVERAGE_FILE') == 'sentinel-coverage-file'\n"
)


def test_conftest_leaves_site_packages_untouched():
    # Arrange
    cmd = [sys.executable, "-c", _CHILD_CODE]
    # Act
    proc = subprocess.run(cmd, capture_output=True, text=True)
    # Assert
    assert proc.returncode == 0, (
        f"child failed with exit {proc.returncode}\n"
        f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )
