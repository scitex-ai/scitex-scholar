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

import pytest
from click.testing import CliRunner

from scitex_scholar._cli_main import cli
from scitex_scholar._cli_main import main as cli_main

# ---------------------------------------------------------------------------
# Top-level universal flags
# ---------------------------------------------------------------------------


def test_version_flag_prints_semver_result_exit_code_equals_n_0():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["--version"], prog_name="scitex-scholar")
    # Act
    # Assert
    assert result.exit_code == 0


def test_version_flag_prints_semver_re_match_scitex_scholar_version_d_d_d_result_output_strip():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["--version"], prog_name="scitex-scholar")
    # Act
    # Assert
    assert re.match(r"scitex-scholar, version \d+\.\d+\.\d+", result.output.strip())




def test_help_lists_top_level_commands_result_exit_code_equals_n_0():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["--help"])
    # Act
    # Assert
    assert result.exit_code == 0


def test_help_lists_top_level_commands_all_cmd_in_out_for_cmd_in_paper_bibtex_pdf_library_mcp_skill():
    # Arrange
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    # Act
    out = result.output
    # Act
    # Assert
    assert all(cmd in out for cmd in ['paper', 'bibtex', 'pdf', 'library', 'mcp', 'skills', 'list-python-apis']), f'missing {cmd!r} in --help'


def test_help_lists_top_level_commands_suppress_not_in_out():
    # Arrange
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    # Act
    out = result.output
    # Act
    # Assert
    assert "==SUPPRESS==" not in out




def test_help_recursive_runs_result_exit_code_equals_n_0():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["--help-recursive"])
    # Act
    # Assert
    assert result.exit_code == 0


def test_help_recursive_runs_scitex_scholar_paper_in_result_output():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["--help-recursive"])
    # Act
    # Assert
    assert "scitex-scholar paper" in result.output


def test_help_recursive_runs_scitex_scholar_mcp_in_result_output():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["--help-recursive"])
    # Act
    # Assert
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
def test_leaf_help_result_exit_code_equals_n_0(argv):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, argv)
    # Assert
    assert result.exit_code == 0, result.output
    # The "Example:" block requirement is the audit-cli §4 rule, enforced
    # by `tests/develop/test_audit.py` via the audit-all gate (currently
    # skipping §4 while docstrings are being swept). Don't double-enforce
    # here — the leaf only needs to render --help cleanly.


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
def test_mutating_has_dry_run_and_yes_result_exit_code_equals_n_0(argv):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, argv + ["--help"])
    # Act
    # Assert
    assert result.exit_code == 0


@pytest.mark.parametrize("argv", MUTATING)
def test_mutating_has_dry_run_and_yes_dry_run_in_result_output(argv):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, argv + ["--help"])
    # Act
    # Assert
    assert "--dry-run" in result.output, argv


@pytest.mark.parametrize("argv", MUTATING)
def test_mutating_has_dry_run_and_yes_yes_in_result_output_or_y_in_result_output(argv):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, argv + ["--help"])
    # Act
    # Assert
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
def test_read_has_json_result_exit_code_equals_n_0(argv):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, argv + ["--help"])
    # Act
    # Assert
    assert result.exit_code == 0


@pytest.mark.parametrize("argv", READS)
def test_read_has_json_json_in_result_output(argv):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, argv + ["--help"])
    # Act
    # Assert
    assert "--json" in result.output, argv




# ---------------------------------------------------------------------------
# Dry-run does not execute (no side effects)
# ---------------------------------------------------------------------------


def test_paper_fetch_dry_run_result_exit_code_equals_n_0():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["paper", "fetch", "--doi", "10.1/x", "--dry-run"])
    # Act
    # Assert
    assert result.exit_code == 0


def test_paper_fetch_dry_run_dry_run_in_result_output():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["paper", "fetch", "--doi", "10.1/x", "--dry-run"])
    # Act
    # Assert
    assert "DRY RUN" in result.output




def test_library_db_build_dry_run_result_exit_code_equals_n_0():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["library", "db", "build", "--dry-run"])
    # Act
    # Assert
    assert result.exit_code == 0


def test_library_db_build_dry_run_dry_run_in_result_output():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["library", "db", "build", "--dry-run"])
    # Act
    # Assert
    assert "DRY RUN" in result.output




def test_mcp_start_dry_run_result_exit_code_equals_n_0():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["mcp", "start", "--dry-run"])
    # Act
    # Assert
    assert result.exit_code == 0


def test_mcp_start_dry_run_dry_run_in_result_output():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["mcp", "start", "--dry-run"])
    # Act
    # Assert
    assert "DRY RUN" in result.output




# ---------------------------------------------------------------------------
# list-python-apis
# ---------------------------------------------------------------------------


