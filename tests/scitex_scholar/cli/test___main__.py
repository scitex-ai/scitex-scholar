"""Tests for the Click-based scitex-scholar CLI grammar.

Mirrors `src/scitex_scholar/__main__.py`. Verifies:

- Every new noun-verb leaf reachable via `--help`.
- Every leaf docstring contains an `Example:` block.
- Mutating verbs accept `--dry-run` / `-y/--yes`.
- Read verbs accept `--json`.
- Top-level `--version`, `--help-recursive`, `--json` all parse.
- Hidden deprecated aliases still work and emit a warning.
- New noun-verb forms do NOT emit a deprecation warning.
- `list-python-apis` prints public API names.
- `skills list` prints leaf names.
"""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from scitex_scholar.__main__ import cli
from scitex_scholar.__main__ import main as cli_main

# ---------------------------------------------------------------------------
# Top-level universal flags
# ---------------------------------------------------------------------------


def test_version_flag_prints_semver():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"], prog_name="scitex-scholar")
    assert result.exit_code == 0
    assert re.match(r"scitex-scholar, version \d+\.\d+\.\d+", result.output.strip())


def test_help_lists_top_level_commands():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    out = result.output
    for cmd in [
        "paper",
        "bibtex",
        "pdf",
        "library",
        "mcp",
        "skills",
        "list-python-apis",
    ]:
        assert cmd in out, f"missing {cmd!r} in --help"
    assert "==SUPPRESS==" not in out


def test_help_recursive_runs():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help-recursive"])
    assert result.exit_code == 0
    assert "scitex-scholar paper" in result.output
    assert "scitex-scholar mcp" in result.output


# ---------------------------------------------------------------------------
# --help reaches every leaf
# ---------------------------------------------------------------------------

LEAVES = [
    ["paper", "fetch", "--help"],
    ["paper", "fetch-batch", "--help"],
    ["bibtex", "import", "--help"],
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
    ["skills", "list", "--help"],
    ["skills", "get", "--help"],
    ["skills", "install", "--help"],
    ["list-python-apis", "--help"],
]


@pytest.mark.parametrize("argv", LEAVES)
def test_leaf_help(argv):
    runner = CliRunner()
    result = runner.invoke(cli, argv)
    assert result.exit_code == 0, result.output
    assert "Example:" in result.output, f"no Example block: {' '.join(argv)}"


# ---------------------------------------------------------------------------
# Mutating verbs expose --dry-run and -y/--yes
# ---------------------------------------------------------------------------

MUTATING = [
    ["paper", "fetch"],
    ["paper", "fetch-batch"],
    ["bibtex", "import"],
    ["pdf", "highlight"],
    ["library", "link-project-tree"],
    ["library", "materialize"],
    ["library", "dematerialize"],
    ["library", "db", "build"],
    ["library", "db", "migrate"],
    ["mcp", "start"],
    ["mcp", "install"],
    ["skills", "install"],
]


@pytest.mark.parametrize("argv", MUTATING)
def test_mutating_has_dry_run_and_yes(argv):
    runner = CliRunner()
    result = runner.invoke(cli, argv + ["--help"])
    assert result.exit_code == 0
    assert "--dry-run" in result.output, argv
    assert "--yes" in result.output or "-y" in result.output, argv


# ---------------------------------------------------------------------------
# Read verbs expose --json
# ---------------------------------------------------------------------------

READS = [
    ["mcp", "list-tools"],
    ["library", "db", "list"],
    ["library", "db", "lookup"],
    ["library", "db", "audit"],
    ["skills", "list"],
    ["list-python-apis"],
]


@pytest.mark.parametrize("argv", READS)
def test_read_has_json(argv):
    runner = CliRunner()
    result = runner.invoke(cli, argv + ["--help"])
    assert result.exit_code == 0
    assert "--json" in result.output, argv


# ---------------------------------------------------------------------------
# Dry-run does not execute (no side effects)
# ---------------------------------------------------------------------------


def test_paper_fetch_dry_run():
    runner = CliRunner()
    result = runner.invoke(cli, ["paper", "fetch", "--doi", "10.1/x", "--dry-run"])
    assert result.exit_code == 0
    assert "DRY RUN" in result.output


def test_library_db_build_dry_run():
    runner = CliRunner()
    result = runner.invoke(cli, ["library", "db", "build", "--dry-run"])
    assert result.exit_code == 0
    assert "DRY RUN" in result.output


def test_mcp_start_dry_run():
    runner = CliRunner()
    result = runner.invoke(cli, ["mcp", "start", "--dry-run"])
    assert result.exit_code == 0
    assert "DRY RUN" in result.output


# ---------------------------------------------------------------------------
# list-python-apis
# ---------------------------------------------------------------------------


