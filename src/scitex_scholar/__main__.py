"""``python -m scitex_scholar`` — thin shim that delegates to the Click app.

The Click CLI lives in :mod:`scitex_scholar._cli_main` so that:

- ``__main__.py`` stays the conventional entry-point hook for
  ``python -m scitex_scholar`` and the ``scitex-scholar`` console script;
- ``_cli_main.py`` is a regular module that can be unit-tested via
  ``tests/scitex_scholar/test__cli_main.py`` (mirrors per PS204).
"""

from ._cli_main import cli

if __name__ == "__main__":  # pragma: no cover — stdlib entry-point hook
    cli()