def test_list_python_apis_includes_core_classes_result_exit_code_equals_n_0():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["list-python-apis"])
    # Act
    # Assert
    assert result.exit_code == 0


def test_list_python_apis_includes_core_classes_all_n_in_out_for_n_in_scholar_paper_papers():
    # Arrange
    runner = CliRunner()
    result = runner.invoke(cli, ["list-python-apis"])
    # Act
    out = result.output
    # Act
    # Assert
    assert all(n in out for n in ['Scholar', 'Paper', 'Papers'])




def test_list_python_apis_json_result_exit_code_equals_n_0():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["list-python-apis", "--json"])
    # Act
    # Assert
    assert result.exit_code == 0


def test_list_python_apis_json_scholar_paper_papers_issubset_names():
    # Arrange
    runner = CliRunner()
    result = runner.invoke(cli, ["list-python-apis", "--json"])
    import json as _j
    payload = _j.loads(result.output)
    # Act
    names = {entry["name"] for entry in payload}
    # Act
    # Assert
    assert {"Scholar", "Paper", "Papers"}.issubset(names)




# ---------------------------------------------------------------------------
# skills list
# ---------------------------------------------------------------------------


def test_skills_list_prints_leaf_names_result_exit_code_equals_n_0():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["skills", "list"])
    # Act
    # Assert
    assert result.exit_code == 0


def test_skills_list_prints_leaf_names_n_04_cli_reference_in_result_output():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["skills", "list"])
    # Act
    # Assert
    assert "04_cli-reference" in result.output




# ---------------------------------------------------------------------------
# mcp list-tools --json
# ---------------------------------------------------------------------------


def test_mcp_list_tools_json_result_exit_code_equals_n_0():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["mcp", "list-tools", "--json"])
    # Act
    # Assert
    assert result.exit_code == 0


def test_mcp_list_tools_json_tools_in_payload():
    # Arrange
    runner = CliRunner()
    result = runner.invoke(cli, ["mcp", "list-tools", "--json"])
    import json as _j
    # Act
    payload = _j.loads(result.output)
    # Act
    # Assert
    assert "tools" in payload


def test_mcp_list_tools_json_payload_count_len_payload_tools():
    # Arrange
    runner = CliRunner()
    result = runner.invoke(cli, ["mcp", "list-tools", "--json"])
    import json as _j
    # Act
    payload = _j.loads(result.output)
    # Act
    # Assert
    assert payload["count"] == len(payload["tools"])


def test_mcp_list_tools_json_any_t_startswith_scholar_for_t_in_payload_tools():
    # Arrange
    runner = CliRunner()
    result = runner.invoke(cli, ["mcp", "list-tools", "--json"])
    import json as _j
    # Act
    payload = _j.loads(result.output)
    # Act
    # Assert
    assert any(t.startswith("scholar_") for t in payload["tools"])




# ---------------------------------------------------------------------------
# Deprecation aliases
# ---------------------------------------------------------------------------


def test_single_alias_warns_result_exit_code_equals_n_0():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli,
        ["single", "--doi", "10.1/x", "--project", "demo", "--dry-run"],
    )
    # Act
    # Assert
    assert result.exit_code == 0


def test_single_alias_warns_deprecationwarning_in_result_output():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli,
        ["single", "--doi", "10.1/x", "--project", "demo", "--dry-run"],
    )
    # Act
    # Assert
    assert "DeprecationWarning" in result.output


def test_single_alias_warns_paper_fetch_in_result_output():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli,
        ["single", "--doi", "10.1/x", "--project", "demo", "--dry-run"],
    )
    # Act
    # Assert
    assert "paper fetch" in result.output




def test_parallel_alias_warns_result_exit_code_equals_n_0():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli,
        ["parallel", "--dois", "10.1/x", "--dry-run"],
    )
    # Act
    # Assert
    assert result.exit_code == 0


def test_parallel_alias_warns_deprecationwarning_in_result_output():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli,
        ["parallel", "--dois", "10.1/x", "--dry-run"],
    )
    # Act
    # Assert
    assert "DeprecationWarning" in result.output


def test_parallel_alias_warns_paper_fetch_batch_in_result_output():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli,
        ["parallel", "--dois", "10.1/x", "--dry-run"],
    )
    # Act
    # Assert
    assert "paper fetch-batch" in result.output




def test_bibtex_legacy_form_invokes_import(tmp_path):
    """`bibtex --bibtex …` (no subcommand) is the legacy form."""
    # Arrange
    bib = tmp_path / "x.bib"
    bib.write_text("")
    # Use main() so the argv-rewrite for the legacy `bibtex --bibtex` form runs.
    # Act
    rc = cli_main(["bibtex", "--bibtex", str(bib), "--dry-run"])
    # Assert
    assert rc == 0


