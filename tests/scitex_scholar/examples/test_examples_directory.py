"""Mirror placeholder for ``src/scitex_scholar/examples/``.

``src/scitex_scholar/examples/`` is a directory of standalone runnable
scripts (filenames start with digits like ``00_config.py``), NOT a
Python package — there's no ``__init__.py`` and individual files
cannot be imported via dotted notation (``scitex_scholar.examples.00_config``
is ``SyntaxError: invalid decimal literal``).

The earlier auto-generated mirror ``test_00_config.py`` tried to
``importlib.import_module`` such a name and worked only because it
silently swallowed every exception. The honest replacement: assert
the directory exists with at least one ``*.py`` script. The actual
"each script runs cleanly" smoke is covered by
``tests/examples/test_examples_smoke.py`` (parametrized subprocess
per script). This file's job is just to satisfy the PS-202
src↔tests-mirror-directory audit rule.
"""

from __future__ import annotations

from pathlib import Path


_EXAMPLES_DIR = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "scitex_scholar"
    / "examples"
)


def test_examples_source_directory_contains_python_scripts():
    # Arrange
    # Act
    scripts = sorted(_EXAMPLES_DIR.glob("*.py"))
    # Assert
    assert len(scripts) > 0, f"no *.py example scripts under {_EXAMPLES_DIR}"
