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


def test_macro_parameter_placeholder_is_not_a_cite_key(tmp_path):
    """Regression: ``\\cite{#1}`` inside a \\newcommand body is a macro
    parameter, not a key; counting it reported a false UNLINKED citation."""
    # Arrange
    (tmp_path / "macros.tex").write_text(
        r"\newcommand{\mycite}[1]{see \citep{#1}}"
        r"\newcommand{\twocite}[2]{\cite{#1,##2}}"
        "\n"
        r"Body \mycite{Real2020}.",
        encoding="utf-8",
    )
    # Act
    keys = extract_cited_keys(tmp_path)
    # Assert: only the real key passed to the wrapper (\\mycite matches the
    # *cite* family) survives; the #1 / ##2 placeholders do not.
    assert keys == {"Real2020"}


def test_legacy_and_archive_sources_are_not_scanned(tmp_path):
    """Regression: old manuscript sources moved under legacy/ (and versioned
    copies under archive/) are not built, so their \\cite keys must not be
    verified as if they were in the manuscript."""
    # Arrange
    (tmp_path / "01_manuscript" / "contents").mkdir(parents=True)
    (tmp_path / "01_manuscript" / "contents" / "intro.tex").write_text(
        r"\cite{Live2020}", encoding="utf-8"
    )
    for old in ("legacy/contents", "archive"):
        d = tmp_path / "01_manuscript" / old
        d.mkdir(parents=True)
        (d / "old.tex").write_text(r"\cite{Old1999}", encoding="utf-8")
    # Act
    keys = extract_cited_keys(tmp_path)
    # Assert
    assert keys == {"Live2020"}


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