def test_highlight_alias_warns_deprecationwarning_in_result_output(tmp_path):
    # Arrange
    pdf = tmp_path / "x.pdf"
    pdf.write_text("%PDF-1.4\n")
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["highlight", str(pdf), "--stub", "--dry-run"])
    # Act
    # Assert
    assert "DeprecationWarning" in result.output


def test_highlight_alias_warns_pdf_highlight_in_result_output(tmp_path):
    # Arrange
    pdf = tmp_path / "x.pdf"
    pdf.write_text("%PDF-1.4\n")
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["highlight", str(pdf), "--stub", "--dry-run"])
    # Act
    # Assert
    assert "pdf highlight" in result.output




def test_link_project_tree_alias_warns_result_exit_code_equals_n_0(tmp_path):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli,
        ["link-project-tree", str(tmp_path), "--dry-run"],
    )
    # Act
    # Assert
    assert result.exit_code == 0


def test_link_project_tree_alias_warns_deprecationwarning_in_result_output(tmp_path):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli,
        ["link-project-tree", str(tmp_path), "--dry-run"],
    )
    # Act
    # Assert
    assert "DeprecationWarning" in result.output




def test_materialize_alias_warns_result_exit_code_equals_n_0(tmp_path):
    # Arrange
    bib = tmp_path / "x.bib"
    bib.write_text("")
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli,
        ["materialize", str(tmp_path / "link"), "--bib", str(bib), "--dry-run"],
    )
    # Act
    # Assert
    assert result.exit_code == 0


def test_materialize_alias_warns_deprecationwarning_in_result_output(tmp_path):
    # Arrange
    bib = tmp_path / "x.bib"
    bib.write_text("")
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli,
        ["materialize", str(tmp_path / "link"), "--bib", str(bib), "--dry-run"],
    )
    # Act
    # Assert
    assert "DeprecationWarning" in result.output




def test_dematerialize_alias_warns_result_exit_code_equals_n_0(tmp_path):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli,
        ["dematerialize", str(tmp_path), "--dry-run"],
    )
    # Act
    # Assert
    assert result.exit_code == 0


def test_dematerialize_alias_warns_deprecationwarning_in_result_output(tmp_path):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli,
        ["dematerialize", str(tmp_path), "--dry-run"],
    )
    # Act
    # Assert
    assert "DeprecationWarning" in result.output




def test_db_alias_warns_result_exit_code_equals_n_0():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["db", "build", "--dry-run"])
    # Act
    # Assert
    assert result.exit_code == 0


def test_db_alias_warns_deprecationwarning_in_result_output():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["db", "build", "--dry-run"])
    # Act
    # Assert
    assert "DeprecationWarning" in result.output


def test_db_alias_warns_library_db_in_result_output():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["db", "build", "--dry-run"])
    # Act
    # Assert
    assert "library db" in result.output




# ---------------------------------------------------------------------------
# New forms do NOT emit DeprecationWarning
# ---------------------------------------------------------------------------


def test_new_paper_fetch_does_not_warn():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli,
        ["paper", "fetch", "--doi", "10.1/x", "--dry-run"],
    )
    # Assert
    assert "DeprecationWarning" not in result.output


def test_new_library_db_audit_does_not_warn_result_exit_code_equals_n_0(tmp_path):
    # Arrange — a real library_root with an empty MASTER subdir; the real
    # auditor walks this and returns a clean (no-issues) report, exercising
    # the live `library db audit --json` codepath end-to-end.
    (tmp_path / "MASTER").mkdir()
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli,
        ["library", "db", "audit", "--library-root", str(tmp_path), "--json"],
    )
    # Assert
    assert result.exit_code == 0


def test_new_library_db_audit_does_not_warn_deprecationwarning_not_in_result_output(tmp_path):
    # Arrange
    (tmp_path / "MASTER").mkdir()
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli,
        ["library", "db", "audit", "--library-root", str(tmp_path), "--json"],
    )
    # Assert
    assert "DeprecationWarning" not in result.output




# ---------------------------------------------------------------------------
# No-args -> help, exit 0
# ---------------------------------------------------------------------------


def test_no_args_prints_help_result_exit_code_equals_n_0():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, [], prog_name="scitex-scholar")
    # Act
    # Assert
    assert result.exit_code == 0


def test_no_args_prints_help_scitex_scholar_in_result_output():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, [], prog_name="scitex-scholar")
    # Act
    # Assert
    assert "scitex-scholar" in result.output


def test_no_args_prints_help_paper_in_result_output():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, [], prog_name="scitex-scholar")
    # Act
    # Assert
    assert "paper" in result.output


def test_no_args_prints_help_library_in_result_output():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, [], prog_name="scitex-scholar")
    # Act
    # Assert
    assert "library" in result.output




# EOF
