"""CLI search verb: query in, paper rows out (no network in tests).

One assertion per test (STX-TQ007): tuple compares.
"""

from click.testing import CliRunner

from scitex_scholar._cli.search import _format_row
from scitex_scholar._cli_main import cli


def test_search_verb_is_listed_in_top_level_help():
    # Arrange
    # Act
    result = CliRunner().invoke(cli, ["--help"], prog_name="scitex-scholar")
    # Assert
    assert (result.exit_code, "search" in result.output) == (0, True)


def test_search_dry_run_prints_plan_without_executing():
    # Arrange
    # Act
    result = CliRunner().invoke(
        cli, ["search", "hippocampus", "--dry-run"], prog_name="scitex-scholar"
    )
    # Assert
    assert (result.exit_code, "DRY RUN" in result.output) == (0, True)


def test_search_rejects_out_of_range_max_results():
    # Arrange
    # Act
    result = CliRunner().invoke(
        cli, ["search", "x", "--max-results", "0"], prog_name="scitex-scholar"
    )
    # Assert
    assert (result.exit_code != 0, "max-results" in result.output) == (True, True)


def test_search_row_formats_title_year_doi():
    # Arrange
    paper = {"title": "Seizure prediction", "year": 2024, "doi": "10.1/x"}
    # Act
    line = _format_row(0, paper)
    # Assert
    assert line == "1. Seizure prediction (2024) 10.1/x"
