#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: tests/scitex_scholar/verify_cites/test__cli.py
# ----------------------------------------
"""Unit tests for scitex_scholar.verify_cites._cli (real CliRunner invocation)."""
from __future__ import annotations

import pytest

vc_cli = pytest.importorskip("scitex_scholar.verify_cites._cli")
click_testing = pytest.importorskip("click.testing")
from scitex_scholar.verify_cites._cli import verify_cites_command  # noqa: E402
from scitex_scholar.verify_cites._model import EXIT_NO_CITES  # noqa: E402


def _run(*args):
    runner = click_testing.CliRunner()
    return runner.invoke(vc_cli.verify_cites_command, list(args))


def test_verify_cites_command_no_cites_exits_with_no_cites_code(tmp_path):
    # Arrange: empty manuscript dir + an existing but unreferenced .bib.
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{Unused, title={t}}\n", encoding="utf-8")
    out = tmp_path / "citation_status.json"
    # Act
    result = _run(str(tmp_path), "--bib", str(bib), "--out", str(out), "--offline")
    # Assert
    assert result.exit_code == EXIT_NO_CITES


def test_verify_cites_command_writes_sidecar_json(tmp_path):
    # Arrange
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{Unused, title={t}}\n", encoding="utf-8")
    out = tmp_path / "citation_status.json"
    # Act
    _run(str(tmp_path), "--bib", str(bib), "--out", str(out), "--offline")
    # Assert
    assert out.exists()


def test_verify_cites_command_missing_bib_raises_click_exception(tmp_path):
    # Arrange: no .bib anywhere and no \bibliography command to resolve one.
    (tmp_path / "main.tex").write_text(r"\cite{Foo2020}", encoding="utf-8")
    # Act
    result = _run(str(tmp_path), "--offline")
    # Assert
    assert result.exit_code != 0

# EOF
