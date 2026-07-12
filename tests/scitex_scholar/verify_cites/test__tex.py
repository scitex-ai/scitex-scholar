#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: tests/scitex_scholar/verify_cites/test__tex.py
# ----------------------------------------
"""Unit tests for scitex_scholar.verify_cites._tex."""
from __future__ import annotations

import os

import pytest

vc_tex = pytest.importorskip("scitex_scholar.verify_cites._tex")
from scitex_scholar.verify_cites._tex import (  # noqa: E402
    extract_cited_keys,
    resolve_compiled_bib,
)


def test_extract_cited_keys_handles_variants_and_comma_lists(tmp_path):
    # Arrange
    tex = tmp_path / "methods.tex"
    tex.write_text(
        r"Text \cite{Aaa2020, Bbb2021} more \citep[see][]{Ccc2019} "
        r"and \textcite{Ddd2018}.",
        encoding="utf-8",
    )
    # Act
    keys = extract_cited_keys(tmp_path)
    # Assert
    assert keys == {"Aaa2020", "Bbb2021", "Ccc2019", "Ddd2018"}


def test_extract_cited_keys_empty_dir_returns_empty_set(tmp_path):
    # Arrange
    # Act
    keys = extract_cited_keys(tmp_path)
    # Assert
    assert keys == set()


def test_resolve_compiled_bib_follows_symlink(tmp_path):
    # Arrange: mirror the neurovista trap — bib is a symlink to the real target.
    real = tmp_path / "shared" / "real.bib"
    real.parent.mkdir(parents=True)
    real.write_text("@article{X, title={t}}\n", encoding="utf-8")
    contents = tmp_path / "contents"
    contents.mkdir()
    os.symlink(real, contents / "bibliography.bib")
    (contents / "main.tex").write_text(
        r"\bibliography{bibliography}" + "\n", encoding="utf-8"
    )
    # Act
    resolved = resolve_compiled_bib(tmp_path)
    # Assert
    assert resolved == real.resolve()


def test_resolve_compiled_bib_returns_none_without_bibliography_command(tmp_path):
    # Arrange
    (tmp_path / "main.tex").write_text("no bib command here", encoding="utf-8")
    # Act
    resolved = resolve_compiled_bib(tmp_path)
    # Assert
    assert resolved is None

# EOF
