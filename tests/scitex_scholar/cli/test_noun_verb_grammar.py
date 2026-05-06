"""Tests for the noun-verb CLI grammar refactor (P2 / 1.3.0).

Covers:

- Every new noun-verb leaf parses cleanly with ``--help``.
- Every deprecated top-level alias parses, emits a ``DeprecationWarning``
  to stderr, and dispatches to the same handler as the new form.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from scitex_scholar import __main__ as cli_main

# ---------------------------------------------------------------------------
# --help on every new noun-verb leaf
# ---------------------------------------------------------------------------

NEW_HELP_FORMS = [
    ["paper", "process", "--help"],
    ["paper", "batch", "--help"],
    ["bibtex", "process", "--help"],
    ["pdf", "highlight", "--help"],
    ["library", "link-project-tree", "--help"],
    ["library", "materialize", "--help"],
    ["library", "dematerialize", "--help"],
    ["library", "db", "build", "--help"],
    ["library", "db", "migrate", "--help"],
    ["library", "db", "lookup", "--help"],
    ["library", "db", "list", "--help"],
    ["library", "db", "audit", "--help"],
    ["mcp", "start", "--help"],
    ["mcp", "list-tools", "--help"],
    ["mcp", "doctor", "--help"],
    ["mcp", "install", "--help"],
]


@pytest.mark.parametrize("argv", NEW_HELP_FORMS)
def test_new_form_help_parses_cleanly(argv):
    parser = cli_main.create_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(argv)
    assert exc.value.code == 0


# ---------------------------------------------------------------------------
# Deprecated top-level forms still parse with --help
# ---------------------------------------------------------------------------

DEPRECATED_HELP_FORMS = [
    ["single", "--help"],
    ["parallel", "--help"],
    ["highlight", "--help"],
    ["link-project-tree", "--help"],
    ["materialize", "--help"],
    ["dematerialize", "--help"],
    ["db", "audit", "--help"],
]


@pytest.mark.parametrize("argv", DEPRECATED_HELP_FORMS)
def test_deprecated_form_help_parses_cleanly(argv):
    parser = cli_main.create_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(argv)
    assert exc.value.code == 0


# ---------------------------------------------------------------------------
# Deprecated form → same handler + DeprecationWarning on stderr
# ---------------------------------------------------------------------------


def _run_cli(argv):
    """Run main_async with given argv (no sys.argv mutation)."""
    return asyncio.run(cli_main.main_async(argv))


def test_single_alias_warns_and_dispatches_to_paper_process(capsys):
    with patch.object(
        cli_main, "run_paper_process", new=AsyncMock(return_value=0)
    ) as h:
        rc = _run_cli(["single", "--doi", "10.1/x"])
    assert rc == 0
    assert h.called
    err = capsys.readouterr().err
    assert "DeprecationWarning" in err
    assert "scitex-scholar single" in err
    assert "paper process" in err


def test_parallel_alias_warns_and_dispatches_to_paper_batch(capsys):
    with patch.object(cli_main, "run_paper_batch", new=AsyncMock(return_value=0)) as h:
        rc = _run_cli(["parallel", "--dois", "10.1/x"])
    assert rc == 0
    assert h.called
    err = capsys.readouterr().err
    assert "DeprecationWarning" in err
    assert "paper batch" in err


def test_bibtex_alias_warns_and_dispatches_to_bibtex_process(capsys):
    with patch.object(
        cli_main, "run_bibtex_process", new=AsyncMock(return_value=0)
    ) as h:
        rc = _run_cli(["bibtex", "--bibtex", "/tmp/x.bib"])
    assert rc == 0
    assert h.called
    err = capsys.readouterr().err
    assert "DeprecationWarning" in err
    assert "bibtex process" in err


def test_highlight_alias_warns_and_dispatches_to_pdf_highlight(capsys):
    with patch.object(cli_main, "run_pdf_highlight", return_value=0) as h:
        rc = _run_cli(["highlight", "/tmp/x.pdf", "--stub"])
    assert rc == 0
    assert h.called
    err = capsys.readouterr().err
    assert "DeprecationWarning" in err
    assert "pdf highlight" in err


def test_link_project_tree_alias_warns_and_dispatches(capsys):
    with patch.object(cli_main, "run_library_link_project_tree", return_value=0) as h:
        rc = _run_cli(["link-project-tree", "/tmp/proj"])
    assert rc == 0
    assert h.called
    err = capsys.readouterr().err
    assert "DeprecationWarning" in err
    assert "library link-project-tree" in err


def test_materialize_alias_warns_and_dispatches(capsys):
    with patch.object(cli_main, "run_library_materialize", return_value=0) as h:
        rc = _run_cli(["materialize", "/tmp/link", "--bib", "/tmp/x.bib"])
    assert rc == 0
    assert h.called
    err = capsys.readouterr().err
    assert "DeprecationWarning" in err
    assert "library materialize" in err


def test_dematerialize_alias_warns_and_dispatches(capsys):
    with patch.object(cli_main, "run_library_dematerialize", return_value=0) as h:
        rc = _run_cli(["dematerialize", "/tmp/path"])
    assert rc == 0
    assert h.called
    err = capsys.readouterr().err
    assert "DeprecationWarning" in err
    assert "library dematerialize" in err


def test_db_alias_warns_and_dispatches_to_library_db(capsys):
    with patch.object(cli_main, "run_library_db", return_value=0) as h:
        rc = _run_cli(["db", "audit"])
    assert rc == 0
    assert h.called
    err = capsys.readouterr().err
    assert "DeprecationWarning" in err
    assert "library db" in err


# ---------------------------------------------------------------------------
# New forms do NOT emit DeprecationWarning
# ---------------------------------------------------------------------------


def test_new_paper_process_does_not_warn(capsys):
    with patch.object(cli_main, "run_paper_process", new=AsyncMock(return_value=0)):
        rc = _run_cli(["paper", "process", "--doi", "10.1/x"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "DeprecationWarning" not in err


def test_new_library_db_audit_does_not_warn(capsys):
    with patch.object(cli_main, "run_library_db", return_value=0):
        rc = _run_cli(["library", "db", "audit"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "DeprecationWarning" not in err


# ---------------------------------------------------------------------------
# No-args → help, exit 0
# ---------------------------------------------------------------------------


def test_no_args_prints_help_and_exits_zero(capsys):
    rc = _run_cli([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "scitex-scholar" in out
    assert "paper" in out
    assert "library" in out


# EOF