def test_list_python_apis_includes_core_classes():
    runner = CliRunner()
    result = runner.invoke(cli, ["list-python-apis"])
    assert result.exit_code == 0
    out = result.output
    for n in ["Scholar", "Paper", "Papers"]:
        assert n in out


def test_list_python_apis_json():
    runner = CliRunner()
    result = runner.invoke(cli, ["list-python-apis", "--json"])
    assert result.exit_code == 0
    import json as _j

    payload = _j.loads(result.output)
    names = {entry["name"] for entry in payload}
    assert {"Scholar", "Paper", "Papers"}.issubset(names)


# ---------------------------------------------------------------------------
# skills list
# ---------------------------------------------------------------------------


def test_skills_list_prints_leaf_names():
    runner = CliRunner()
    result = runner.invoke(cli, ["skills", "list"])
    assert result.exit_code == 0
    assert "04_cli-reference" in result.output


# ---------------------------------------------------------------------------
# mcp list-tools --json
# ---------------------------------------------------------------------------


def test_mcp_list_tools_json():
    runner = CliRunner()
    result = runner.invoke(cli, ["mcp", "list-tools", "--json"])
    assert result.exit_code == 0
    import json as _j

    payload = _j.loads(result.output)
    assert "tools" in payload
    assert payload["count"] == len(payload["tools"])
    assert any(t.startswith("scholar_") for t in payload["tools"])


# ---------------------------------------------------------------------------
# Deprecation aliases
# ---------------------------------------------------------------------------


def test_single_alias_warns():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["single", "--doi", "10.1/x", "--project", "demo", "--dry-run"],
    )
    assert result.exit_code == 0
    assert "DeprecationWarning" in result.output
    assert "paper fetch" in result.output


def test_parallel_alias_warns():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["parallel", "--dois", "10.1/x", "--dry-run"],
    )
    assert result.exit_code == 0
    assert "DeprecationWarning" in result.output
    assert "paper fetch-batch" in result.output


def test_bibtex_legacy_form_invokes_import(tmp_path):
    """`bibtex --bibtex …` (no subcommand) is the legacy form."""
    bib = tmp_path / "x.bib"
    bib.write_text("")
    # Use main() so the argv-rewrite for the legacy `bibtex --bibtex` form runs.
    rc = cli_main(["bibtex", "--bibtex", str(bib), "--dry-run"])
    assert rc == 0


def test_highlight_alias_warns(tmp_path):
    pdf = tmp_path / "x.pdf"
    pdf.write_text("%PDF-1.4\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["highlight", str(pdf), "--stub", "--dry-run"])
    assert "DeprecationWarning" in result.output
    assert "pdf highlight" in result.output


def test_link_project_tree_alias_warns(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["link-project-tree", str(tmp_path), "--dry-run"],
    )
    assert result.exit_code == 0
    assert "DeprecationWarning" in result.output


def test_materialize_alias_warns(tmp_path):
    bib = tmp_path / "x.bib"
    bib.write_text("")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["materialize", str(tmp_path / "link"), "--bib", str(bib), "--dry-run"],
    )
    assert result.exit_code == 0
    assert "DeprecationWarning" in result.output


def test_dematerialize_alias_warns(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["dematerialize", str(tmp_path), "--dry-run"],
    )
    assert result.exit_code == 0
    assert "DeprecationWarning" in result.output


def test_db_alias_warns():
    runner = CliRunner()
    result = runner.invoke(cli, ["db", "build", "--dry-run"])
    assert result.exit_code == 0
    assert "DeprecationWarning" in result.output
    assert "library db" in result.output


# ---------------------------------------------------------------------------
# New forms do NOT emit DeprecationWarning
# ---------------------------------------------------------------------------


def test_new_paper_fetch_does_not_warn():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["paper", "fetch", "--doi", "10.1/x", "--dry-run"],
    )
    assert "DeprecationWarning" not in result.output


def test_new_library_db_audit_does_not_warn(tmp_path):
    runner = CliRunner()
    with patch("scitex_scholar.storage._library_audit.audit") as a:
        a.return_value.has_issues = False
        a.return_value.to_dict.return_value = {}
        result = runner.invoke(
            cli,
            ["library", "db", "audit", "--library-root", str(tmp_path), "--json"],
        )
    assert result.exit_code == 0
    assert "DeprecationWarning" not in result.output


# ---------------------------------------------------------------------------
# No-args -> help, exit 0
# ---------------------------------------------------------------------------


def test_no_args_prints_help():
    runner = CliRunner()
    result = runner.invoke(cli, [], prog_name="scitex-scholar")
    assert result.exit_code == 0
    assert "scitex-scholar" in result.output
    assert "paper" in result.output
    assert "library" in result.output


# EOF
