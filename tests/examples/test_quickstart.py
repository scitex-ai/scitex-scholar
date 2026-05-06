#!/usr/bin/env python3
"""Compile-only smoke test for examples/quickstart.py."""

import py_compile
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "quickstart.py"


def test_quickstart_compiles():
    assert EXAMPLE.is_file(), f"missing example: {EXAMPLE}"
    py_compile.compile(str(EXAMPLE), doraise=True)


if __name__ == "__main__":
    test_quickstart_compiles()
